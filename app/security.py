from datetime import datetime, timedelta, timezone
from hashlib import sha256
from uuid import uuid4

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from pwdlib import PasswordHash
from sqlmodel import Session

from .config import settings
from .database import get_session
from .models import AuthSession, User

ALGORITHM = "HS256"
bearer_scheme = HTTPBearer(auto_error=False)
REGISTRATION_TOKEN_PURPOSE = "email_registration"
password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    return password_hash.verify(password, hashed_password)


def create_access_token(data: dict[str, str]) -> str:
    payload = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload.update({"exp": expire})
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def create_registration_token(email: str) -> str:
    expire = datetime.now(timezone.utc) + timedelta(
        minutes=settings.registration_token_expire_minutes
    )
    payload = {"sub": email, "purpose": REGISTRATION_TOKEN_PURPOSE, "exp": expire}
    return jwt.encode(payload, settings.secret_key, algorithm=ALGORITHM)


def decode_registration_token(token: str) -> str:
    payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    if payload.get("purpose") != REGISTRATION_TOKEN_PURPOSE:
        raise JWTError("Invalid registration token purpose")

    email = payload.get("sub")
    if not isinstance(email, str):
        raise JWTError("Invalid registration token subject")
    return email


def create_refresh_token() -> str:
    return uuid4().hex + uuid4().hex


def hash_token(token: str) -> str:
    return sha256(token.encode()).hexdigest()


def create_session_access_token(user: User, session_id: str) -> str:
    return create_access_token(data={"sub": str(user.id), "sid": session_id})


def decode_access_token(token: str) -> dict[str, str]:
    payload = jwt.decode(token, settings.secret_key, algorithms=[ALGORITHM])
    if not isinstance(payload.get("sub"), str) or not isinstance(payload.get("sid"), str):
        raise JWTError("Invalid access token")
    return payload


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    session: Session = Depends(get_session),
) -> User:
    if credentials is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")
    try:
        payload = decode_access_token(credentials.credentials)
        user_id = int(payload["sub"])
    except (JWTError, ValueError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token") from None

    user = session.get(User, user_id)
    auth_session = session.get(AuthSession, payload["sid"])
    now = datetime.now(timezone.utc)
    if (
        user is None
        or not user.is_active
        or user.deleted_at is not None
        or auth_session is None
        or auth_session.user_id != user.id
        or auth_session.revoked_at is not None
        or auth_session.expires_at <= now
    ):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or revoked session")
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    if user.role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin role required")
    return user
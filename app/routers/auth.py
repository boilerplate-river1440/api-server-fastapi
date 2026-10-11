from datetime import datetime, timedelta, timezone
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials
from jose import JWTError
from sqlmodel import Session, select

from ..config import settings
from ..database import get_session
from ..models import AuthSession, OAuthAccount, OneTimeToken, Profile, User
from ..schemas import (
    LoginRequest,
    OAuthLinkRequest,
    PasswordRequest,
    RefreshRequest,
    RegisterEmailRequest,
    RegisterPasswordRequest,
    RegistrationToken,
    SessionRead,
    Token,
    TokenRequest,
    UserRead,
)
from ..security import (
    bearer_scheme,
    create_refresh_token,
    create_registration_token,
    create_session_access_token,
    decode_access_token,
    decode_registration_token,
    get_current_user,
    hash_password,
    hash_token,
    verify_password,
)

router = APIRouter(prefix="/auth", tags=["auth"])


def normalize_email(email: str) -> str:
    return email.strip().lower()


def issue_session(user: User, request: Request, session: Session) -> Token:
    refresh_token = create_refresh_token()
    auth_session = AuthSession(
        id=uuid4().hex,
        user_id=user.id,
        refresh_token_hash=hash_token(refresh_token),
        user_agent=request.headers.get("user-agent"),
        ip_address=request.client.host if request.client else None,
        expires_at=datetime.now(timezone.utc) + timedelta(days=settings.refresh_token_expire_days),
    )
    session.add(auth_session)
    session.commit()
    return Token(access_token=create_session_access_token(user, auth_session.id), refresh_token=refresh_token)


def create_one_time_token(user_id: int, purpose: str, expires_at: datetime, session: Session) -> str:
    token = create_refresh_token()
    session.add(OneTimeToken(user_id=user_id, token_hash=hash_token(token), purpose=purpose, expires_at=expires_at))
    session.commit()
    return token


def consume_one_time_token(token: str, purpose: str, session: Session) -> OneTimeToken:
    record = session.exec(select(OneTimeToken).where(OneTimeToken.token_hash == hash_token(token), OneTimeToken.purpose == purpose)).first()
    now = datetime.now(timezone.utc)
    if record is None or record.consumed_at is not None or record.expires_at <= now:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired token")
    record.consumed_at = now
    session.add(record)
    return record


@router.post("/register/email", response_model=RegistrationToken)
def register_email(request: RegisterEmailRequest, session: Session = Depends(get_session)) -> RegistrationToken:
    email = normalize_email(str(request.email))
    if session.exec(select(User).where(User.email == email)).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")
    return RegistrationToken(email=email, token=create_registration_token(email))


@router.post("/register/password", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def register_password(request: RegisterPasswordRequest, session: Session = Depends(get_session)) -> User:
    email = normalize_email(str(request.email))
    try:
        token_email = normalize_email(decode_registration_token(request.token))
    except JWTError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired registration token") from None
    if token_email != email:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Registration token does not match email")
    if session.exec(select(User).where(User.email == email)).first():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")
    user = User(email=email, hashed_password=hash_password(request.password))
    session.add(user)
    session.commit()
    session.refresh(user)
    session.add(Profile(user_id=user.id))
    session.commit()
    return user


@router.post("/login", response_model=Token)
def login(request: LoginRequest, http_request: Request, session: Session = Depends(get_session)) -> Token:
    email = normalize_email(str(request.email))
    user = session.exec(select(User).where(User.email == email, User.deleted_at.is_(None))).first()
    if user is None or user.hashed_password is None or not user.is_active or not verify_password(request.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password", headers={"WWW-Authenticate": "Bearer"})
    return issue_session(user, http_request, session)


@router.post("/refresh", response_model=Token)
def refresh(request: RefreshRequest, http_request: Request, session: Session = Depends(get_session)) -> Token:
    auth_session = session.exec(select(AuthSession).where(AuthSession.refresh_token_hash == hash_token(request.refresh_token))).first()
    now = datetime.now(timezone.utc)
    if auth_session is None or auth_session.revoked_at is not None or auth_session.expires_at <= now:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token")
    user = session.get(User, auth_session.user_id)
    if user is None or not user.is_active or user.deleted_at is not None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is inactive")
    auth_session.revoked_at = now
    session.add(auth_session)
    session.commit()
    return issue_session(user, http_request, session)


def session_id_from_credentials(credentials: HTTPAuthorizationCredentials) -> str:
    try:
        return decode_access_token(credentials.credentials)["sid"]
    except (JWTError, KeyError):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token") from None


@router.post("/logout")
def logout(user: User = Depends(get_current_user), credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme), session: Session = Depends(get_session)) -> dict[str, str]:
    auth_session = session.get(AuthSession, session_id_from_credentials(credentials))
    if auth_session and auth_session.user_id == user.id:
        auth_session.revoked_at = datetime.now(timezone.utc)
        session.add(auth_session)
        session.commit()
    return {"message": "Logged out"}


@router.post("/logout-everywhere")
def logout_everywhere(user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, str]:
    now = datetime.now(timezone.utc)
    for auth_session in session.exec(select(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))):
        auth_session.revoked_at = now
        session.add(auth_session)
    session.commit()
    return {"message": "All sessions revoked"}


@router.get("/sessions", response_model=list[SessionRead])
def list_sessions(user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> list[AuthSession]:
    return list(session.exec(select(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))))


@router.post("/verify-email", response_model=UserRead)
def verify_email(request: TokenRequest, session: Session = Depends(get_session)) -> User:
    record = consume_one_time_token(request.token, "email_verification", session)
    user = session.get(User, record.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.email_verified_at = datetime.now(timezone.utc)
    session.add(user)
    session.commit()
    return user


@router.post("/verify-email/request", response_model=RegistrationToken)
def request_email_verification(user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> RegistrationToken:
    token = create_one_time_token(user.id, "email_verification", datetime.now(timezone.utc) + timedelta(hours=settings.verification_token_expire_hours), session)
    return RegistrationToken(email=user.email, token=token)


@router.post("/forgot-password", response_model=RegistrationToken)
def forgot_password(request: RegisterEmailRequest, session: Session = Depends(get_session)) -> RegistrationToken:
    email = normalize_email(str(request.email))
    user = session.exec(select(User).where(User.email == email, User.deleted_at.is_(None))).first()
    if user is None:
        return RegistrationToken(email=email, token="")
    token = create_one_time_token(user.id, "password_reset", datetime.now(timezone.utc) + timedelta(minutes=settings.password_reset_token_expire_minutes), session)
    return RegistrationToken(email=email, token=token)


@router.post("/reset-password", response_model=UserRead)
def reset_password(request: PasswordRequest, token: str, session: Session = Depends(get_session)) -> User:
    record = consume_one_time_token(token, "password_reset", session)
    user = session.get(User, record.user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")
    user.hashed_password = hash_password(request.password)
    session.add(user)
    session.commit()
    return user


@router.post("/change-password", response_model=UserRead)
def change_password(request: PasswordRequest, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> User:
    user.hashed_password = hash_password(request.password)
    session.add(user)
    session.commit()
    return user


@router.post("/oauth/link", response_model=OAuthAccount)
def link_oauth(request: OAuthLinkRequest, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> OAuthAccount:
    existing = session.exec(select(OAuthAccount).where(OAuthAccount.provider == request.provider, OAuthAccount.provider_user_id == request.provider_user_id)).first()
    if existing:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="OAuth account is already linked")
    account = OAuthAccount(user_id=user.id, provider=request.provider, provider_user_id=request.provider_user_id, email=str(request.email) if request.email else None)
    session.add(account)
    session.commit()
    session.refresh(account)
    return account


@router.delete("/oauth/{provider}")
def unlink_oauth(provider: str, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict[str, str]:
    account = session.exec(select(OAuthAccount).where(OAuthAccount.user_id == user.id, OAuthAccount.provider == provider)).first()
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="OAuth account is not linked")
    linked_accounts = list(session.exec(select(OAuthAccount).where(OAuthAccount.user_id == user.id)))
    if user.hashed_password is None and len(linked_accounts) == 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Set a password before unlinking the only login method")
    session.delete(account)
    session.commit()
    return {"message": "OAuth account unlinked"}

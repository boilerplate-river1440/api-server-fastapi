from fastapi import APIRouter, Depends, Request
from sqlmodel import Session, select

from ..database import get_session
from ..models import OAuthAccount, User
from ..oauth import oauth
from ..schemas import Token
from .auth import issue_session

router = APIRouter(prefix="/auth/google", tags=["oauth"])


@router.get("/login")
async def google_login(request: Request):
    redirect_uri = request.url_for("google_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback", name="google_callback", response_model=Token)
async def google_callback(
    request: Request,
    session: Session = Depends(get_session),
) -> Token:
    token = await oauth.google.authorize_access_token(request)
    userinfo = token["userinfo"]
    provider_user_id = userinfo["sub"]
    email = userinfo["email"]

    oauth_account = session.exec(
        select(OAuthAccount).where(
            OAuthAccount.provider == "google",
            OAuthAccount.provider_user_id == provider_user_id,
        )
    ).first()

    if oauth_account:
        user = session.get(User, oauth_account.user_id)
    else:
        user = session.exec(select(User).where(User.email == email)).first()
        if not user:
            user = User(email=email)
            session.add(user)
            session.commit()
            session.refresh(user)

        session.add(
            OAuthAccount(
                user_id=user.id,
                provider="google",
                provider_user_id=provider_user_id,
                email=email,
            )
        )
        session.commit()

    if user is None:
        raise ValueError("OAuth account points to a missing user")

    return issue_session(user, request, session)
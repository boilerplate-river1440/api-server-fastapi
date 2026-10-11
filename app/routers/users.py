from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, UploadFile
from sqlmodel import Session, select

from ..database import get_session
from ..models import Profile, User
from ..schemas import AdminUserRead, ProfileRead, ProfileUpdate, UserMeRead, UserRead
from ..security import get_current_user, require_admin
from ..storage import storage

router = APIRouter(prefix="/users", tags=["users"])


def profile_for(user: User, session: Session) -> Profile:
    profile = session.exec(select(Profile).where(Profile.user_id == user.id)).first()
    if profile is None:
        profile = Profile(user_id=user.id)
        session.add(profile)
        session.commit()
        session.refresh(profile)
    return profile


def user_with_profile(user: User, session: Session) -> UserMeRead:
    return UserMeRead(
        id=user.id,
        email=user.email,
        is_active=user.is_active,
        role=user.role,
        email_verified_at=user.email_verified_at,
        profile=profile_for(user, session),
    )


@router.get("/me", response_model=UserMeRead)
def read_me(user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict:
    return user_with_profile(user, session)


@router.patch("/me/profile", response_model=ProfileRead)
def update_profile(request: ProfileUpdate, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> Profile:
    profile = profile_for(user, session)
    for field, value in request.model_dump(exclude_unset=True).items():
        setattr(profile, field, value)
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


@router.patch("/me", response_model=UserMeRead)
def update_me(request: ProfileUpdate, user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> dict:
    update_profile(request, user, session)
    return user_with_profile(user, session)


@router.post("/me/avatar", response_model=ProfileRead)
async def upload_avatar(file: UploadFile = File(...), user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> Profile:
    profile = profile_for(user, session)
    profile.avatar_url = await storage.save(file, f"users/{user.id}")
    session.add(profile)
    session.commit()
    session.refresh(profile)
    return profile


@router.delete("/me", status_code=204)
def delete_me(user: User = Depends(get_current_user), session: Session = Depends(get_session)) -> None:
    user.email = f"deleted-{user.id}@invalid.local"
    user.hashed_password = None
    user.is_active = False
    user.deleted_at = datetime.now(timezone.utc)
    session.add(user)
    session.commit()


@router.get("/", response_model=list[AdminUserRead], dependencies=[Depends(require_admin)])
def list_users(search: str | None = None, limit: int = 50, offset: int = 0, session: Session = Depends(get_session)) -> list[User]:
    limit = min(max(limit, 1), 100)
    offset = max(offset, 0)
    query = select(User).where(User.deleted_at.is_(None))
    if search:
        query = query.where(User.email.contains(search.strip().lower()))
    return list(session.exec(query.offset(offset).limit(limit)))


@router.patch("/{user_id}/active", response_model=AdminUserRead, dependencies=[Depends(require_admin)])
def set_user_active(user_id: int, active: bool, session: Session = Depends(get_session)) -> User:
    user = session.get(User, user_id)
    if user is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="User not found")
    user.is_active = active
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@router.patch("/{user_id}/role", response_model=AdminUserRead, dependencies=[Depends(require_admin)])
def set_user_role(user_id: int, role: str, session: Session = Depends(get_session)) -> User:
    if role not in {"user", "admin"}:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="Role must be user or admin")
    user = session.get(User, user_id)
    if user is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="User not found")
    user.role = role
    session.add(user)
    session.commit()
    session.refresh(user)
    return user

from datetime import datetime

from pydantic import EmailStr, Field
from sqlmodel import SQLModel


class ItemCreate(SQLModel):
    name: str
    status: str = Field(default="draft", pattern="^(draft|published)$")


class ItemUpdate(SQLModel):
    name: str | None = None
    status: str | None = Field(default=None, pattern="^(draft|published)$")


class ItemRead(SQLModel):
    id: int
    owner_id: int
    name: str
    status: str
    created_at: datetime
    updated_at: datetime


class ItemDescriptionCreate(SQLModel):
    locale: str = Field(min_length=2, max_length=10)
    content: str = Field(min_length=1)


class ItemDescriptionRead(SQLModel):
    id: int
    item_id: int
    locale: str
    content: str


class PaginatedItems(SQLModel):
    items: list[ItemRead]
    limit: int
    offset: int
    total: int


class OAuthAccountRead(SQLModel):
    provider: str
    email: str | None = None


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"
    refresh_token: str | None = None


class RegisterEmailRequest(SQLModel):
    email: EmailStr


class RegisterPasswordRequest(SQLModel):
    email: EmailStr
    password: str = Field(min_length=8)
    token: str


class LoginRequest(SQLModel):
    email: EmailStr
    password: str


class RegistrationToken(SQLModel):
    email: EmailStr
    token: str


class UserRead(SQLModel):
    id: int
    email: EmailStr
    is_active: bool
    role: str
    email_verified_at: datetime | None = None


class ProfileRead(SQLModel):
    display_name: str | None = None
    avatar_url: str | None = None
    bio: str | None = None
    locale: str
    timezone: str


class ProfileUpdate(SQLModel):
    display_name: str | None = None
    bio: str | None = None
    locale: str | None = None
    timezone: str | None = None


class UserMeRead(UserRead):
    profile: ProfileRead


class AdminUserRead(UserRead):
    pass


class RefreshRequest(SQLModel):
    refresh_token: str


class PasswordRequest(SQLModel):
    password: str = Field(min_length=8)


class TokenRequest(SQLModel):
    token: str


class OAuthLinkRequest(SQLModel):
    provider: str = Field(min_length=1, max_length=50)
    provider_user_id: str = Field(min_length=1, max_length=255)
    email: EmailStr | None = None


class SessionRead(SQLModel):
    id: str
    user_agent: str | None
    ip_address: str | None
    created_at: datetime
    expires_at: datetime

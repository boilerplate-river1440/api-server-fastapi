from datetime import datetime, timezone

from sqlmodel import Field, SQLModel, UniqueConstraint


class Item(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    description: str | None = None


class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    email: str = Field(unique=True, index=True)
    hashed_password: str | None = None
    is_active: bool = True


class OAuthAccount(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("provider", "provider_user_id"),)

    id: int | None = Field(default=None, primary_key=True)
    user_id: int = Field(foreign_key="user.id", index=True)
    provider: str
    provider_user_id: str
    email: str | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
from sqlmodel import SQLModel


class ItemCreate(SQLModel):
    name: str
    description: str | None = None


class ItemRead(SQLModel):
    id: int
    name: str
    description: str | None = None


class OAuthAccountRead(SQLModel):
    provider: str
    email: str | None = None


class Token(SQLModel):
    access_token: str
    token_type: str = "bearer"
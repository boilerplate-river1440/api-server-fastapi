from sqlmodel import SQLModel

from app.database import engine
from app.models import OAuthAccount, User  # noqa: F401


def reset_db() -> None:
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)


if __name__ == "__main__":
    reset_db()
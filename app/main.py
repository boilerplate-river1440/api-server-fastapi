from contextlib import asynccontextmanager

from fastapi import FastAPI
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .database import create_db_and_tables
from .routers import items, oauth as oauth_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret_key)
app.include_router(items.router)
app.include_router(oauth_router.router)


@app.get("/")
def read_root():
    return {"status": "success", "message": "Hit successful!"}

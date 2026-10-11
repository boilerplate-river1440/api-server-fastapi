from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware

from .config import settings
from .database import create_db_and_tables
from .middleware import RequestIDMiddleware
from .routers import auth, items, oauth as oauth_router, users


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield


app = FastAPI(lifespan=lifespan)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(SessionMiddleware, secret_key=settings.session_secret_key)
app.include_router(auth.router)
app.include_router(items.router)
app.include_router(users.router)
app.include_router(oauth_router.router)


def error_response(request: Request, message: str, code: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"error": {"code": code, "message": message}, "request_id": getattr(request.state, "request_id", None)},
    )


@app.exception_handler(RequestValidationError)
async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return error_response(request, "Request validation failed", "validation_error", 422)


@app.exception_handler(HTTPException)
async def http_error_handler(request: Request, exc: HTTPException) -> JSONResponse:
    return error_response(request, str(exc.detail), "http_error", exc.status_code)


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return error_response(request, "Internal server error", "internal_error", 500)


@app.get("/")
def read_root():
    return {"status": "success", "message": "Hit successful!"}


@app.get("/health", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ready", tags=["system"])
def ready() -> dict[str, str]:
    return {"status": "ready"}

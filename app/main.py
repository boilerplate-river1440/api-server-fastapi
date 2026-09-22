from fastapi import FastAPI

from .database import create_db_and_tables
from .routers import items

app = FastAPI()


@app.on_event("startup")
def on_startup():
    create_db_and_tables()


app.include_router(items.router)


@app.get("/")
def read_root():
    return {"status": "success", "message": "Hit successful!"}

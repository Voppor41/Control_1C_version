from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.core.database import dispose_engine, init_db


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    yield
    await dispose_engine()


app = FastAPI(lifespan=lifespan)

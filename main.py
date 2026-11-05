import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.router import api_router
from src.api.routers.health import router as health_router
from src.core.config import settings
from src.core.database import dispose_engine, init_db

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    await init_db()
    yield
    await dispose_engine()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    summary="1C configuration version control and update planning",
    description=(
        "MVP API for clients and 1C configurations, version checks, "
        "notifications, update scheduling, and department-head reports. "
        "GET /health checks the process and the database. Interactive docs: /docs."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(api_router)


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {"app": settings.app_name, "health": "/health", "docs": "/docs"}

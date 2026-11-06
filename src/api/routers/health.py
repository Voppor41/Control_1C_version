"""Проверка, что процесс жив, база отвечает, роли на месте и демо-пользователи созданы."""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import select, text

from src.core.config import settings
from src.core.database import async_session
from src.data.models import Role, User
from src.data.seed import DEMO_EMAILS

logger = logging.getLogger(__name__)

router = APIRouter(tags=["health"])

REQUIRED_ROLES = {"admin", "specialist", "manager", "client"}


async def database_reachable() -> bool:
    """SELECT 1. False, если соединение не удалось. Текст ошибки наружу не отдаётся."""
    try:
        async with async_session() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception:
        logger.exception("database health check failed")
        return False


@router.get("/health", summary="Liveness: API process and database")
@router.get("/api/health", include_in_schema=False)
async def health():
    """Живость: процесс и база. 503, если база не отвечает."""
    if not await database_reachable():
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "app": settings.app_name, "database": "down"},
        )
    return {"status": "ok", "app": settings.app_name, "database": "ok"}


@router.get("/health/ready", summary="Readiness: migrations, roles, demo accounts")
@router.get("/api/health/ready", include_in_schema=False)
async def ready():
    """Готовность: все четыре роли есть. demo_seeded говорит, созданы ли учебные учётки."""
    if not await database_reachable():
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "database": "down", "demo_seeded": False},
        )
    try:
        async with async_session() as session:
            codes = list((await session.scalars(select(Role.code))).all())
            present = set(
                (await session.scalars(select(User.email).where(User.email.in_(DEMO_EMAILS)))).all()
            )
    except Exception:
        logger.exception("readiness check failed")
        return JSONResponse(
            status_code=503,
            content={"status": "not_ready", "database": "down", "demo_seeded": False},
        )
    normalized = sorted({item.value if hasattr(item, "value") else str(item) for item in codes})
    missing = sorted(REQUIRED_ROLES - set(normalized))
    body = {
        "status": "ok" if not missing else "not_ready",
        "database": "ok",
        "roles": normalized,
        "missing_roles": missing,
        "demo_seeded": set(DEMO_EMAILS) <= present,
    }
    if missing:
        return JSONResponse(status_code=503, content=body)
    return body

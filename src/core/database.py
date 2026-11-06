"""Асинхронный движок SQLAlchemy и сессия запроса. При старте проверяет БД и наполняет справочники."""

import logging
from typing import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Базовый класс моделей. metadata отсюда забирает Alembic."""
    pass


engine = create_async_engine(
    settings.database_url,
    pool_size=settings.database_pool_size,
    echo=settings.debug,
    connect_args={"ssl": False},
)

async_session = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Сессия одного запроса. При ошибке откатывает транзакцию и пробрасывает исключение дальше."""
    async with async_session() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Проверяет соединение и наполняет роли. Демо-данные — только если should_seed_demo.

    Исключения:
        RuntimeError, если база недоступна или таблицы ещё не созданы миграцией.
    """
    from src.core.config import settings
    from src.data.seed import seed_demo_data, seed_initial_data

    try:
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception as exc:
        raise RuntimeError(
            "Database is unreachable. Check DATABASE_URL and that Postgres is running."
        ) from exc

    async with async_session() as session:
        try:
            await seed_initial_data(session)
            if settings.should_seed_demo:
                await seed_demo_data(session)
        except Exception as exc:
            logger.exception("seed failed")
            raise RuntimeError(
                "Failed to seed data. Apply migrations first: alembic upgrade head"
            ) from exc


async def dispose_engine() -> None:
    """Закрывает пул соединений при остановке процесса."""
    await engine.dispose()

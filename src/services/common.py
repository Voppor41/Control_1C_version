"""Общие операции сессии, поиск по подстроке и проверка, что клиент видит только свою организацию."""

import uuid

from fastapi import HTTPException
from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models import Role, RoleCode, User


def like_pattern(value: str) -> str:
    """Подстрока для ILIKE. Экранирует % и _, чтобы поиск был буквальным."""
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


async def count_rows(session: AsyncSession, stmt: Select) -> int:
    """Число строк запроса без limit и order by.

    Возвращает:
        Целое количество.
    """
    total = await session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    return int(total or 0)


async def commit_session(session: AsyncSession) -> None:
    """Фиксирует транзакцию. Нарушение уникальности превращает в ответ 409."""
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Data conflict") from exc


async def flush_session(session: AsyncSession) -> None:
    """Отправляет INSERT/UPDATE, не закрывая транзакцию. Конфликт тоже даёт 409."""
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Data conflict") from exc


def remember_actor(user: User) -> User:
    """Запоминает роль и client_id на объекте пользователя.

    Позже selectinload того же User (автор заявки) может сбросить связь role.
    Чтение роли тогда пошло бы ленивым запросом вне greenlet.

    Возвращает:
        Того же пользователя.
    """

    user.__dict__["_role_code"] = user.role.code
    user.__dict__["_client_id"] = user.client_id
    return user


def actor_role(user: User) -> RoleCode:
    """Код роли из кэша remember_actor либо из загруженной связи."""
    cached = user.__dict__.get("_role_code")
    if cached is not None:
        return cached
    return user.role.code


def actor_client_id(user: User) -> uuid.UUID | None:
    """Организация пользователя-клиента. У сотрудника возвращает None."""
    if "_client_id" in user.__dict__:
        return user.__dict__["_client_id"]
    return user.client_id


def ensure_client_scope(user: User, client_id: uuid.UUID) -> None:
    """Клиенту нельзя открыть чужую организацию. Остальные роли не ограничиваются."""
    if actor_role(user) == RoleCode.CLIENT and actor_client_id(user) != client_id:
        raise HTTPException(status_code=403, detail="You can only access your own client data")


async def get_role(session: AsyncSession, code: RoleCode) -> Role:
    """Справочная роль по коду.

    Исключения:
        500, если роли нет в базе: миграция или наполнение не выполнены.
    """
    role = await session.scalar(select(Role).where(Role.code == code))
    if role is None:
        raise HTTPException(status_code=500, detail=f"Role {code.value} is not configured")
    return role

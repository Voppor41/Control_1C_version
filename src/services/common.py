"""Общие операции сессии, поиск по подстроке и проверка, что клиент видит только свою организацию."""

import uuid

from fastapi import HTTPException
from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models import Account, ClientUser, Employee, Role, RoleCode


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


def remember_actor(person: Account) -> Account:
    """Запоминает код доступа и client_id на объекте человека.

    Позже selectinload той же строки (автор заявки) может сбросить связь role.
    Чтение роли тогда пошло бы ленивым запросом вне greenlet.
    У сотрудника роль берётся из справочника должностей, у пользователя компании это всегда client.

    Возвращает:
        Того же человека.
    """

    if isinstance(person, Employee):
        person.__dict__["_role_code"] = person.role.code
        person.__dict__["_client_id"] = None
    elif isinstance(person, ClientUser):
        person.__dict__["_role_code"] = RoleCode.CLIENT
        person.__dict__["_client_id"] = person.client_id
    else:
        raise TypeError("Actor must be an employee or a company user")
    return person


def actor_role(person: Account) -> RoleCode:
    """Код доступа из кэша remember_actor либо из загруженной должности."""
    cached = person.__dict__.get("_role_code")
    if cached is not None:
        return cached
    if isinstance(person, ClientUser):
        return RoleCode.CLIENT
    return person.role.code


def actor_client_id(person: Account) -> uuid.UUID | None:
    """Организация пользователя компании. У сотрудника возвращает None."""
    if "_client_id" in person.__dict__:
        return person.__dict__["_client_id"]
    if isinstance(person, ClientUser):
        return person.client_id
    return None


def ensure_client_scope(person: Account, client_id: uuid.UUID) -> None:
    """Пользователю компании нельзя открыть чужую организацию. Сотрудники не ограничиваются."""
    if actor_role(person) == RoleCode.CLIENT and actor_client_id(person) != client_id:
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

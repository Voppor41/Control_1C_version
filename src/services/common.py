import uuid

from fastapi import HTTPException
from sqlalchemy import Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models import Role, RoleCode, User


def like_pattern(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


async def count_rows(session: AsyncSession, stmt: Select) -> int:
    total = await session.scalar(select(func.count()).select_from(stmt.order_by(None).subquery()))
    return int(total or 0)


async def commit_session(session: AsyncSession) -> None:
    try:
        await session.commit()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Data conflict") from exc


async def flush_session(session: AsyncSession) -> None:
    try:
        await session.flush()
    except IntegrityError as exc:
        await session.rollback()
        raise HTTPException(status_code=409, detail="Data conflict") from exc


def remember_actor(user: User) -> User:
    """Keep role and client id available after later queries reload this user."""

    user.__dict__["_role_code"] = user.role.code
    user.__dict__["_client_id"] = user.client_id
    return user


def actor_role(user: User) -> RoleCode:
    cached = user.__dict__.get("_role_code")
    if cached is not None:
        return cached
    return user.role.code


def actor_client_id(user: User) -> uuid.UUID | None:
    if "_client_id" in user.__dict__:
        return user.__dict__["_client_id"]
    return user.client_id


def ensure_client_scope(user: User, client_id: uuid.UUID) -> None:
    if actor_role(user) == RoleCode.CLIENT and actor_client_id(user) != client_id:
        raise HTTPException(status_code=403, detail="You can only access your own client data")


async def get_role(session: AsyncSession, code: RoleCode) -> Role:
    role = await session.scalar(select(Role).where(Role.code == code))
    if role is None:
        raise HTTPException(status_code=500, detail=f"Role {code.value} is not configured")
    return role

"""Поиск сотрудников и пользователей компании. Общей таблицы users больше нет."""

import logging
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.data.models import Account, ClientUser, Employee

logger = logging.getLogger(__name__)

EMPLOYEE_PRINCIPAL = "employee"
CLIENT_USER_PRINCIPAL = "client_user"


def principal_kind(person: Account) -> str:
    """Метка JWT: в какой таблице лежит id."""
    if isinstance(person, Employee):
        return EMPLOYEE_PRINCIPAL
    return CLIENT_USER_PRINCIPAL


def author_ids(person: Account) -> tuple[UUID | None, UUID | None]:
    """Пара (id сотрудника, id пользователя компании). Заполнен ровно один."""
    if isinstance(person, ClientUser):
        return None, person.id
    return person.id, None


async def find_by_email(session: AsyncSession, email: str) -> Account | None:
    """Ищет почту в обеих таблицах. Две строки с одной почтой считаются ошибкой данных и не пускают внутрь."""
    employee = await session.scalar(
        select(Employee).where(Employee.email == email).options(selectinload(Employee.role))
    )
    client_user = await session.scalar(
        select(ClientUser).where(ClientUser.email == email).options(selectinload(ClientUser.client))
    )
    if employee is not None and client_user is not None:
        logger.error("login email is stored in both employees and client_users")
        return None
    return employee or client_user


async def assert_email_available(session: AsyncSession, email: str) -> None:
    """Почта свободна и у сотрудников, и у пользователей компании. Иначе 409."""
    taken = await session.scalar(select(Employee.id).where(Employee.email == email))
    if taken is None:
        taken = await session.scalar(select(ClientUser.id).where(ClientUser.email == email))
    if taken is not None:
        raise HTTPException(status_code=409, detail="User with this email already exists")


async def get_account(session: AsyncSession, person_id: UUID) -> Account:
    """Карточка по id из любой таблицы людей. 404, если такого id нет."""
    employee = await session.scalar(
        select(Employee).where(Employee.id == person_id).options(selectinload(Employee.role))
    )
    client_user = await session.scalar(
        select(ClientUser).where(ClientUser.id == person_id).options(selectinload(ClientUser.client))
    )
    if employee is not None and client_user is not None:
        raise HTTPException(status_code=409, detail="Data conflict")
    if employee is not None:
        return employee
    if client_user is not None:
        return client_user
    raise HTTPException(status_code=404, detail="User not found")


async def get_principal(session: AsyncSession, *, principal: str, person_id: UUID) -> Account | None:
    """Человек из той таблицы, которую назвал токен. Чужая таблица не подставляется."""
    if principal == EMPLOYEE_PRINCIPAL:
        return await session.scalar(
            select(Employee).where(Employee.id == person_id).options(selectinload(Employee.role))
        )
    if principal == CLIENT_USER_PRINCIPAL:
        return await session.scalar(
            select(ClientUser)
            .where(ClientUser.id == person_id)
            .options(selectinload(ClientUser.client))
        )
    return None

"""Зависимости FastAPI: текущий человек, проверка роли и параметры страницы."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.core.security import TokenError, decode_access_token
from src.data.models import Account, RoleCode
from src.services.accounts import CLIENT_USER_PRINCIPAL, EMPLOYEE_PRINCIPAL, get_principal
from src.services.common import actor_role, remember_actor

bearer = HTTPBearer(auto_error=False)


class PageParams:
    """limit и offset списка."""

    def __init__(self, limit: int, offset: int) -> None:
        self.limit = limit
        self.offset = offset


def get_page(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> PageParams:
    """Разбирает query-параметры страницы. limit не больше 200."""
    return PageParams(limit, offset)


PageDep = Annotated[PageParams, Depends(get_page)]
Db = Annotated[AsyncSession, Depends(get_db)]


async def get_current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: Db,
) -> Account:
    """Человек из Bearer-токена. principal говорит, employees это или client_users.

    Неактивный, неизвестный и токен без таблицы получают 401.
    """
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_access_token(creds.credentials)
        user_id = UUID(str(payload.get("sub")))
        principal = payload.get("principal")
    except (TokenError, ValueError, TypeError):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if principal not in (EMPLOYEE_PRINCIPAL, CLIENT_USER_PRINCIPAL):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    person = await get_principal(session, principal=str(principal), person_id=user_id)
    if person is None or not person.is_active:
        raise HTTPException(
            status_code=401,
            detail="Inactive or unknown user",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return remember_actor(person)


def require(*roles: RoleCode):
    """Зависимость, которая пускает только перечисленные роли. Иначе 403.

    Администратор и специалист меняют данные, руководитель читает отчёты,
    пользователь компании ограничен своей организацией на уровне конкретных маршрутов.
    """

    async def checker(user: Account = Depends(get_current_user)) -> Account:
        if actor_role(user) not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return checker


CurrentUser = Annotated[Account, Depends(get_current_user)]
AdminUser = Annotated[Account, Depends(require(RoleCode.ADMIN))]
StaffUser = Annotated[Account, Depends(require(RoleCode.ADMIN, RoleCode.SPECIALIST, RoleCode.MANAGER))]
WriterUser = Annotated[Account, Depends(require(RoleCode.ADMIN, RoleCode.SPECIALIST))]
ReportUser = Annotated[Account, Depends(require(RoleCode.ADMIN, RoleCode.MANAGER))]

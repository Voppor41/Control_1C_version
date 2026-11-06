"""Зависимости FastAPI: текущий пользователь, проверка роли и параметры страницы."""

from typing import Annotated
from uuid import UUID

from fastapi import Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.core.database import get_db
from src.core.security import TokenError, decode_access_token
from src.data.models import RoleCode, User
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
) -> User:
    """Пользователь из Bearer-токена. Неактивный и неизвестный получают 401."""
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(
            status_code=401,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = decode_access_token(creds.credentials)
        user_id = UUID(str(payload.get("sub")))
    except (TokenError, ValueError, TypeError):
        raise HTTPException(
            status_code=401,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = await session.scalar(
        select(User)
        .where(User.id == user_id)
        .options(selectinload(User.role), selectinload(User.client))
    )
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=401,
            detail="Inactive or unknown user",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return remember_actor(user)


def require(*roles: RoleCode):
    """Зависимость, которая пускает только перечисленные роли. Иначе 403.

    Администратор и специалист меняют данные, руководитель читает отчёты,
    клиент ограничен своей организацией на уровне конкретных маршрутов.
    """
    async def checker(user: User = Depends(get_current_user)) -> User:
        if actor_role(user) not in roles:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        return user

    return checker


CurrentUser = Annotated[User, Depends(get_current_user)]
AdminUser = Annotated[User, Depends(require(RoleCode.ADMIN))]
StaffUser = Annotated[User, Depends(require(RoleCode.ADMIN, RoleCode.SPECIALIST, RoleCode.MANAGER))]
WriterUser = Annotated[User, Depends(require(RoleCode.ADMIN, RoleCode.SPECIALIST))]
ReportUser = Annotated[User, Depends(require(RoleCode.ADMIN, RoleCode.MANAGER))]

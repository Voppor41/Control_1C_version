"""Вход по почте и паролю и карточка текущего пользователя."""

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from src.api.deps import CurrentUser, Db
from src.api.schemas import LoginRequest, TokenResponse
from src.api.serializers import user_read
from src.core.config import settings
from src.core.security import create_access_token, verify_password
from src.data.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse, summary="Sign in and receive a bearer token")
async def login(payload: LoginRequest, session: Db) -> TokenResponse:
    """Сверяет пароль и отдаёт токен. Неверный пароль — 401, отключённый пользователь — 403."""
    user = await session.scalar(
        select(User)
        .where(User.email == payload.email)
        .options(selectinload(User.role), selectinload(User.client))
    )
    if user is None or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not user.is_active:
        raise HTTPException(status_code=403, detail="User is deactivated")
    token = create_access_token(user_id=user.id, role=user.role.code.value)
    return TokenResponse(
        access_token=token,
        expires_in=settings.access_token_expire_minutes * 60,
        role=user.role.code,
        user=user_read(user),
    )


@router.get("/me", summary="Current user")
async def me(user: CurrentUser):
    """Карточка владельца токена."""
    return user_read(user)

"""Вход по почте и паролю и карточка текущего человека."""

from fastapi import APIRouter, HTTPException

from src.api.deps import CurrentUser, Db
from src.api.schemas import LoginRequest, TokenResponse
from src.api.serializers import user_read
from src.core.config import settings
from src.core.security import create_access_token, verify_password
from src.data.models import ClientUser, Employee, RoleCode
from src.services.accounts import find_by_email, principal_kind

router = APIRouter(prefix="/auth", tags=["auth"])


def _access_code(person: Employee | ClientUser) -> RoleCode:
    """Должность сотрудника или client у пользователя компании."""
    if isinstance(person, Employee):
        return person.role.code
    return RoleCode.CLIENT


@router.post("/login", response_model=TokenResponse, summary="Sign in and receive a bearer token")
async def login(payload: LoginRequest, session: Db) -> TokenResponse:
    """Сверяет пароль в employees и в client_users. Неверный пароль — 401, отключённый человек — 403."""
    person = await find_by_email(session, payload.email)
    if person is None or not verify_password(payload.password, person.hashed_password):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    if not person.is_active:
        raise HTTPException(status_code=403, detail="User is deactivated")
    role = _access_code(person)
    token = create_access_token(
        user_id=person.id,
        role=role.value,
        principal=principal_kind(person),
    )
    return TokenResponse(
        access_token=token,
        expires_in=settings.access_token_expire_minutes * 60,
        role=role,
        user=user_read(person),
    )


@router.get("/me", summary="Current user")
async def me(user: CurrentUser):
    """Карточка владельца токена."""
    return user_read(user)

"""Хеш пароля и выпуск JWT. В токене лежат идентификатор, код роли и таблица человека."""

from datetime import datetime, timedelta, timezone
from uuid import UUID

import bcrypt
import jwt

from src.core.config import settings


class TokenError(Exception):
    """Токен не разобран или просрочен."""
    pass


def hash_password(password: str) -> str:
    """Возвращает bcrypt-хеш. В ответе API пароль не отдаётся."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(password: str, hashed: str) -> bool:
    """Сравнивает пароль с хешем. При битом хеше возвращает False, а не исключение."""
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def create_access_token(*, user_id: UUID, role: str, principal: str) -> str:
    """Собирает JWT.

    Параметры:
        user_id: чей это токен.
        role: код доступа (admin, specialist, manager или client).
        principal: таблица id — employee или client_user. Без неё один UUID не отличить.

    Возвращает:
        Подписанную строку токена.
    """
    expires = datetime.now(timezone.utc) + timedelta(minutes=settings.access_token_expire_minutes)
    payload = {"sub": str(user_id), "role": role, "principal": principal, "exp": expires}
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Проверяет подпись и срок.

    Возвращает:
        Полезную нагрузку с полями sub, role и principal.

    Исключения:
        TokenError, если токен недействителен.
    """
    try:
        return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.PyJWTError as exc:
        raise TokenError("Invalid or expired token") from exc

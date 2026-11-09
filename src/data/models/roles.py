"""Должности сотрудников сопровождения. Код совпадает с RoleCode и не меняется из API.

Пользователь компании должность не получает: его нет в этой таблице.
Код client остаётся только в ответах API и в JWT, отдельной строки roles для него нет.
"""

import uuid
from typing import TYPE_CHECKING

from sqlalchemy import String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base

from .enums import RoleCode, persisted_enum
from .mixins import TimestampMixin

if TYPE_CHECKING:
    from .employees import Employee


class Role(TimestampMixin, Base):
    """Строка справочника должностей. Сотрудники ссылаются на неё, а не хранят код строкой."""

    __tablename__ = "roles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    code: Mapped[RoleCode] = mapped_column(
        persisted_enum(RoleCode, "role_code"),
        unique=True,
        index=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)

    employees: Mapped[list["Employee"]] = relationship(back_populates="role")

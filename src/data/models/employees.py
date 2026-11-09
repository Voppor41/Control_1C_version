"""Сотрудник службы сопровождения. Пользователи компании сюда не входят."""

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base

from .mixins import TimestampMixin

if TYPE_CHECKING:
    from .clients import Client
    from .notifications import Notification
    from .roles import Role
    from .scheduled_updates import ScheduledUpdate, UpdateStatusHistory
    from .update_slots import UpdateSlot
    from .version_checks import VersionCheck


class Employee(TimestampMixin, Base):
    """Учётка сотрудника: должность из roles, пароль и контакты.

    Почта уникальна здесь и не должна совпадать с почтой client_users
    (это проверяет триггер login_email_not_shared и регистрация в API).
    """

    __tablename__ = "employees"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(32))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    role_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("roles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    role: Mapped["Role"] = relationship(back_populates="employees")
    assigned_clients: Mapped[list["Client"]] = relationship(
        back_populates="responsible_employee",
        foreign_keys="Client.responsible_employee_id",
    )
    version_checks: Mapped[list["VersionCheck"]] = relationship(back_populates="checked_by")
    created_notifications: Mapped[list["Notification"]] = relationship(
        back_populates="created_by_employee",
        foreign_keys="Notification.created_by_employee_id",
    )
    update_slots: Mapped[list["UpdateSlot"]] = relationship(back_populates="specialist")
    requested_updates: Mapped[list["ScheduledUpdate"]] = relationship(
        back_populates="requested_by_employee",
        foreign_keys="ScheduledUpdate.requested_by_employee_id",
    )
    assigned_updates: Mapped[list["ScheduledUpdate"]] = relationship(
        back_populates="assigned_specialist",
        foreign_keys="ScheduledUpdate.assigned_specialist_id",
    )
    status_changes: Mapped[list["UpdateStatusHistory"]] = relationship(
        back_populates="changed_by_employee",
        foreign_keys="UpdateStatusHistory.changed_by_employee_id",
    )

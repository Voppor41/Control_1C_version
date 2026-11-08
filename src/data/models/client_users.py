"""Пользователь компании: входит в портал клиента и всегда привязан к организации."""

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
    from .scheduled_updates import ScheduledUpdate, UpdateStatusHistory


class ClientUser(TimestampMixin, Base):
    """Учётка со стороны клиента. Должности сотрудника у неё нет: организация задаётся client_id.

    Почта уникальна здесь и не должна совпадать с почтой employees.
    """

    __tablename__ = "client_users"

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
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    client: Mapped["Client"] = relationship(
        back_populates="company_users",
        foreign_keys=[client_id],
    )
    received_notifications: Mapped[list["Notification"]] = relationship(
        back_populates="recipient",
        foreign_keys="Notification.recipient_id",
    )
    created_notifications: Mapped[list["Notification"]] = relationship(
        back_populates="created_by_client_user",
        foreign_keys="Notification.created_by_client_user_id",
    )
    requested_updates: Mapped[list["ScheduledUpdate"]] = relationship(
        back_populates="requested_by_client_user",
        foreign_keys="ScheduledUpdate.requested_by_client_user_id",
    )
    status_changes: Mapped[list["UpdateStatusHistory"]] = relationship(
        back_populates="changed_by_client_user",
        foreign_keys="UpdateStatusHistory.changed_by_client_user_id",
    )

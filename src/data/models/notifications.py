"""Сообщение пользователю компании. Автор может быть сотрудником или этим же пользователем."""

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base

from .enums import NotificationType, persisted_enum
from .mixins import TimestampMixin

if TYPE_CHECKING:
    from .client_configurations import ClientConfiguration
    from .client_users import ClientUser
    from .clients import Client
    from .employees import Employee
    from .scheduled_updates import ScheduledUpdate


class Notification(TimestampMixin, Base):
    """Одно сообщение одному пользователю компании.

    Получатель всегда из client_users. Автор — либо сотрудник, либо пользователь компании,
    либо никто (оба внешних ключа пустые). Оба автора сразу стоять не могут.
    """

    __tablename__ = "notifications"
    __table_args__ = (
        CheckConstraint(
            "(CASE WHEN created_by_employee_id IS NOT NULL THEN 1 ELSE 0 END"
            " + CASE WHEN created_by_client_user_id IS NOT NULL THEN 1 ELSE 0 END) <= 1",
            name="ck_notifications_one_author",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    type: Mapped[NotificationType] = mapped_column(
        persisted_enum(NotificationType, "notification_type"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    recipient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("client_users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_employee_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="SET NULL"),
        index=True,
    )
    created_by_client_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("client_users.id", ondelete="SET NULL"),
        index=True,
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_configuration_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("client_configurations.id", ondelete="SET NULL"),
    )
    scheduled_update_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scheduled_updates.id", ondelete="SET NULL"),
    )

    recipient: Mapped["ClientUser"] = relationship(
        back_populates="received_notifications",
        foreign_keys=[recipient_id],
    )
    created_by_employee: Mapped[Optional["Employee"]] = relationship(
        back_populates="created_notifications",
        foreign_keys=[created_by_employee_id],
    )
    created_by_client_user: Mapped[Optional["ClientUser"]] = relationship(
        back_populates="created_notifications",
        foreign_keys=[created_by_client_user_id],
    )
    client: Mapped["Client"] = relationship(back_populates="notifications")
    client_configuration: Mapped[Optional["ClientConfiguration"]] = relationship(
        back_populates="notifications",
    )
    scheduled_update: Mapped[Optional["ScheduledUpdate"]] = relationship(
        back_populates="notifications",
    )

    @property
    def created_by_id(self) -> uuid.UUID | None:
        """Идентификатор автора для ответа API: сотрудник, пользователь компании или никто."""
        return self.created_by_employee_id or self.created_by_client_user_id

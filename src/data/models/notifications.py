"""Сообщение конкретному пользователю клиента."""

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base

from .enums import NotificationType, persisted_enum
from .mixins import TimestampMixin

if TYPE_CHECKING:
    from .client_configurations import ClientConfiguration
    from .clients import Client
    from .scheduled_updates import ScheduledUpdate
    from .users import User


class Notification(TimestampMixin, Base):
    """Одно сообщение одному получателю. У клиента без портального пользователя строка не появится."""
    __tablename__ = "notifications"

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
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
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

    recipient: Mapped["User"] = relationship(
        back_populates="received_notifications",
        foreign_keys=[recipient_id],
    )
    created_by: Mapped[Optional["User"]] = relationship(
        back_populates="created_notifications",
        foreign_keys=[created_by_id],
    )
    client: Mapped["Client"] = relationship(back_populates="notifications")
    client_configuration: Mapped[Optional["ClientConfiguration"]] = relationship(
        back_populates="notifications",
    )
    scheduled_update: Mapped[Optional["ScheduledUpdate"]] = relationship(
        back_populates="notifications",
    )

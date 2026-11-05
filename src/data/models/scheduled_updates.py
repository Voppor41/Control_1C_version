import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base

from .enums import UpdateStatus
from .mixins import TimestampMixin

if TYPE_CHECKING:
    from .client_configurations import ClientConfiguration
    from .clients import Client
    from .notifications import Notification
    from .update_slots import UpdateSlot
    from .users import User


class ScheduledUpdate(TimestampMixin, Base):
    __tablename__ = "scheduled_updates"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    status: Mapped[UpdateStatus] = mapped_column(
        Enum(UpdateStatus, name="update_status", native_enum=False, length=32),
        default=UpdateStatus.REQUESTED,
        nullable=False,
        index=True,
    )
    comment: Mapped[Optional[str]] = mapped_column(Text)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    client_configuration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("client_configurations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    slot_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("update_slots.id", ondelete="SET NULL"),
        index=True,
    )
    requested_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )
    assigned_specialist_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )

    client: Mapped["Client"] = relationship(back_populates="scheduled_updates")
    client_configuration: Mapped["ClientConfiguration"] = relationship(
        back_populates="scheduled_updates",
    )
    slot: Mapped[Optional["UpdateSlot"]] = relationship(back_populates="scheduled_updates")
    requested_by: Mapped["User"] = relationship(
        back_populates="requested_updates",
        foreign_keys=[requested_by_id],
    )
    assigned_specialist: Mapped[Optional["User"]] = relationship(
        back_populates="assigned_updates",
        foreign_keys=[assigned_specialist_id],
    )
    status_history: Mapped[list["UpdateStatusHistory"]] = relationship(
        back_populates="scheduled_update",
        cascade="all, delete-orphan",
        order_by="UpdateStatusHistory.changed_at",
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="scheduled_update",
    )


class UpdateStatusHistory(Base):
    __tablename__ = "update_status_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    old_status: Mapped[Optional[UpdateStatus]] = mapped_column(
        Enum(UpdateStatus, name="update_status", native_enum=False, length=32),
    )
    new_status: Mapped[UpdateStatus] = mapped_column(
        Enum(UpdateStatus, name="update_status", native_enum=False, length=32),
        nullable=False,
    )
    comment: Mapped[Optional[str]] = mapped_column(Text)
    changed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    scheduled_update_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("scheduled_updates.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    changed_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
    )

    scheduled_update: Mapped["ScheduledUpdate"] = relationship(back_populates="status_history")
    changed_by: Mapped["User"] = relationship(back_populates="status_changes")

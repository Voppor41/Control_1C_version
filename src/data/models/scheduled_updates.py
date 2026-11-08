"""Заявка на обновление, выбранное окно и история смены статуса."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base

from .enums import UpdateStatus, persisted_enum
from .mixins import TimestampMixin

if TYPE_CHECKING:
    from .client_configurations import ClientConfiguration
    from .client_users import ClientUser
    from .clients import Client
    from .configurations import ConfigurationVersion
    from .employees import Employee
    from .notifications import Notification
    from .update_slots import UpdateSlot


class ScheduledUpdate(TimestampMixin, Base):
    """Заявка. source_version_id — что стояло при создании, target_version_id — на что обновляем.

    Запросить обновление может и пользователь компании, и сотрудник от её имени.
    Поэтому автор заявки — ровно один из двух внешних ключей, а не «голый» id без таблицы.
    Исполнитель (assigned_specialist_id) всегда сотрудник.
    """

    __tablename__ = "scheduled_updates"
    __table_args__ = (
        CheckConstraint(
            "(CASE WHEN requested_by_employee_id IS NOT NULL THEN 1 ELSE 0 END"
            " + CASE WHEN requested_by_client_user_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_scheduled_updates_one_requester",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    status: Mapped[UpdateStatus] = mapped_column(
        persisted_enum(UpdateStatus, "update_status"),
        default=UpdateStatus.REQUESTED,
        nullable=False,
        index=True,
    )
    comment: Mapped[Optional[str]] = mapped_column(Text)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), index=True)
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
    source_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("configuration_versions.id", ondelete="RESTRICT"),
        index=True,
    )
    target_version_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("configuration_versions.id", ondelete="RESTRICT"),
        index=True,
    )
    slot_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("update_slots.id", ondelete="SET NULL"),
        index=True,
    )
    requested_by_employee_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        index=True,
    )
    requested_by_client_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("client_users.id", ondelete="RESTRICT"),
        index=True,
    )
    assigned_specialist_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="SET NULL"),
        index=True,
    )

    client: Mapped["Client"] = relationship(back_populates="scheduled_updates")
    client_configuration: Mapped["ClientConfiguration"] = relationship(
        back_populates="scheduled_updates",
    )
    source_version: Mapped[Optional["ConfigurationVersion"]] = relationship(
        foreign_keys=[source_version_id],
    )
    target_version: Mapped[Optional["ConfigurationVersion"]] = relationship(
        foreign_keys=[target_version_id],
    )
    slot: Mapped[Optional["UpdateSlot"]] = relationship(back_populates="scheduled_updates")
    requested_by_employee: Mapped[Optional["Employee"]] = relationship(
        back_populates="requested_updates",
        foreign_keys=[requested_by_employee_id],
    )
    requested_by_client_user: Mapped[Optional["ClientUser"]] = relationship(
        back_populates="requested_updates",
        foreign_keys=[requested_by_client_user_id],
    )
    assigned_specialist: Mapped[Optional["Employee"]] = relationship(
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

    @property
    def requested_by_id(self) -> uuid.UUID:
        """Кто запросил заявку: id сотрудника или пользователя компании."""
        value = self.requested_by_employee_id or self.requested_by_client_user_id
        if value is None:
            raise RuntimeError("scheduled update has no requester")
        return value

    @property
    def requested_by(self) -> "Employee | ClientUser":
        """Загруженный автор заявки. Связь requested_by_employee или requested_by_client_user уже должна быть в сессии."""
        person = self.requested_by_employee or self.requested_by_client_user
        if person is None:
            raise RuntimeError("scheduled update requester is not loaded")
        return person


class UpdateStatusHistory(Base):
    """Кто и когда сменил статус. Старые строки не редактируются.

    Дату может выбрать и пользователь компании, и сотрудник, поэтому автор смены —
    ровно один из двух внешних ключей.
    """

    __tablename__ = "update_status_history"
    __table_args__ = (
        CheckConstraint(
            "(CASE WHEN changed_by_employee_id IS NOT NULL THEN 1 ELSE 0 END"
            " + CASE WHEN changed_by_client_user_id IS NOT NULL THEN 1 ELSE 0 END) = 1",
            name="ck_update_status_history_one_changer",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    old_status: Mapped[Optional[UpdateStatus]] = mapped_column(
        persisted_enum(UpdateStatus, "update_status"),
    )
    new_status: Mapped[UpdateStatus] = mapped_column(
        persisted_enum(UpdateStatus, "update_status"),
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
    changed_by_employee_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        index=True,
    )
    changed_by_client_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("client_users.id", ondelete="RESTRICT"),
        index=True,
    )

    scheduled_update: Mapped["ScheduledUpdate"] = relationship(back_populates="status_history")
    changed_by_employee: Mapped[Optional["Employee"]] = relationship(
        back_populates="status_changes",
        foreign_keys=[changed_by_employee_id],
    )
    changed_by_client_user: Mapped[Optional["ClientUser"]] = relationship(
        back_populates="status_changes",
        foreign_keys=[changed_by_client_user_id],
    )

    @property
    def changed_by_id(self) -> uuid.UUID:
        """Кто сменил статус: id сотрудника или пользователя компании."""
        value = self.changed_by_employee_id or self.changed_by_client_user_id
        if value is None:
            raise RuntimeError("status change has no author")
        return value

    @property
    def changed_by(self) -> "Employee | ClientUser":
        """Загруженный автор смены статуса."""
        person = self.changed_by_employee or self.changed_by_client_user
        if person is None:
            raise RuntimeError("status change author is not loaded")
        return person

"""Организация-клиент и сотрудник, который её ведёт."""

import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base

from .mixins import TimestampMixin

if TYPE_CHECKING:
    from .client_configurations import ClientConfiguration
    from .client_users import ClientUser
    from .employees import Employee
    from .notifications import Notification
    from .scheduled_updates import ScheduledUpdate


class Client(TimestampMixin, Base):
    """Организация. responsible_employee_id — сотрудник сопровождения, который её ведёт."""

    __tablename__ = "clients"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    company_name: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        index=True,
    )
    phone: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    responsible_employee_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="SET NULL"),
        index=True,
    )

    responsible_employee: Mapped[Optional["Employee"]] = relationship(
        back_populates="assigned_clients",
        foreign_keys=[responsible_employee_id],
    )
    company_users: Mapped[list["ClientUser"]] = relationship(
        back_populates="client",
        foreign_keys="ClientUser.client_id",
    )
    configurations: Mapped[list["ClientConfiguration"]] = relationship(
        back_populates="client",
        cascade="all, delete-orphan",
    )
    notifications: Mapped[list["Notification"]] = relationship(back_populates="client")
    scheduled_updates: Mapped[list["ScheduledUpdate"]] = relationship(back_populates="client")

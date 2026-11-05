import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base

from .mixins import TimestampMixin

if TYPE_CHECKING:
    from .client_configurations import ClientConfiguration
    from .notifications import Notification
    from .scheduled_updates import ScheduledUpdate
    from .users import User


class Client(TimestampMixin, Base):
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
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )

    responsible_employee: Mapped[Optional["User"]] = relationship(
        back_populates="assigned_clients",
        foreign_keys=[responsible_employee_id],
    )
    portal_users: Mapped[list["User"]] = relationship(
        back_populates="client",
        foreign_keys="User.client_id",
    )
    configurations: Mapped[list["ClientConfiguration"]] = relationship(
        back_populates="client",
        cascade="all, delete-orphan",
    )
    notifications: Mapped[list["Notification"]] = relationship(back_populates="client")
    scheduled_updates: Mapped[list["ScheduledUpdate"]] = relationship(back_populates="client")

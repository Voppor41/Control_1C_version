import uuid
from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base

from .mixins import TimestampMixin

if TYPE_CHECKING:
    from .clients import Client
    from .configurations import Configuration, ConfigurationVersion
    from .notifications import Notification
    from .scheduled_updates import ScheduledUpdate
    from .version_checks import VersionCheck


class ClientConfiguration(TimestampMixin, Base):
    __tablename__ = "client_configurations"
    __table_args__ = (
        UniqueConstraint(
            "client_id",
            "configuration_id",
            name="uq_client_configuration",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    client_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("clients.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    configuration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("configurations.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    installed_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("configuration_versions.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    infobase_name: Mapped[Optional[str]] = mapped_column(String(255))

    client: Mapped["Client"] = relationship(back_populates="configurations")
    configuration: Mapped["Configuration"] = relationship(back_populates="client_installations")
    installed_version: Mapped["ConfigurationVersion"] = relationship(
        back_populates="installations",
        foreign_keys=[installed_version_id],
    )
    checks: Mapped[list["VersionCheck"]] = relationship(
        back_populates="client_configuration",
        cascade="all, delete-orphan",
    )
    notifications: Mapped[list["Notification"]] = relationship(
        back_populates="client_configuration",
    )
    scheduled_updates: Mapped[list["ScheduledUpdate"]] = relationship(
        back_populates="client_configuration",
    )

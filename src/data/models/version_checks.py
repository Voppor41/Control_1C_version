"""Снимок сравнения: что было установлено, что было актуальным и устарело ли."""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base

if TYPE_CHECKING:
    from .client_configurations import ClientConfiguration
    from .configurations import ConfigurationVersion
    from .employees import Employee


class VersionCheck(Base):
    """История сравнения. Строка не переписывается: новый запуск проверки добавляет ещё одну."""

    __tablename__ = "version_checks"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    client_configuration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("client_configurations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    installed_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("configuration_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    actual_version_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("configuration_versions.id", ondelete="RESTRICT"),
        nullable=False,
    )
    is_outdated: Mapped[bool] = mapped_column(Boolean, nullable=False, index=True)
    checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
        index=True,
    )
    checked_by_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("employees.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )

    client_configuration: Mapped["ClientConfiguration"] = relationship(back_populates="checks")
    installed_version: Mapped["ConfigurationVersion"] = relationship(
        foreign_keys=[installed_version_id],
    )
    actual_version: Mapped["ConfigurationVersion"] = relationship(
        foreign_keys=[actual_version_id],
    )
    checked_by: Mapped["Employee"] = relationship(back_populates="version_checks")

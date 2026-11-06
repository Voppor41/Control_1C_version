"""Каталог конфигураций 1С и выпуски. Признак is_current единственный на конфигурацию."""

import uuid
from datetime import date
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Date, ForeignKey, Index, String, Text, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.database import Base

from .mixins import TimestampMixin

if TYPE_CHECKING:
    from .client_configurations import ClientConfiguration


class Configuration(TimestampMixin, Base):
    """Типовая конфигурация 1С, например «Бухгалтерия предприятия»."""
    __tablename__ = "configurations"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    name: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)

    versions: Mapped[list["ConfigurationVersion"]] = relationship(
        back_populates="configuration",
        cascade="all, delete-orphan",
        order_by="ConfigurationVersion.released_at.desc()",
    )
    client_installations: Mapped[list["ClientConfiguration"]] = relationship(
        back_populates="configuration",
    )


class ConfigurationVersion(TimestampMixin, Base):
    """Конкретный релиз. Частичный уникальный индекс не даёт двум is_current на одну конфигурацию."""
    __tablename__ = "configuration_versions"
    __table_args__ = (
        UniqueConstraint("configuration_id", "version", name="uq_configuration_version"),
        Index(
            "uq_configuration_versions_current",
            "configuration_id",
            unique=True,
            postgresql_where=text("is_current IS TRUE"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    configuration_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("configurations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    version: Mapped[str] = mapped_column(String(64), nullable=False)
    released_at: Mapped[Optional[date]] = mapped_column(Date)
    is_current: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text)

    configuration: Mapped["Configuration"] = relationship(back_populates="versions")
    installations: Mapped[list["ClientConfiguration"]] = relationship(
        back_populates="installed_version",
        foreign_keys="ClientConfiguration.installed_version_id",
    )

"""Добавляет к заявке исходную и целевую версии, чтобы отчёт показывал, с какого релиза на какой перешли.

Revision ID: 20261105_0002
Revises: 20261102_0001
Create Date: 2026-11-05
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20261105_0002"
down_revision: Union[str, Sequence[str], None] = "20261102_0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

uuid_pk = postgresql.UUID(as_uuid=True)


def _column_names(inspector: sa.Inspector, table: str) -> set[str]:
    return {column["name"] for column in inspector.get_columns(table)}


def _fk_names(inspector: sa.Inspector, table: str) -> set[str]:
    return {fk["name"] for fk in inspector.get_foreign_keys(table) if fk.get("name")}


def _index_names(inspector: sa.Inspector, table: str) -> set[str]:
    return {index["name"] for index in inspector.get_indexes(table) if index.get("name")}


def upgrade() -> None:
    """Колонки source_version_id и target_version_id и индекс по completed_at.

    Старая локальная БД могла уже содержать часть этих объектов
    (например target_version_id), поэтому добавляем только то, чего нет.
    """
    inspector = sa.inspect(op.get_bind())
    columns = _column_names(inspector, "scheduled_updates")
    foreign_keys = _fk_names(inspector, "scheduled_updates")
    indexes = _index_names(inspector, "scheduled_updates")

    if "source_version_id" not in columns:
        op.add_column(
            "scheduled_updates",
            sa.Column("source_version_id", uuid_pk, nullable=True),
        )
    if "target_version_id" not in columns:
        op.add_column(
            "scheduled_updates",
            sa.Column("target_version_id", uuid_pk, nullable=True),
        )
    if "fk_scheduled_updates_source_version_id" not in foreign_keys:
        op.create_foreign_key(
            "fk_scheduled_updates_source_version_id",
            "scheduled_updates",
            "configuration_versions",
            ["source_version_id"],
            ["id"],
            ondelete="RESTRICT",
        )
    if "fk_scheduled_updates_target_version_id" not in foreign_keys:
        op.create_foreign_key(
            "fk_scheduled_updates_target_version_id",
            "scheduled_updates",
            "configuration_versions",
            ["target_version_id"],
            ["id"],
            ondelete="RESTRICT",
        )
    if "ix_scheduled_updates_source_version_id" not in indexes:
        op.create_index(
            op.f("ix_scheduled_updates_source_version_id"),
            "scheduled_updates",
            ["source_version_id"],
            unique=False,
        )
    if "ix_scheduled_updates_target_version_id" not in indexes:
        op.create_index(
            op.f("ix_scheduled_updates_target_version_id"),
            "scheduled_updates",
            ["target_version_id"],
            unique=False,
        )
    if "ix_scheduled_updates_completed_at" not in indexes:
        op.create_index(
            "ix_scheduled_updates_completed_at",
            "scheduled_updates",
            ["completed_at"],
            unique=False,
        )


def downgrade() -> None:
    """Убирает эти колонки и индекс, если они ещё есть."""
    inspector = sa.inspect(op.get_bind())
    columns = _column_names(inspector, "scheduled_updates")
    foreign_keys = _fk_names(inspector, "scheduled_updates")
    indexes = _index_names(inspector, "scheduled_updates")

    if "ix_scheduled_updates_completed_at" in indexes:
        op.drop_index("ix_scheduled_updates_completed_at", table_name="scheduled_updates")
    if "ix_scheduled_updates_target_version_id" in indexes:
        op.drop_index(op.f("ix_scheduled_updates_target_version_id"), table_name="scheduled_updates")
    if "ix_scheduled_updates_source_version_id" in indexes:
        op.drop_index(op.f("ix_scheduled_updates_source_version_id"), table_name="scheduled_updates")
    if "fk_scheduled_updates_target_version_id" in foreign_keys:
        op.drop_constraint(
            "fk_scheduled_updates_target_version_id",
            "scheduled_updates",
            type_="foreignkey",
        )
    if "fk_scheduled_updates_source_version_id" in foreign_keys:
        op.drop_constraint(
            "fk_scheduled_updates_source_version_id",
            "scheduled_updates",
            type_="foreignkey",
        )
    if "target_version_id" in columns:
        op.drop_column("scheduled_updates", "target_version_id")
    if "source_version_id" in columns:
        op.drop_column("scheduled_updates", "source_version_id")

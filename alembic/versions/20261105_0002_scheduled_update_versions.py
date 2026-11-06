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


def upgrade() -> None:
    """Колонки source_version_id и target_version_id и индекс по completed_at."""
    op.add_column(
        "scheduled_updates",
        sa.Column("source_version_id", uuid_pk, nullable=True),
    )
    op.add_column(
        "scheduled_updates",
        sa.Column("target_version_id", uuid_pk, nullable=True),
    )
    op.create_foreign_key(
        "fk_scheduled_updates_source_version_id",
        "scheduled_updates",
        "configuration_versions",
        ["source_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_scheduled_updates_target_version_id",
        "scheduled_updates",
        "configuration_versions",
        ["target_version_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_index(
        op.f("ix_scheduled_updates_source_version_id"),
        "scheduled_updates",
        ["source_version_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_scheduled_updates_target_version_id"),
        "scheduled_updates",
        ["target_version_id"],
        unique=False,
    )
    op.create_index(
        "ix_scheduled_updates_completed_at",
        "scheduled_updates",
        ["completed_at"],
        unique=False,
    )


def downgrade() -> None:
    """Убирает эти колонки и индекс."""
    op.drop_index("ix_scheduled_updates_completed_at", table_name="scheduled_updates")
    op.drop_index(op.f("ix_scheduled_updates_target_version_id"), table_name="scheduled_updates")
    op.drop_index(op.f("ix_scheduled_updates_source_version_id"), table_name="scheduled_updates")
    op.drop_constraint(
        "fk_scheduled_updates_target_version_id",
        "scheduled_updates",
        type_="foreignkey",
    )
    op.drop_constraint(
        "fk_scheduled_updates_source_version_id",
        "scheduled_updates",
        type_="foreignkey",
    )
    op.drop_column("scheduled_updates", "target_version_id")
    op.drop_column("scheduled_updates", "source_version_id")

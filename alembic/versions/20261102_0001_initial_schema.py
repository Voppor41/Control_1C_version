"""initial schema

Revision ID: 20261102_0001
Revises:
Create Date: 2026-11-02

"""
from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20261102_0001"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

uuid_pk = postgresql.UUID(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "roles",
        sa.Column("id", uuid_pk, primary_key=True, nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_roles_code"), "roles", ["code"], unique=True)

    op.create_table(
        "users",
        sa.Column("id", uuid_pk, primary_key=True, nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("role_id", uuid_pk, nullable=False),
        sa.Column("client_id", uuid_pk, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_users_full_name"), "users", ["full_name"], unique=False)
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=True)
    op.create_index(op.f("ix_users_role_id"), "users", ["role_id"], unique=False)
    op.create_index(op.f("ix_users_client_id"), "users", ["client_id"], unique=False)

    op.create_table(
        "clients",
        sa.Column("id", uuid_pk, primary_key=True, nullable=False),
        sa.Column("company_name", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("responsible_employee_id", uuid_pk, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["responsible_employee_id"], ["users.id"], ondelete="SET NULL"),
        sa.UniqueConstraint("company_name"),
        sa.UniqueConstraint("phone"),
        sa.UniqueConstraint("email"),
    )
    op.create_index(op.f("ix_clients_company_name"), "clients", ["company_name"], unique=True)
    op.create_index(op.f("ix_clients_phone"), "clients", ["phone"], unique=True)
    op.create_index(op.f("ix_clients_email"), "clients", ["email"], unique=True)
    op.create_index(op.f("ix_clients_responsible_employee_id"), "clients", ["responsible_employee_id"], unique=False)

    op.create_foreign_key(
        "fk_users_client_id_clients",
        "users",
        "clients",
        ["client_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "configurations",
        sa.Column("id", uuid_pk, primary_key=True, nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.UniqueConstraint("name"),
    )
    op.create_index(op.f("ix_configurations_name"), "configurations", ["name"], unique=True)

    op.create_table(
        "configuration_versions",
        sa.Column("id", uuid_pk, primary_key=True, nullable=False),
        sa.Column("configuration_id", uuid_pk, nullable=False),
        sa.Column("version", sa.String(length=64), nullable=False),
        sa.Column("released_at", sa.Date(), nullable=True),
        sa.Column("is_current", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["configuration_id"], ["configurations.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("configuration_id", "version", name="uq_configuration_version"),
    )
    op.create_index(
        op.f("ix_configuration_versions_configuration_id"),
        "configuration_versions",
        ["configuration_id"],
        unique=False,
    )
    op.create_index(
        "uq_configuration_versions_current",
        "configuration_versions",
        ["configuration_id"],
        unique=True,
        postgresql_where=sa.text("is_current IS TRUE"),
    )

    op.create_table(
        "client_configurations",
        sa.Column("id", uuid_pk, primary_key=True, nullable=False),
        sa.Column("client_id", uuid_pk, nullable=False),
        sa.Column("configuration_id", uuid_pk, nullable=False),
        sa.Column("installed_version_id", uuid_pk, nullable=False),
        sa.Column("infobase_name", sa.String(length=255), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["configuration_id"], ["configurations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["installed_version_id"], ["configuration_versions.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("client_id", "configuration_id", name="uq_client_configuration"),
    )
    op.create_index(op.f("ix_client_configurations_client_id"), "client_configurations", ["client_id"], unique=False)
    op.create_index(
        op.f("ix_client_configurations_configuration_id"),
        "client_configurations",
        ["configuration_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_client_configurations_installed_version_id"),
        "client_configurations",
        ["installed_version_id"],
        unique=False,
    )

    op.create_table(
        "version_checks",
        sa.Column("id", uuid_pk, primary_key=True, nullable=False),
        sa.Column("client_configuration_id", uuid_pk, nullable=False),
        sa.Column("installed_version_id", uuid_pk, nullable=False),
        sa.Column("actual_version_id", uuid_pk, nullable=False),
        sa.Column("is_outdated", sa.Boolean(), nullable=False),
        sa.Column("checked_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("checked_by_id", uuid_pk, nullable=False),
        sa.ForeignKeyConstraint(["client_configuration_id"], ["client_configurations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["installed_version_id"], ["configuration_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["actual_version_id"], ["configuration_versions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["checked_by_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        op.f("ix_version_checks_client_configuration_id"),
        "version_checks",
        ["client_configuration_id"],
        unique=False,
    )
    op.create_index(op.f("ix_version_checks_is_outdated"), "version_checks", ["is_outdated"], unique=False)
    op.create_index(op.f("ix_version_checks_checked_at"), "version_checks", ["checked_at"], unique=False)
    op.create_index(op.f("ix_version_checks_checked_by_id"), "version_checks", ["checked_by_id"], unique=False)

    op.create_table(
        "update_slots",
        sa.Column("id", uuid_pk, primary_key=True, nullable=False),
        sa.Column("slot_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("capacity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("specialist_id", uuid_pk, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["specialist_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("specialist_id", "slot_date", "start_time", name="uq_specialist_slot"),
    )
    op.create_index(op.f("ix_update_slots_slot_date"), "update_slots", ["slot_date"], unique=False)
    op.create_index(op.f("ix_update_slots_specialist_id"), "update_slots", ["specialist_id"], unique=False)

    op.create_table(
        "scheduled_updates",
        sa.Column("id", uuid_pk, primary_key=True, nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="requested"),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("client_id", uuid_pk, nullable=False),
        sa.Column("client_configuration_id", uuid_pk, nullable=False),
        sa.Column("slot_id", uuid_pk, nullable=True),
        sa.Column("requested_by_id", uuid_pk, nullable=False),
        sa.Column("assigned_specialist_id", uuid_pk, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_configuration_id"], ["client_configurations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["slot_id"], ["update_slots.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requested_by_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_specialist_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_scheduled_updates_status"), "scheduled_updates", ["status"], unique=False)
    op.create_index(op.f("ix_scheduled_updates_client_id"), "scheduled_updates", ["client_id"], unique=False)
    op.create_index(
        op.f("ix_scheduled_updates_client_configuration_id"),
        "scheduled_updates",
        ["client_configuration_id"],
        unique=False,
    )
    op.create_index(op.f("ix_scheduled_updates_slot_id"), "scheduled_updates", ["slot_id"], unique=False)
    op.create_index(
        op.f("ix_scheduled_updates_assigned_specialist_id"),
        "scheduled_updates",
        ["assigned_specialist_id"],
        unique=False,
    )

    op.create_table(
        "update_status_history",
        sa.Column("id", uuid_pk, primary_key=True, nullable=False),
        sa.Column("old_status", sa.String(length=32), nullable=True),
        sa.Column("new_status", sa.String(length=32), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("scheduled_update_id", uuid_pk, nullable=False),
        sa.Column("changed_by_id", uuid_pk, nullable=False),
        sa.ForeignKeyConstraint(["scheduled_update_id"], ["scheduled_updates.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["changed_by_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index(
        op.f("ix_update_status_history_changed_at"),
        "update_status_history",
        ["changed_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_update_status_history_scheduled_update_id"),
        "update_status_history",
        ["scheduled_update_id"],
        unique=False,
    )

    op.create_table(
        "notifications",
        sa.Column("id", uuid_pk, primary_key=True, nullable=False),
        sa.Column("type", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("is_read", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("recipient_id", uuid_pk, nullable=False),
        sa.Column("created_by_id", uuid_pk, nullable=True),
        sa.Column("client_id", uuid_pk, nullable=False),
        sa.Column("client_configuration_id", uuid_pk, nullable=True),
        sa.Column("scheduled_update_id", uuid_pk, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["recipient_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["client_configuration_id"], ["client_configurations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["scheduled_update_id"], ["scheduled_updates.id"], ondelete="SET NULL"),
    )
    op.create_index(op.f("ix_notifications_type"), "notifications", ["type"], unique=False)
    op.create_index(op.f("ix_notifications_is_read"), "notifications", ["is_read"], unique=False)
    op.create_index(op.f("ix_notifications_recipient_id"), "notifications", ["recipient_id"], unique=False)
    op.create_index(op.f("ix_notifications_client_id"), "notifications", ["client_id"], unique=False)

    roles = sa.table(
        "roles",
        sa.column("id", uuid_pk),
        sa.column("code", sa.String),
        sa.column("name", sa.String),
    )
    op.bulk_insert(
        roles,
        [
            {"id": uuid.uuid4(), "code": "admin", "name": "Администратор"},
            {"id": uuid.uuid4(), "code": "specialist", "name": "Специалист по сопровождению"},
            {"id": uuid.uuid4(), "code": "manager", "name": "Руководитель отдела сопровождения"},
            {"id": uuid.uuid4(), "code": "client", "name": "Клиент"},
        ],
    )


def downgrade() -> None:
    op.drop_table("notifications")
    op.drop_table("update_status_history")
    op.drop_table("scheduled_updates")
    op.drop_table("update_slots")
    op.drop_table("version_checks")
    op.drop_table("client_configurations")
    op.drop_index("uq_configuration_versions_current", table_name="configuration_versions")
    op.drop_table("configuration_versions")
    op.drop_table("configurations")
    op.drop_constraint("fk_users_client_id_clients", "users", type_="foreignkey")
    op.drop_table("clients")
    op.drop_table("users")
    op.drop_table("roles")

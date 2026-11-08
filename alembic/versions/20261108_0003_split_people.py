"""Сотрудники и пользователи компании в разных таблицах. Должности остаются в roles без строки client.

Revision ID: 20261108_0003
Revises: 20261105_0002
Create Date: 2026-11-08

Общая таблица users делится на employees (служба сопровождения) и client_users
(вход со стороны организации). Идентификаторы сохраняются.

Колонки, где человек всегда сотрудник, начинают ссылаться на employees:
clients.responsible_employee_id, update_slots.specialist_id,
scheduled_updates.assigned_specialist_id, version_checks.checked_by_id.

Колонки, где человек может быть и тем и другим, становятся парой внешних ключей
с проверкой, что заполнен ровно один (или не больше одного у автора уведомления):
scheduled_updates.requested_by_*, update_status_history.changed_by_*,
notifications.created_by_*. Получатель уведомления всегда пользователь компании.
"""

from typing import Sequence, Union
import uuid

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "20261108_0003"
down_revision: Union[str, Sequence[str], None] = "20261105_0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

uuid_pk = postgresql.UUID(as_uuid=True)

_ONE_REQUESTER = (
    "(CASE WHEN requested_by_employee_id IS NOT NULL THEN 1 ELSE 0 END"
    " + CASE WHEN requested_by_client_user_id IS NOT NULL THEN 1 ELSE 0 END) = 1"
)
_ONE_CHANGER = (
    "(CASE WHEN changed_by_employee_id IS NOT NULL THEN 1 ELSE 0 END"
    " + CASE WHEN changed_by_client_user_id IS NOT NULL THEN 1 ELSE 0 END) = 1"
)
_ONE_AUTHOR = (
    "(CASE WHEN created_by_employee_id IS NOT NULL THEN 1 ELSE 0 END"
    " + CASE WHEN created_by_client_user_id IS NOT NULL THEN 1 ELSE 0 END) <= 1"
)


def _count(sql: str) -> int:
    value = op.get_bind().execute(sa.text(sql)).scalar()
    return int(value or 0)


def _expect_zero(sql: str, message: str) -> None:
    found = _count(sql)
    if found:
        raise RuntimeError(f"{message} ({found} rows)")


def _inspector() -> sa.Inspector:
    """Свежий список ограничений: Inspector кэширует отражение на соединении."""
    inspector = sa.inspect(op.get_bind())
    inspector.clear_cache()
    return inspector


def _drop_fk(table: str, column: str, referred: str) -> None:
    """Снимает внешний ключ колонки, если он ещё ссылается на referred."""
    for fk in _inspector().get_foreign_keys(table):
        if fk.get("constrained_columns") == [column] and fk.get("referred_table") == referred:
            name = fk.get("name")
            if name:
                op.drop_constraint(name, table, type_="foreignkey")
            return


def _point_fk(table: str, column: str, *, name: str, referred: str, ondelete: str) -> None:
    op.create_foreign_key(name, table, referred, [column], ["id"], ondelete=ondelete)


def _create_people_tables() -> None:
    op.create_table(
        "employees",
        sa.Column("id", uuid_pk, primary_key=True, nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("role_id", uuid_pk, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("email", name="uq_employees_email"),
    )
    op.create_index(op.f("ix_employees_full_name"), "employees", ["full_name"], unique=False)
    op.create_index(op.f("ix_employees_email"), "employees", ["email"], unique=True)
    op.create_index(op.f("ix_employees_role_id"), "employees", ["role_id"], unique=False)

    op.create_table(
        "client_users",
        sa.Column("id", uuid_pk, primary_key=True, nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=False),
        sa.Column("hashed_password", sa.String(length=255), nullable=False),
        sa.Column("phone", sa.String(length=32), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("client_id", uuid_pk, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["client_id"], ["clients.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("email", name="uq_client_users_email"),
    )
    op.create_index(op.f("ix_client_users_full_name"), "client_users", ["full_name"], unique=False)
    op.create_index(op.f("ix_client_users_email"), "client_users", ["email"], unique=True)
    op.create_index(op.f("ix_client_users_client_id"), "client_users", ["client_id"], unique=False)


def _copy_people() -> None:
    _expect_zero(
        """
        SELECT count(*)
        FROM users AS u
        JOIN roles AS r ON r.id = u.role_id
        WHERE r.code = 'client' AND u.client_id IS NULL
        """,
        "A company login has no client_id and cannot move into client_users",
    )
    op.execute(
        sa.text(
            """
            INSERT INTO employees (
                id, full_name, email, hashed_password, phone, is_active, role_id, created_at, updated_at
            )
            SELECT u.id, u.full_name, u.email, u.hashed_password, u.phone, u.is_active, u.role_id,
                   u.created_at, u.updated_at
            FROM users AS u
            JOIN roles AS r ON r.id = u.role_id
            WHERE r.code <> 'client'
            """
        )
    )
    op.execute(
        sa.text(
            """
            INSERT INTO client_users (
                id, full_name, email, hashed_password, phone, is_active, client_id, created_at, updated_at
            )
            SELECT u.id, u.full_name, u.email, u.hashed_password, u.phone, u.is_active, u.client_id,
                   u.created_at, u.updated_at
            FROM users AS u
            JOIN roles AS r ON r.id = u.role_id
            WHERE r.code = 'client' AND u.client_id IS NOT NULL
            """
        )
    )
    users_count = _count("SELECT count(*) FROM users")
    copied = _count("SELECT count(*) FROM employees") + _count("SELECT count(*) FROM client_users")
    if users_count != copied:
        raise RuntimeError(
            f"Not every users row was copied into employees or client_users ({copied} of {users_count})"
        )


def _install_email_guard() -> None:
    """Почта для входа не может одновременно лежать в employees и в client_users."""
    op.execute(
        sa.text(
            """
            CREATE OR REPLACE FUNCTION login_email_not_shared() RETURNS trigger AS $$
            BEGIN
              IF TG_TABLE_NAME = 'employees' THEN
                IF EXISTS (SELECT 1 FROM client_users WHERE email = NEW.email) THEN
                  RAISE EXCEPTION 'login email already belongs to a company user'
                    USING ERRCODE = 'unique_violation';
                END IF;
              ELSIF TG_TABLE_NAME = 'client_users' THEN
                IF EXISTS (SELECT 1 FROM employees WHERE email = NEW.email) THEN
                  RAISE EXCEPTION 'login email already belongs to an employee'
                    USING ERRCODE = 'unique_violation';
                END IF;
              END IF;
              RETURN NEW;
            END;
            $$ LANGUAGE plpgsql
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER employees_login_email_not_shared
            BEFORE INSERT OR UPDATE OF email ON employees
            FOR EACH ROW EXECUTE FUNCTION login_email_not_shared()
            """
        )
    )
    op.execute(
        sa.text(
            """
            CREATE TRIGGER client_users_login_email_not_shared
            BEFORE INSERT OR UPDATE OF email ON client_users
            FOR EACH ROW EXECUTE FUNCTION login_email_not_shared()
            """
        )
    )


def _retarget_staff_fks() -> None:
    """Колонки, которые и раньше означали только сотрудника."""
    staff = (
        ("clients", "responsible_employee_id", "SET NULL", "fk_clients_responsible_employee_id_employees"),
        ("version_checks", "checked_by_id", "RESTRICT", "fk_version_checks_checked_by_id_employees"),
        ("update_slots", "specialist_id", "RESTRICT", "fk_update_slots_specialist_id_employees"),
        (
            "scheduled_updates",
            "assigned_specialist_id",
            "SET NULL",
            "fk_scheduled_updates_assigned_specialist_id_employees",
        ),
    )
    for table, column, ondelete, name in staff:
        _expect_zero(
            f"""
            SELECT count(*) FROM {table}
            WHERE {column} IS NOT NULL
              AND {column} NOT IN (SELECT id FROM employees)
            """,
            f"{table}.{column} does not point at an employee",
        )
        _drop_fk(table, column, "users")
        _point_fk(table, column, name=name, referred="employees", ondelete=ondelete)


def _split_requested_by() -> None:
    op.add_column("scheduled_updates", sa.Column("requested_by_employee_id", uuid_pk, nullable=True))
    op.add_column("scheduled_updates", sa.Column("requested_by_client_user_id", uuid_pk, nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE scheduled_updates AS su
            SET requested_by_employee_id = su.requested_by_id
            WHERE EXISTS (SELECT 1 FROM employees AS e WHERE e.id = su.requested_by_id)
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE scheduled_updates AS su
            SET requested_by_client_user_id = su.requested_by_id
            WHERE su.requested_by_employee_id IS NULL
              AND EXISTS (SELECT 1 FROM client_users AS c WHERE c.id = su.requested_by_id)
            """
        )
    )
    _expect_zero(
        f"SELECT count(*) FROM scheduled_updates WHERE NOT ({_ONE_REQUESTER})",
        "scheduled_updates.requested_by_id did not map to exactly one person",
    )
    _point_fk(
        "scheduled_updates",
        "requested_by_employee_id",
        name="fk_scheduled_updates_requested_by_employee_id",
        referred="employees",
        ondelete="RESTRICT",
    )
    _point_fk(
        "scheduled_updates",
        "requested_by_client_user_id",
        name="fk_scheduled_updates_requested_by_client_user_id",
        referred="client_users",
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_scheduled_updates_requested_by_employee_id",
        "scheduled_updates",
        ["requested_by_employee_id"],
        unique=False,
    )
    op.create_index(
        "ix_scheduled_updates_requested_by_client_user_id",
        "scheduled_updates",
        ["requested_by_client_user_id"],
        unique=False,
    )
    op.create_check_constraint("ck_scheduled_updates_one_requester", "scheduled_updates", _ONE_REQUESTER)
    _drop_fk("scheduled_updates", "requested_by_id", "users")
    op.drop_column("scheduled_updates", "requested_by_id")


def _split_changed_by() -> None:
    op.add_column("update_status_history", sa.Column("changed_by_employee_id", uuid_pk, nullable=True))
    op.add_column("update_status_history", sa.Column("changed_by_client_user_id", uuid_pk, nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE update_status_history AS h
            SET changed_by_employee_id = h.changed_by_id
            WHERE EXISTS (SELECT 1 FROM employees AS e WHERE e.id = h.changed_by_id)
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE update_status_history AS h
            SET changed_by_client_user_id = h.changed_by_id
            WHERE h.changed_by_employee_id IS NULL
              AND EXISTS (SELECT 1 FROM client_users AS c WHERE c.id = h.changed_by_id)
            """
        )
    )
    _expect_zero(
        f"SELECT count(*) FROM update_status_history WHERE NOT ({_ONE_CHANGER})",
        "update_status_history.changed_by_id did not map to exactly one person",
    )
    _point_fk(
        "update_status_history",
        "changed_by_employee_id",
        name="fk_update_status_history_changed_by_employee_id",
        referred="employees",
        ondelete="RESTRICT",
    )
    _point_fk(
        "update_status_history",
        "changed_by_client_user_id",
        name="fk_update_status_history_changed_by_client_user_id",
        referred="client_users",
        ondelete="RESTRICT",
    )
    op.create_index(
        "ix_update_status_history_changed_by_employee_id",
        "update_status_history",
        ["changed_by_employee_id"],
        unique=False,
    )
    op.create_index(
        "ix_update_status_history_changed_by_client_user_id",
        "update_status_history",
        ["changed_by_client_user_id"],
        unique=False,
    )
    op.create_check_constraint("ck_update_status_history_one_changer", "update_status_history", _ONE_CHANGER)
    _drop_fk("update_status_history", "changed_by_id", "users")
    op.drop_column("update_status_history", "changed_by_id")


def _split_notification_people() -> None:
    _expect_zero(
        """
        SELECT count(*) FROM notifications
        WHERE recipient_id NOT IN (SELECT id FROM client_users)
        """,
        "notifications.recipient_id is not a company user",
    )
    _drop_fk("notifications", "recipient_id", "users")
    _point_fk(
        "notifications",
        "recipient_id",
        name="fk_notifications_recipient_id_client_users",
        referred="client_users",
        ondelete="CASCADE",
    )

    op.add_column("notifications", sa.Column("created_by_employee_id", uuid_pk, nullable=True))
    op.add_column("notifications", sa.Column("created_by_client_user_id", uuid_pk, nullable=True))
    op.execute(
        sa.text(
            """
            UPDATE notifications AS n
            SET created_by_employee_id = n.created_by_id
            WHERE n.created_by_id IS NOT NULL
              AND EXISTS (SELECT 1 FROM employees AS e WHERE e.id = n.created_by_id)
            """
        )
    )
    op.execute(
        sa.text(
            """
            UPDATE notifications AS n
            SET created_by_client_user_id = n.created_by_id
            WHERE n.created_by_id IS NOT NULL
              AND n.created_by_employee_id IS NULL
              AND EXISTS (SELECT 1 FROM client_users AS c WHERE c.id = n.created_by_id)
            """
        )
    )
    _expect_zero(
        """
        SELECT count(*) FROM notifications
        WHERE created_by_id IS NOT NULL
          AND created_by_employee_id IS NULL
          AND created_by_client_user_id IS NULL
        """,
        "notifications.created_by_id did not map to an employee or a company user",
    )
    _point_fk(
        "notifications",
        "created_by_employee_id",
        name="fk_notifications_created_by_employee_id",
        referred="employees",
        ondelete="SET NULL",
    )
    _point_fk(
        "notifications",
        "created_by_client_user_id",
        name="fk_notifications_created_by_client_user_id",
        referred="client_users",
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_notifications_created_by_employee_id",
        "notifications",
        ["created_by_employee_id"],
        unique=False,
    )
    op.create_index(
        "ix_notifications_created_by_client_user_id",
        "notifications",
        ["created_by_client_user_id"],
        unique=False,
    )
    op.create_check_constraint("ck_notifications_one_author", "notifications", _ONE_AUTHOR)
    _drop_fk("notifications", "created_by_id", "users")
    op.drop_column("notifications", "created_by_id")


def _drop_users_and_client_role() -> None:
    user_fks = {fk.get("name") for fk in _inspector().get_foreign_keys("users")}
    if "fk_users_client_id_clients" in user_fks:
        op.drop_constraint("fk_users_client_id_clients", "users", type_="foreignkey")
    op.drop_table("users")
    op.execute(sa.text("DELETE FROM roles WHERE code = 'client'"))


def upgrade() -> None:
    """Делит users на employees и client_users и переназначает внешние ключи."""
    _create_people_tables()
    _copy_people()
    _install_email_guard()
    _retarget_staff_fks()
    _split_requested_by()
    _split_changed_by()
    _split_notification_people()
    _drop_users_and_client_role()


def _ensure_client_role() -> uuid.UUID:
    existing = op.get_bind().execute(sa.text("SELECT id FROM roles WHERE code = 'client'")).scalar()
    if existing is not None:
        return existing
    role_id = uuid.uuid4()
    op.get_bind().execute(
        sa.text("INSERT INTO roles (id, code, name) VALUES (:id, 'client', :name)"),
        {"id": role_id, "name": "Клиент"},
    )
    return role_id


def _recreate_users(client_role_id: uuid.UUID) -> None:
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
    op.execute(
        sa.text(
            """
            INSERT INTO users (
                id, full_name, email, hashed_password, phone, is_active, role_id, client_id, created_at, updated_at
            )
            SELECT id, full_name, email, hashed_password, phone, is_active, role_id, NULL, created_at, updated_at
            FROM employees
            """
        )
    )
    op.get_bind().execute(
        sa.text(
            """
            INSERT INTO users (
                id, full_name, email, hashed_password, phone, is_active, role_id, client_id, created_at, updated_at
            )
            SELECT id, full_name, email, hashed_password, phone, is_active, :role_id, client_id, created_at, updated_at
            FROM client_users
            """
        ),
        {"role_id": client_role_id},
    )
    op.create_foreign_key(
        "fk_users_client_id_clients",
        "users",
        "clients",
        ["client_id"],
        ["id"],
        ondelete="SET NULL",
    )


def _restore_single_user_fk(
    table: str,
    column: str,
    *,
    employee_column: str,
    client_column: str,
    ondelete: str,
    nullable: bool,
    check_name: str | None,
) -> None:
    op.add_column(table, sa.Column(column, uuid_pk, nullable=True))
    op.execute(
        sa.text(
            f"""
            UPDATE {table}
            SET {column} = COALESCE({employee_column}, {client_column})
            """
        )
    )
    if not nullable:
        op.alter_column(table, column, nullable=False)
    _point_fk(table, column, name=f"fk_{table}_{column}_users", referred="users", ondelete=ondelete)
    if check_name is not None:
        op.drop_constraint(check_name, table, type_="check")
    for extra in (employee_column, client_column):
        _drop_fk(table, extra, "employees")
        _drop_fk(table, extra, "client_users")
        index_name = f"ix_{table}_{extra}"
        indexes = {index["name"] for index in _inspector().get_indexes(table)}
        if index_name in indexes:
            op.drop_index(index_name, table_name=table)
        op.drop_column(table, extra)


def _retarget_staff_back_to_users() -> None:
    staff = (
        ("clients", "responsible_employee_id", "SET NULL", "fk_clients_responsible_employee_id_employees"),
        ("version_checks", "checked_by_id", "RESTRICT", "fk_version_checks_checked_by_id_employees"),
        ("update_slots", "specialist_id", "RESTRICT", "fk_update_slots_specialist_id_employees"),
        (
            "scheduled_updates",
            "assigned_specialist_id",
            "SET NULL",
            "fk_scheduled_updates_assigned_specialist_id_employees",
        ),
    )
    for table, column, ondelete, current in staff:
        op.drop_constraint(current, table, type_="foreignkey")
        _point_fk(table, column, name=f"fk_{table}_{column}_users", referred="users", ondelete=ondelete)


def downgrade() -> None:
    """Собирает users обратно и возвращает одиночные внешние ключи на неё."""
    client_role_id = _ensure_client_role()
    _recreate_users(client_role_id)
    _retarget_staff_back_to_users()
    _restore_single_user_fk(
        "scheduled_updates",
        "requested_by_id",
        employee_column="requested_by_employee_id",
        client_column="requested_by_client_user_id",
        ondelete="RESTRICT",
        nullable=False,
        check_name="ck_scheduled_updates_one_requester",
    )
    _restore_single_user_fk(
        "update_status_history",
        "changed_by_id",
        employee_column="changed_by_employee_id",
        client_column="changed_by_client_user_id",
        ondelete="RESTRICT",
        nullable=False,
        check_name="ck_update_status_history_one_changer",
    )
    _restore_single_user_fk(
        "notifications",
        "created_by_id",
        employee_column="created_by_employee_id",
        client_column="created_by_client_user_id",
        ondelete="SET NULL",
        nullable=True,
        check_name="ck_notifications_one_author",
    )
    op.drop_constraint("fk_notifications_recipient_id_client_users", "notifications", type_="foreignkey")
    _point_fk(
        "notifications",
        "recipient_id",
        name="fk_notifications_recipient_id_users",
        referred="users",
        ondelete="CASCADE",
    )
    op.execute(sa.text("DROP TRIGGER IF EXISTS employees_login_email_not_shared ON employees"))
    op.execute(sa.text("DROP TRIGGER IF EXISTS client_users_login_email_not_shared ON client_users"))
    op.drop_table("client_users")
    op.drop_table("employees")
    op.execute(sa.text("DROP FUNCTION IF EXISTS login_email_not_shared()"))

import asyncio
import logging
import uuid
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.security import hash_password
from src.data.models import (
    Client,
    ClientConfiguration,
    Configuration,
    ConfigurationVersion,
    Notification,
    NotificationType,
    Role,
    RoleCode,
    ScheduledUpdate,
    UpdateSlot,
    UpdateStatus,
    UpdateStatusHistory,
    User,
    VersionCheck,
)

logger = logging.getLogger(__name__)

NS = uuid.UUID("c0ffee00-0000-4000-8000-000000000001")

DEMO_EMAILS = (
    "admin@example.com",
    "specialist@example.com",
    "manager@example.com",
    "client@example.com",
)

DEMO_PASSWORD = {
    "admin@example.com": "admin123",
    "specialist@example.com": "specialist123",
    "manager@example.com": "manager123",
    "client@example.com": "client123",
}

ROLE_TITLES = {
    RoleCode.ADMIN: "Администратор",
    RoleCode.SPECIALIST: "Специалист по сопровождению",
    RoleCode.MANAGER: "Руководитель отдела сопровождения",
    RoleCode.CLIENT: "Клиент",
}


def demo_id(name: str) -> uuid.UUID:
    return uuid.uuid5(NS, name)


async def seed_initial_data(session: AsyncSession) -> None:
    existing = set()
    for code in (await session.execute(select(Role.code))).scalars().all():
        existing.add(code.value if hasattr(code, "value") else str(code))
    for code, title in ROLE_TITLES.items():
        if code.value not in existing:
            session.add(Role(code=code, name=title))
    await session.commit()


async def _role(session: AsyncSession, code: RoleCode) -> Role:
    role = await session.scalar(select(Role).where(Role.code == code))
    if role is None:
        raise RuntimeError(f"Role {code.value} is missing. Run alembic upgrade head first.")
    return role


async def _ensure_user(
    session: AsyncSession,
    *,
    key: str,
    email: str,
    full_name: str,
    password: str,
    role: Role,
    client_id: uuid.UUID | None = None,
) -> User:
    user = await session.scalar(select(User).where(User.email == email))
    if user is None:
        user = await session.get(User, demo_id(key))
    if user is not None:
        if user.email != email:
            user.email = email
            await session.flush()
        return user
    user = User(
        id=demo_id(key),
        full_name=full_name,
        email=email,
        hashed_password=hash_password(password),
        is_active=True,
        role_id=role.id,
        client_id=client_id,
    )
    session.add(user)
    await session.flush()
    return user


async def _ensure_client(
    session: AsyncSession,
    *,
    key: str,
    company_name: str,
    phone: str,
    email: str,
    responsible_employee_id: uuid.UUID,
) -> Client:
    client = await session.scalar(select(Client).where(Client.company_name == company_name))
    if client is not None:
        return client
    client = Client(
        id=demo_id(key),
        company_name=company_name,
        phone=phone,
        email=email,
        responsible_employee_id=responsible_employee_id,
    )
    session.add(client)
    await session.flush()
    return client


async def _ensure_configuration(
    session: AsyncSession,
    *,
    key: str,
    name: str,
    description: str,
) -> Configuration:
    row = await session.scalar(select(Configuration).where(Configuration.name == name))
    if row is not None:
        return row
    row = Configuration(id=demo_id(key), name=name, description=description)
    session.add(row)
    await session.flush()
    return row


async def _ensure_version(
    session: AsyncSession,
    *,
    key: str,
    configuration_id: uuid.UUID,
    version: str,
    released_at: date,
    is_current: bool,
    notes: str,
) -> ConfigurationVersion:
    row = await session.scalar(
        select(ConfigurationVersion).where(
            ConfigurationVersion.configuration_id == configuration_id,
            ConfigurationVersion.version == version,
        )
    )
    if row is not None:
        return row
    row = ConfigurationVersion(
        id=demo_id(key),
        configuration_id=configuration_id,
        version=version,
        released_at=released_at,
        is_current=is_current,
        notes=notes,
    )
    session.add(row)
    await session.flush()
    return row


async def _ensure_installation(
    session: AsyncSession,
    *,
    key: str,
    client_id: uuid.UUID,
    configuration_id: uuid.UUID,
    installed_version_id: uuid.UUID,
    infobase_name: str,
) -> ClientConfiguration:
    row = await session.scalar(
        select(ClientConfiguration).where(
            ClientConfiguration.client_id == client_id,
            ClientConfiguration.configuration_id == configuration_id,
        )
    )
    if row is not None:
        return row
    row = ClientConfiguration(
        id=demo_id(key),
        client_id=client_id,
        configuration_id=configuration_id,
        installed_version_id=installed_version_id,
        infobase_name=infobase_name,
    )
    session.add(row)
    await session.flush()
    return row


async def seed_demo_data(session: AsyncSession) -> None:
    admin_role = await _role(session, RoleCode.ADMIN)
    specialist_role = await _role(session, RoleCode.SPECIALIST)
    manager_role = await _role(session, RoleCode.MANAGER)
    client_role = await _role(session, RoleCode.CLIENT)

    await _ensure_user(
        session,
        key="user:admin",
        email="admin@example.com",
        full_name="Администратор Системы",
        password=DEMO_PASSWORD["admin@example.com"],
        role=admin_role,
    )
    specialist = await _ensure_user(
        session,
        key="user:specialist",
        email="specialist@example.com",
        full_name="Мария Смирнова",
        password=DEMO_PASSWORD["specialist@example.com"],
        role=specialist_role,
    )
    await _ensure_user(
        session,
        key="user:manager",
        email="manager@example.com",
        full_name="Алексей Орлов",
        password=DEMO_PASSWORD["manager@example.com"],
        role=manager_role,
    )

    romashka = await _ensure_client(
        session,
        key="client:romashka",
        company_name="ООО Ромашка",
        phone="+79000000001",
        email="romashka@example.com",
        responsible_employee_id=specialist.id,
    )
    vasilek = await _ensure_client(
        session,
        key="client:vasilek",
        company_name="АО Василёк",
        phone="+79000000002",
        email="vasilek@example.com",
        responsible_employee_id=specialist.id,
    )

    accounting = await _ensure_configuration(
        session,
        key="cfg:bp",
        name="Бухгалтерия предприятия",
        description="Типовая конфигурация 1С:Бухгалтерия предприятия",
    )
    payroll = await _ensure_configuration(
        session,
        key="cfg:zup",
        name="Зарплата и управление персоналом",
        description="Типовая конфигурация 1С:Зарплата и управление персоналом",
    )

    bp_old = await _ensure_version(
        session,
        key="ver:bp:3.0.150",
        configuration_id=accounting.id,
        version="3.0.150",
        released_at=date(2025, 6, 1),
        is_current=False,
        notes="Предыдущий релиз",
    )
    bp_current = await _ensure_version(
        session,
        key="ver:bp:3.0.175",
        configuration_id=accounting.id,
        version="3.0.175",
        released_at=date(2026, 9, 15),
        is_current=True,
        notes="Актуальный релиз",
    )
    zup_old = await _ensure_version(
        session,
        key="ver:zup:3.1.27",
        configuration_id=payroll.id,
        version="3.1.27",
        released_at=date(2025, 11, 1),
        is_current=False,
        notes="Предыдущий релиз",
    )
    zup_current = await _ensure_version(
        session,
        key="ver:zup:3.1.32",
        configuration_id=payroll.id,
        version="3.1.32",
        released_at=date(2026, 8, 20),
        is_current=True,
        notes="Актуальный релиз",
    )

    romashka_bp = await _ensure_installation(
        session,
        key="cc:romashka:bp",
        client_id=romashka.id,
        configuration_id=accounting.id,
        installed_version_id=bp_old.id,
        infobase_name="romashka_bp",
    )
    vasilek_zup = await _ensure_installation(
        session,
        key="cc:vasilek:zup",
        client_id=vasilek.id,
        configuration_id=payroll.id,
        installed_version_id=zup_current.id,
        infobase_name="vasilek_zup",
    )

    portal = await _ensure_user(
        session,
        key="user:client",
        email="client@example.com",
        full_name="Иван Петров",
        password=DEMO_PASSWORD["client@example.com"],
        role=client_role,
        client_id=romashka.id,
    )

    today = date.today()
    for offset in range(1, 8):
        slot_date = today + timedelta(days=offset)
        for start_hour, end_hour in ((10, 12), (14, 16)):
            start = time(start_hour, 0)
            exists = await session.scalar(
                select(UpdateSlot.id).where(
                    UpdateSlot.specialist_id == specialist.id,
                    UpdateSlot.slot_date == slot_date,
                    UpdateSlot.start_time == start,
                )
            )
            if exists is not None:
                continue
            session.add(
                UpdateSlot(
                    id=demo_id(f"slot:{slot_date.isoformat()}:{start_hour}"),
                    slot_date=slot_date,
                    start_time=start,
                    end_time=time(end_hour, 0),
                    capacity=1,
                    is_active=True,
                    specialist_id=specialist.id,
                )
            )

    update_id = demo_id("update:vasilek:zup")
    scheduled = await session.get(ScheduledUpdate, update_id)
    if scheduled is None:
        completed_at = datetime.now(timezone.utc) - timedelta(days=2)
        scheduled = ScheduledUpdate(
            id=update_id,
            status=UpdateStatus.COMPLETED,
            comment="Демонстрационное выполненное обновление",
            completed_at=completed_at,
            client_id=vasilek.id,
            client_configuration_id=vasilek_zup.id,
            source_version_id=zup_old.id,
            target_version_id=zup_current.id,
            requested_by_id=specialist.id,
            assigned_specialist_id=specialist.id,
        )
        session.add(scheduled)
        await session.flush()
        session.add_all(
            [
                UpdateStatusHistory(
                    id=demo_id("hist:vasilek:requested"),
                    old_status=None,
                    new_status=UpdateStatus.REQUESTED,
                    comment="Клиент запросил обновление",
                    changed_at=completed_at - timedelta(days=1),
                    scheduled_update_id=scheduled.id,
                    changed_by_id=specialist.id,
                ),
                UpdateStatusHistory(
                    id=demo_id("hist:vasilek:completed"),
                    old_status=UpdateStatus.REQUESTED,
                    new_status=UpdateStatus.COMPLETED,
                    comment="Обновление выполнено",
                    changed_at=completed_at,
                    scheduled_update_id=scheduled.id,
                    changed_by_id=specialist.id,
                ),
            ]
        )

    check_id = demo_id("check:romashka:bp")
    if await session.get(VersionCheck, check_id) is None:
        session.add(
            VersionCheck(
                id=check_id,
                client_configuration_id=romashka_bp.id,
                installed_version_id=bp_old.id,
                actual_version_id=bp_current.id,
                is_outdated=True,
                checked_at=datetime.now(timezone.utc) - timedelta(days=1),
                checked_by_id=specialist.id,
            )
        )

    note_id = demo_id("note:romashka:update")
    existing_note = await session.get(Notification, note_id)
    if existing_note is None:
        session.add(
            Notification(
                id=note_id,
                type=NotificationType.UPDATE_AVAILABLE,
                title="Доступно обновление: Бухгалтерия предприятия",
                message=(
                    "Конфигурация «Бухгалтерия предприятия» (romashka_bp): "
                    "установлена версия 3.0.150, актуальная 3.0.175. "
                    "Выберите дату обновления."
                ),
                is_read=False,
                recipient_id=portal.id,
                created_by_id=specialist.id,
                client_id=romashka.id,
                client_configuration_id=romashka_bp.id,
            )
        )
    elif existing_note.recipient_id != portal.id:
        existing_note.recipient_id = portal.id

    await session.commit()
    logger.info(
        "Demo seed ready for %s (passwords are in the README)",
        ", ".join(DEMO_EMAILS),
    )


async def _cli() -> None:
    from src.core.database import async_session

    async with async_session() as session:
        await seed_initial_data(session)
        await seed_demo_data(session)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    asyncio.run(_cli())

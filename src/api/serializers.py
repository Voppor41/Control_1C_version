"""Сборка схем ответа из ORM-объектов. Связи должны быть загружены заранее."""

from datetime import datetime
from uuid import UUID

from src.api.schemas import (
    ClientConfigurationRead,
    ClientRead,
    ConfigurationDetail,
    ConfigurationRead,
    NotificationRead,
    ScheduledUpdateDetail,
    ScheduledUpdateRead,
    SlotRead,
    StatusEventRead,
    UpdateBrief,
    UserRead,
    VersionCheckRead,
    VersionRead,
)
from src.data.models import (
    Client,
    ClientConfiguration,
    ClientUser,
    Configuration,
    ConfigurationVersion,
    Employee,
    Notification,
    RoleCode,
    ScheduledUpdate,
    UpdateSlot,
    UpdateStatusHistory,
    VersionCheck,
)


def user_read(person: Employee | ClientUser) -> UserRead:
    """Карточка без хеша пароля. У сотрудника role — должность, у пользователя компании role=client."""
    if isinstance(person, Employee):
        return UserRead(
            id=person.id,
            full_name=person.full_name,
            email=person.email,
            phone=person.phone,
            is_active=person.is_active,
            role=person.role.code,
            client_id=None,
            client_name=None,
            created_at=person.created_at,
            updated_at=person.updated_at,
        )
    return UserRead(
        id=person.id,
        full_name=person.full_name,
        email=person.email,
        phone=person.phone,
        is_active=person.is_active,
        role=RoleCode.CLIENT,
        client_id=person.client_id,
        client_name=person.client.company_name if person.client is not None else None,
        created_at=person.created_at,
        updated_at=person.updated_at,
    )


def client_read(client: Client) -> ClientRead:
    """Карточка организации и имя ответственного, если он загружен."""
    employee = client.responsible_employee
    return ClientRead(
        id=client.id,
        company_name=client.company_name,
        phone=client.phone,
        email=client.email,
        responsible_employee_id=client.responsible_employee_id,
        responsible_employee_name=employee.full_name if employee is not None else None,
        created_at=client.created_at,
        updated_at=client.updated_at,
    )


def configuration_read(row: Configuration, current: str | None) -> ConfigurationRead:
    """Каталожная конфигурация и строка актуального релиза."""
    return ConfigurationRead(
        id=row.id,
        name=row.name,
        description=row.description,
        current_version=current,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def configuration_detail(row: Configuration, versions: list[ConfigurationVersion]) -> ConfigurationDetail:
    """То же плюс список релизов."""
    current = next((item.version for item in versions if item.is_current), None)
    base = configuration_read(row, current)
    return ConfigurationDetail(
        **base.model_dump(),
        versions=[VersionRead.model_validate(item) for item in versions],
    )


def installation_read(
    row: ClientConfiguration,
    current: ConfigurationVersion | None,
    last_checked_at: datetime | None,
) -> ClientConfigurationRead:
    """Установка, актуальный релиз и признак устаревания."""
    installed = row.installed_version
    return ClientConfigurationRead(
        id=row.id,
        client_id=row.client_id,
        company_name=row.client.company_name,
        configuration_id=row.configuration_id,
        configuration_name=row.configuration.name,
        installed_version_id=row.installed_version_id,
        installed_version=installed.version,
        current_version_id=current.id if current is not None else None,
        current_version=current.version if current is not None else None,
        # None, если в каталоге ещё не отмечен актуальный релиз: сравнивать не с чем.
        is_outdated=(installed.id != current.id) if current is not None else None,
        infobase_name=row.infobase_name,
        last_checked_at=last_checked_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def version_check_read(row: VersionCheck) -> VersionCheckRead:
    """Одна сохранённая проверка человекочитаемыми номерами версий."""
    installation = row.client_configuration
    return VersionCheckRead(
        id=row.id,
        client_configuration_id=row.client_configuration_id,
        client_id=installation.client_id,
        company_name=installation.client.company_name,
        configuration_name=installation.configuration.name,
        installed_version_id=row.installed_version_id,
        installed_version=row.installed_version.version,
        actual_version_id=row.actual_version_id,
        actual_version=row.actual_version.version,
        is_outdated=row.is_outdated,
        checked_at=row.checked_at,
        checked_by_id=row.checked_by_id,
        checked_by_name=row.checked_by.full_name,
    )


def notification_read(row: Notification) -> NotificationRead:
    """Уведомление с названием организации и конфигурации."""
    configuration_name = None
    if row.client_configuration is not None and row.client_configuration.configuration is not None:
        configuration_name = row.client_configuration.configuration.name
    return NotificationRead(
        id=row.id,
        type=row.type,
        title=row.title,
        message=row.message,
        is_read=row.is_read,
        created_at=row.created_at,
        client_id=row.client_id,
        company_name=row.client.company_name,
        client_configuration_id=row.client_configuration_id,
        configuration_name=configuration_name,
        scheduled_update_id=row.scheduled_update_id,
        recipient_id=row.recipient_id,
        created_by_id=row.created_by_id,
    )


def slot_read(row: UpdateSlot, booked: int) -> SlotRead:
    """Окно и остаток мест: capacity минус уже занятые."""
    remaining = max(row.capacity - booked, 0)
    return SlotRead(
        id=row.id,
        slot_date=row.slot_date,
        start_time=row.start_time,
        end_time=row.end_time,
        capacity=row.capacity,
        booked=booked,
        remaining=remaining,
        is_active=row.is_active,
        specialist_id=row.specialist_id,
        specialist_name=row.specialist.full_name,
    )


def status_event_read(row: UpdateStatusHistory) -> StatusEventRead:
    """Строка истории статуса."""
    return StatusEventRead(
        id=row.id,
        old_status=row.old_status,
        new_status=row.new_status,
        comment=row.comment,
        changed_at=row.changed_at,
        changed_by_id=row.changed_by_id,
        changed_by_name=row.changed_by.full_name,
    )


def scheduled_update_read(row: ScheduledUpdate) -> ScheduledUpdateRead:
    """Заявка без истории."""
    installation = row.client_configuration
    slot = row.slot
    return ScheduledUpdateRead(
        id=row.id,
        status=row.status,
        comment=row.comment,
        completed_at=row.completed_at,
        created_at=row.created_at,
        updated_at=row.updated_at,
        client_id=row.client_id,
        company_name=row.client.company_name,
        client_configuration_id=row.client_configuration_id,
        configuration_name=installation.configuration.name,
        infobase_name=installation.infobase_name,
        source_version_id=row.source_version_id,
        source_version=row.source_version.version if row.source_version is not None else None,
        target_version_id=row.target_version_id,
        target_version=row.target_version.version if row.target_version is not None else None,
        slot_id=row.slot_id,
        slot_date=slot.slot_date if slot is not None else None,
        slot_start=slot.start_time if slot is not None else None,
        slot_end=slot.end_time if slot is not None else None,
        requested_by_id=row.requested_by_id,
        requested_by_name=row.requested_by.full_name,
        assigned_specialist_id=row.assigned_specialist_id,
        assigned_specialist_name=(
            row.assigned_specialist.full_name if row.assigned_specialist is not None else None
        ),
    )


def scheduled_update_detail(row: ScheduledUpdate) -> ScheduledUpdateDetail:
    """Заявка с историей статусов."""
    base = scheduled_update_read(row)
    return ScheduledUpdateDetail(
        **base.model_dump(),
        status_history=[status_event_read(item) for item in row.status_history],
    )


def update_brief(row: ScheduledUpdate) -> UpdateBrief:
    """Короткая строка для отчёта план/факт."""
    return UpdateBrief(
        id=row.id,
        status=row.status,
        client_id=row.client_id,
        company_name=row.client.company_name,
        configuration_name=row.client_configuration.configuration.name,
        slot_date=row.slot.slot_date if row.slot is not None else None,
        completed_at=row.completed_at,
        created_at=row.created_at,
    )


def ids(values: list[UUID]) -> set[UUID]:
    """Множество идентификаторов без повторов."""
    return set(values)

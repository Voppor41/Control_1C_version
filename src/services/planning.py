"""Окна обновления и заявки: выбор даты, вместимость слота и переходы статуса."""

from datetime import date, datetime, time, timezone
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.data.models import (
    Account,
    ClientConfiguration,
    ConfigurationVersion,
    NotificationType,
    RoleCode,
    ScheduledUpdate,
    UpdateSlot,
    UpdateStatus,
    UpdateStatusHistory,
)
from src.services.accounts import author_ids
from src.services.catalog import get_current_version, get_installation
from src.services.common import actor_role, ensure_client_scope, flush_session
from src.services.notifications import notify_client_users

# Пока заявка в одном из этих статусов, вторую на ту же установку не создаём.
OPEN_STATUSES = (
    UpdateStatus.REQUESTED,
    UpdateStatus.SCHEDULED,
    UpdateStatus.IN_PROGRESS,
)

# Завершённую и отменённую заявку дальше не двигаем.
# requested можно отменить или поставить на дату; scheduled — начать, отменить или вернуть в запрос.
ALLOWED_TRANSITIONS = {
    UpdateStatus.REQUESTED: {UpdateStatus.SCHEDULED, UpdateStatus.CANCELLED},
    UpdateStatus.SCHEDULED: {UpdateStatus.IN_PROGRESS, UpdateStatus.CANCELLED, UpdateStatus.REQUESTED},
    UpdateStatus.IN_PROGRESS: {UpdateStatus.COMPLETED, UpdateStatus.CANCELLED},
    UpdateStatus.COMPLETED: set(),
    UpdateStatus.CANCELLED: set(),
}

WRITERS = {RoleCode.ADMIN, RoleCode.SPECIALIST}


def update_options(*, with_history: bool = False):
    """Связи заявки. with_history=True добавляет цепочку статусов и автора каждой смены."""
    options = [
        selectinload(ScheduledUpdate.client),
        selectinload(ScheduledUpdate.client_configuration).selectinload(ClientConfiguration.configuration),
        selectinload(ScheduledUpdate.client_configuration).selectinload(ClientConfiguration.installed_version),
        selectinload(ScheduledUpdate.source_version),
        selectinload(ScheduledUpdate.target_version),
        selectinload(ScheduledUpdate.slot).selectinload(UpdateSlot.specialist),
        selectinload(ScheduledUpdate.requested_by_employee),
        selectinload(ScheduledUpdate.requested_by_client_user),
        selectinload(ScheduledUpdate.assigned_specialist),
    ]
    if with_history:
        options.append(
            selectinload(ScheduledUpdate.status_history).selectinload(UpdateStatusHistory.changed_by_employee)
        )
        options.append(
            selectinload(ScheduledUpdate.status_history).selectinload(
                UpdateStatusHistory.changed_by_client_user
            )
        )
    return options


async def get_scheduled_update(
    session: AsyncSession,
    update_id: UUID,
    *,
    with_history: bool = False,
) -> ScheduledUpdate:
    """Заявка по id. populate_existing обновляет уже лежащий в сессии объект."""
    row = await session.scalar(
        select(ScheduledUpdate)
        .where(ScheduledUpdate.id == update_id)
        .options(*update_options(with_history=with_history))
        .execution_options(populate_existing=True)
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Scheduled update not found")
    return row


def ensure_can_view(user: Account, row: ScheduledUpdate) -> None:
    """Клиент видит только заявки своей организации."""
    ensure_client_scope(user, row.client_id)


def ensure_can_book(user: Account, installation: ClientConfiguration) -> None:
    """Дату выбирает клиент для себя или специалист/администратор. Руководитель только смотрит."""
    if actor_role(user) == RoleCode.CLIENT:
        ensure_client_scope(user, installation.client_id)
        return
    if actor_role(user) not in WRITERS:
        raise HTTPException(status_code=403, detail="Insufficient permissions")


async def booked_count(
    session: AsyncSession,
    slot_id: UUID,
    *,
    ignore_update_id: UUID | None = None,
) -> int:
    """Сколько неотменённых заявок уже стоят на слот. ignore_update_id не считает саму заявку."""
    stmt = select(func.count()).select_from(ScheduledUpdate).where(
        ScheduledUpdate.slot_id == slot_id,
        ScheduledUpdate.status != UpdateStatus.CANCELLED,
    )
    if ignore_update_id is not None:
        stmt = stmt.where(ScheduledUpdate.id != ignore_update_id)
    return int(await session.scalar(stmt) or 0)


def slot_is_past(slot: UpdateSlot, today: date | None = None, now: time | None = None) -> bool:
    """Окно в прошлом дне или уже закончившееся сегодня."""
    today = today or date.today()
    now = now or datetime.now().time()
    if slot.slot_date < today:
        return True
    if slot.slot_date == today and slot.end_time <= now:
        return True
    return False


async def lock_slot(session: AsyncSession, slot_id: UUID) -> UpdateSlot:
    """Блокирует строку слота, чтобы два запроса не заняли последнее место."""
    slot = (
        await session.execute(select(UpdateSlot).where(UpdateSlot.id == slot_id).with_for_update())
    ).scalar_one_or_none()
    if slot is None:
        raise HTTPException(status_code=404, detail="Update slot not found")
    return slot


async def ensure_slot_available(
    session: AsyncSession,
    slot: UpdateSlot,
    *,
    ignore_update_id: UUID | None = None,
) -> None:
    """Слот активен, не в прошлом и ещё есть место."""
    if not slot.is_active:
        raise HTTPException(status_code=409, detail="Slot is not active")
    if slot_is_past(slot):
        raise HTTPException(status_code=409, detail="Slot is in the past")
    booked = await booked_count(session, slot.id, ignore_update_id=ignore_update_id)
    if booked >= slot.capacity:
        raise HTTPException(status_code=409, detail="Slot is full")


def add_history(
    session: AsyncSession,
    *,
    update: ScheduledUpdate,
    old_status: UpdateStatus | None,
    new_status: UpdateStatus,
    comment: str | None,
    actor: Account,
) -> None:
    """Добавляет строку истории, не трогая уже загруженную коллекцию (иначе ленивая подгрузка в async)."""
    employee_id, client_user_id = author_ids(actor)
    session.add(
        UpdateStatusHistory(
            old_status=old_status,
            new_status=new_status,
            comment=comment,
            scheduled_update_id=update.id,
            changed_by_employee_id=employee_id,
            changed_by_client_user_id=client_user_id,
        )
    )


async def _notify_status(
    session: AsyncSession,
    update: ScheduledUpdate,
    kind: NotificationType,
    actor: Account,
) -> None:
    """Письмо клиенту о дате, выполнении или отмене. Смена на in_progress письмом не сопровождается."""
    installation = update.client_configuration
    config_name = installation.configuration.name
    if kind == NotificationType.UPDATE_SCHEDULED and update.slot is not None:
        slot = update.slot
        title = "Обновление запланировано"
        message = (
            f"Обновление «{config_name}» запланировано на {slot.slot_date.isoformat()} "
            f"{slot.start_time.strftime('%H:%M')}–{slot.end_time.strftime('%H:%M')}."
        )
    elif kind == NotificationType.UPDATE_COMPLETED:
        version = update.target_version.version if update.target_version is not None else ""
        title = "Обновление выполнено"
        message = f"Обновление «{config_name}» выполнено. Установлена версия {version}."
    elif kind == NotificationType.UPDATE_CANCELLED:
        title = "Обновление отменено"
        message = f"Запланированное обновление «{config_name}» отменено."
    else:
        return
    await notify_client_users(
        session,
        client_id=update.client_id,
        type=kind,
        title=title,
        message=message,
        created_by=actor,
        client_configuration_id=update.client_configuration_id,
        scheduled_update_id=update.id,
        strict=False,
    )


async def create_scheduled_update(
    session: AsyncSession,
    *,
    actor: Account,
    client_configuration_id: UUID,
    slot_id: UUID | None,
    comment: str | None,
) -> ScheduledUpdate:
    """Новая заявка. Со слотом статус сразу scheduled, без слота — requested.

    Вторую открытую заявку на ту же установку не создаёт.
    """
    installation = await get_installation(session, client_configuration_id)
    ensure_can_book(actor, installation)
    open_update = await session.scalar(
        select(ScheduledUpdate.id).where(
            ScheduledUpdate.client_configuration_id == installation.id,
            ScheduledUpdate.status.in_(OPEN_STATUSES),
        )
    )
    if open_update is not None:
        raise HTTPException(
            status_code=409,
            detail="An open update already exists for this configuration",
        )
    # Цель фиксируем сейчас: это актуальный релиз каталога, а не «какой появится позже».
    current = await get_current_version(session, installation.configuration_id)
    if current is None:
        raise HTTPException(status_code=422, detail="Configuration has no current version")

    slot = None
    if slot_id is not None:
        slot = await lock_slot(session, slot_id)
        await ensure_slot_available(session, slot)

    assigned_id = None
    if slot is not None:
        assigned_id = slot.specialist_id
    elif installation.client.responsible_employee_id is not None:
        assigned_id = installation.client.responsible_employee_id
    elif actor_role(actor) in WRITERS:
        assigned_id = actor.id

    status = UpdateStatus.SCHEDULED if slot is not None else UpdateStatus.REQUESTED
    employee_id, client_user_id = author_ids(actor)
    row = ScheduledUpdate(
        status=status,
        comment=comment,
        client_id=installation.client_id,
        client_configuration_id=installation.id,
        source_version_id=installation.installed_version_id,
        target_version_id=current.id,
        slot_id=slot.id if slot is not None else None,
        requested_by_employee_id=employee_id,
        requested_by_client_user_id=client_user_id,
        assigned_specialist_id=assigned_id,
    )
    session.add(row)
    await flush_session(session)
    add_history(
        session,
        update=row,
        old_status=None,
        new_status=status,
        comment=comment,
        actor=actor,
    )
    await flush_session(session)
    if slot is not None:
        session.expire(row, ["slot", "target_version", "client_configuration"])
        loaded = await get_scheduled_update(session, row.id)
        await _notify_status(session, loaded, NotificationType.UPDATE_SCHEDULED, actor)
    return row


async def assign_slot(
    session: AsyncSession,
    update: ScheduledUpdate,
    *,
    actor: Account,
    slot_id: UUID,
    comment: str | None = None,
) -> None:
    """Клиент или сотрудник выбирает дату, пока заявка в requested или scheduled."""
    ensure_can_book(actor, update.client_configuration)
    if actor_role(actor) == RoleCode.CLIENT and update.status not in (
        UpdateStatus.REQUESTED,
        UpdateStatus.SCHEDULED,
    ):
        raise HTTPException(status_code=409, detail="The date can no longer be changed")
    if update.status not in (UpdateStatus.REQUESTED, UpdateStatus.SCHEDULED):
        raise HTTPException(
            status_code=409,
            detail="Slot can only be chosen while the update is requested or scheduled",
        )
    slot = await lock_slot(session, slot_id)
    await ensure_slot_available(session, slot, ignore_update_id=update.id)
    old = update.status
    update.slot_id = slot.id
    update.assigned_specialist_id = slot.specialist_id
    if comment is not None:
        update.comment = comment
    if old != UpdateStatus.SCHEDULED:
        update.status = UpdateStatus.SCHEDULED
        add_history(
            session,
            update=update,
            old_status=old,
            new_status=UpdateStatus.SCHEDULED,
            comment=comment,
            actor=actor,
        )
    await flush_session(session)
    session.expire(update, ["slot", "target_version", "client_configuration"])
    loaded = await get_scheduled_update(session, update.id)
    await _notify_status(session, loaded, NotificationType.UPDATE_SCHEDULED, actor)


async def _apply_completion(session: AsyncSession, update: ScheduledUpdate) -> None:
    """Ставит на установку целевой релиз и запоминает, с какой версии ушли."""
    installation = update.client_configuration
    target = update.target_version
    if target is None and update.target_version_id is not None:
        target = await session.get(ConfigurationVersion, update.target_version_id)
    if target is None:
        target = await get_current_version(session, installation.configuration_id)
        if target is None:
            raise HTTPException(status_code=422, detail="No current version is available to install")
        update.target_version_id = target.id
    if update.source_version_id is None:
        # Фиксируем, с какой версии ушли, до того как подменим установленный релиз.
        update.source_version_id = installation.installed_version_id
    installation.installed_version_id = target.id
    update.completed_at = datetime.now(timezone.utc)
    update.target_version = target


async def change_status(
    session: AsyncSession,
    update: ScheduledUpdate,
    *,
    actor: Account,
    new_status: UpdateStatus,
    comment: str | None,
) -> None:
    """Переход по таблице ALLOWED_TRANSITIONS. Завершение вызывает _apply_completion."""
    if actor_role(actor) not in WRITERS:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    old = update.status
    if new_status == old:
        raise HTTPException(status_code=422, detail="Status is unchanged")
    if new_status not in ALLOWED_TRANSITIONS[old]:
        raise HTTPException(
            status_code=409,
            detail=f"Transition {old.value} -> {new_status.value} is not allowed",
        )
    if new_status == UpdateStatus.SCHEDULED:
        if update.slot_id is None:
            raise HTTPException(status_code=422, detail="Choose a slot before scheduling")
        slot = await lock_slot(session, update.slot_id)
        await ensure_slot_available(session, slot, ignore_update_id=update.id)
        update.assigned_specialist_id = slot.specialist_id
    if new_status == UpdateStatus.REQUESTED:
        # Возврат в «запрошено» отпускает окно, иначе место останется занятым.
        update.slot_id = None
    if new_status == UpdateStatus.COMPLETED:
        await _apply_completion(session, update)
    if comment is not None:
        update.comment = comment
    update.status = new_status
    add_history(
        session,
        update=update,
        old_status=old,
        new_status=new_status,
        comment=comment,
        actor=actor,
    )
    await flush_session(session)
    if new_status in (
        UpdateStatus.SCHEDULED,
        UpdateStatus.COMPLETED,
        UpdateStatus.CANCELLED,
    ):
        # Сбрасываем связи: иначе в письме останется старый слот или старая версия из кэша сессии.
        session.expire(update, ["slot", "target_version", "client_configuration"])
        loaded = await get_scheduled_update(session, update.id)
        kind = {
            UpdateStatus.SCHEDULED: NotificationType.UPDATE_SCHEDULED,
            UpdateStatus.COMPLETED: NotificationType.UPDATE_COMPLETED,
            UpdateStatus.CANCELLED: NotificationType.UPDATE_CANCELLED,
        }[new_status]
        await _notify_status(session, loaded, kind, actor)

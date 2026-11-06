"""Доступные даты, выбор даты клиентом и смена статуса заявки сотрудником."""

from collections import defaultdict
from datetime import date, datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from src.api.deps import CurrentUser, Db, PageDep, WriterUser
from src.api.schemas import (
    AvailableDate,
    Page,
    ScheduledUpdateCreate,
    ScheduledUpdateDetail,
    ScheduledUpdatePatch,
    ScheduledUpdateRead,
    SlotCreate,
    SlotRead,
    SlotUpdate,
    StatusChange,
)
from src.api.serializers import scheduled_update_detail, scheduled_update_read, slot_read
from src.data.models import (
    Client,
    RoleCode,
    ScheduledUpdate,
    UpdateSlot,
    UpdateStatus,
    User,
)
from src.services.common import (
    actor_client_id,
    actor_role,
    commit_session,
    count_rows,
    ensure_client_scope,
    flush_session,
    like_pattern,
)
from src.services.planning import (
    assign_slot,
    booked_count,
    change_status,
    create_scheduled_update,
    ensure_can_view,
    get_scheduled_update,
    slot_is_past,
)

slots = APIRouter(prefix="/update-slots", tags=["planning"])
updates = APIRouter(prefix="/scheduled-updates", tags=["planning"])


def _slot_query():
    """Слот и число неотменённых заявок на нём."""
    booked = (
        select(ScheduledUpdate.slot_id.label("slot_id"), func.count().label("booked"))
        .where(
            ScheduledUpdate.slot_id.is_not(None),
            ScheduledUpdate.status != UpdateStatus.CANCELLED,
        )
        .group_by(ScheduledUpdate.slot_id)
        .subquery()
    )
    stmt = (
        select(UpdateSlot, func.coalesce(booked.c.booked, 0))
        .outerjoin(booked, booked.c.slot_id == UpdateSlot.id)
    )
    return stmt, booked


async def _owner_for_create(session, actor: User, specialist_id: UUID | None) -> User:
    """Специалист создаёт окно себе. Администратор обязан передать specialist_id."""
    if actor_role(actor) == RoleCode.SPECIALIST:
        owner_id = actor.id
    elif specialist_id is None:
        raise HTTPException(status_code=422, detail="specialist_id is required")
    else:
        owner_id = specialist_id
    owner = await session.scalar(
        select(User).where(User.id == owner_id).options(selectinload(User.role))
    )
    if owner is None or not owner.is_active or owner.role.code != RoleCode.SPECIALIST:
        raise HTTPException(status_code=422, detail="Slot must belong to an active support specialist")
    return owner


@slots.post("", response_model=SlotRead, status_code=201, summary="4.1 Open a date for updates")
async def create_slot(payload: SlotCreate, actor: WriterUser, session: Db) -> SlotRead:
    """Новое окно. Повтор того же начала у того же специалиста — 409."""
    owner = await _owner_for_create(session, actor, payload.specialist_id)
    duplicate = await session.scalar(
        select(UpdateSlot.id).where(
            UpdateSlot.specialist_id == owner.id,
            UpdateSlot.slot_date == payload.slot_date,
            UpdateSlot.start_time == payload.start_time,
        )
    )
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="This specialist already has a slot at that time")
    row = UpdateSlot(
        slot_date=payload.slot_date,
        start_time=payload.start_time,
        end_time=payload.end_time,
        capacity=payload.capacity,
        is_active=True,
        specialist_id=owner.id,
    )
    session.add(row)
    await flush_session(session)
    await commit_session(session)
    loaded = await session.scalar(
        select(UpdateSlot).where(UpdateSlot.id == row.id).options(selectinload(UpdateSlot.specialist))
    )
    return slot_read(loaded, 0)


@slots.get("/dates", response_model=list[AvailableDate], summary="4.1 Available dates")
async def available_dates(
    actor: CurrentUser,
    session: Db,
    date_from: date | None = None,
    date_to: date | None = None,
) -> list[AvailableDate]:
    """Даты, на которые ещё есть свободные места. Клиент видит только такие."""
    page = await _list_slots(
        session,
        actor=actor,
        available_only=True,
        date_from=date_from or date.today(),
        date_to=date_to,
        limit=500,
        offset=0,
        specialist_id=None,
        is_active=True,
    )
    grouped: dict[date, dict[str, int]] = defaultdict(lambda: {"open_slots": 0, "remaining_capacity": 0})
    for item in page.items:
        if item.remaining <= 0:
            continue
        bucket = grouped[item.slot_date]
        bucket["open_slots"] += 1
        bucket["remaining_capacity"] += item.remaining
    return [
        AvailableDate(slot_date=slot_date, **values)
        for slot_date, values in sorted(grouped.items())
    ]


@slots.get("", response_model=Page[SlotRead], summary="4.1 List update slots")
async def list_slots(
    actor: CurrentUser,
    session: Db,
    page: PageDep,
    available_only: bool = False,
    date_from: date | None = None,
    date_to: date | None = None,
    specialist_id: UUID | None = None,
    is_active: bool | None = None,
) -> Page[SlotRead]:
    """Список окон. Клиенту принудительно включается available_only."""
    return await _list_slots(
        session,
        actor=actor,
        available_only=available_only,
        date_from=date_from,
        date_to=date_to,
        limit=page.limit,
        offset=page.offset,
        specialist_id=specialist_id,
        is_active=is_active,
    )


async def _list_slots(
    session,
    *,
    actor: User,
    available_only: bool,
    date_from: date | None,
    date_to: date | None,
    limit: int,
    offset: int,
    specialist_id: UUID | None,
    is_active: bool | None,
) -> Page[SlotRead]:
    """Общая выборка окон для списка и для сводки дат."""
    if actor_role(actor) == RoleCode.CLIENT:
        available_only = True
        is_active = True
    stmt, booked = _slot_query()
    if specialist_id is not None:
        stmt = stmt.where(UpdateSlot.specialist_id == specialist_id)
    if is_active is not None:
        stmt = stmt.where(UpdateSlot.is_active.is_(is_active))
    if date_from is not None:
        stmt = stmt.where(UpdateSlot.slot_date >= date_from)
    if date_to is not None:
        stmt = stmt.where(UpdateSlot.slot_date <= date_to)
    if available_only:
        today = date.today()
        now = datetime.now().time()
        stmt = stmt.where(UpdateSlot.is_active.is_(True))
        stmt = stmt.where(
            or_(
                UpdateSlot.slot_date > today,
                (UpdateSlot.slot_date == today) & (UpdateSlot.end_time > now),
            )
        )
        stmt = stmt.where(func.coalesce(booked.c.booked, 0) < UpdateSlot.capacity)
        if date_from is None:
            stmt = stmt.where(UpdateSlot.slot_date >= today)
    total = await count_rows(session, stmt)
    rows = (
        await session.execute(
            stmt.order_by(UpdateSlot.slot_date, UpdateSlot.start_time)
            .limit(limit)
            .offset(offset)
            .options(selectinload(UpdateSlot.specialist))
        )
    ).all()
    return Page(
        items=[slot_read(slot, int(count)) for slot, count in rows],
        total=total,
        limit=limit,
        offset=offset,
    )


@slots.get("/{slot_id}", response_model=SlotRead, summary="4.1 Get a slot")
async def read_slot(slot_id: UUID, actor: CurrentUser, session: Db) -> SlotRead:
    """Одно окно. Клиенту прошедшее или полное окно выглядит как 404."""
    slot = await session.scalar(
        select(UpdateSlot).where(UpdateSlot.id == slot_id).options(selectinload(UpdateSlot.specialist))
    )
    if slot is None:
        raise HTTPException(status_code=404, detail="Update slot not found")
    booked = await booked_count(session, slot.id)
    if actor_role(actor) == RoleCode.CLIENT and (not slot.is_active or slot_is_past(slot) or booked >= slot.capacity):
        raise HTTPException(status_code=404, detail="Update slot not found")
    return slot_read(slot, booked)


@slots.patch("/{slot_id}", response_model=SlotRead, summary="4.1 Change slot capacity or availability")
async def update_slot(slot_id: UUID, payload: SlotUpdate, actor: WriterUser, session: Db) -> SlotRead:
    """Вместимость и флаг активности. Вместимость нельзя опустить ниже уже занятых мест."""
    slot = await session.scalar(
        select(UpdateSlot).where(UpdateSlot.id == slot_id).options(selectinload(UpdateSlot.specialist))
    )
    if slot is None:
        raise HTTPException(status_code=404, detail="Update slot not found")
    if actor_role(actor) == RoleCode.SPECIALIST and slot.specialist_id != actor.id:
        raise HTTPException(status_code=403, detail="You can only change your own slots")
    if payload.capacity is not None:
        taken = await booked_count(session, slot.id)
        if payload.capacity < taken:
            raise HTTPException(status_code=422, detail="Capacity is below the number of bookings")
        slot.capacity = payload.capacity
    if payload.is_active is not None:
        slot.is_active = payload.is_active
    await flush_session(session)
    await commit_session(session)
    fresh = await session.scalar(
        select(UpdateSlot).where(UpdateSlot.id == slot.id).options(selectinload(UpdateSlot.specialist))
    )
    return slot_read(fresh, await booked_count(session, fresh.id))


def _update_filters(stmt, *, status, client_id, date_from, date_to, assigned_specialist_id, q):
    """Фильтры списка заявок: статус, клиент, специалист, дата слота, подстрока названия."""
    stmt = stmt.join(Client, Client.id == ScheduledUpdate.client_id)
    if status is not None:
        stmt = stmt.where(ScheduledUpdate.status == status)
    if client_id is not None:
        stmt = stmt.where(ScheduledUpdate.client_id == client_id)
    if assigned_specialist_id is not None:
        stmt = stmt.where(ScheduledUpdate.assigned_specialist_id == assigned_specialist_id)
    if q and q.strip():
        stmt = stmt.where(Client.company_name.ilike(like_pattern(q.strip()), escape="\\"))
    if date_from is not None or date_to is not None:
        stmt = stmt.outerjoin(UpdateSlot, UpdateSlot.id == ScheduledUpdate.slot_id)
        if date_from is not None:
            stmt = stmt.where(UpdateSlot.slot_date >= date_from)
        if date_to is not None:
            stmt = stmt.where(UpdateSlot.slot_date <= date_to)
    return stmt


@updates.post("", response_model=ScheduledUpdateDetail, status_code=201, summary="4.2 Pick a date or request an update")
async def create_update(payload: ScheduledUpdateCreate, actor: CurrentUser, session: Db) -> ScheduledUpdateDetail:
    """Заявка. slot_id сразу ставит статус scheduled."""
    row = await create_scheduled_update(
        session,
        actor=actor,
        client_configuration_id=payload.client_configuration_id,
        slot_id=payload.slot_id,
        comment=payload.comment,
    )
    update_id = row.id
    await commit_session(session)
    return scheduled_update_detail(await get_scheduled_update(session, update_id, with_history=True))


@updates.get("", response_model=Page[ScheduledUpdateRead], summary="4.3 List planned updates")
async def list_updates(
    actor: CurrentUser,
    session: Db,
    page: PageDep,
    status: UpdateStatus | None = None,
    client_id: UUID | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    assigned_specialist_id: UUID | None = None,
    q: str | None = Query(default=None, max_length=255),
) -> Page[ScheduledUpdateRead]:
    """Список заявок. Клиент видит только свои."""
    if actor_role(actor) == RoleCode.CLIENT:
        if client_id is not None:
            ensure_client_scope(actor, client_id)
        client_id = actor_client_id(actor)
        if client_id is None:
            return Page(items=[], total=0, limit=page.limit, offset=page.offset)
    stmt = _update_filters(
        select(ScheduledUpdate),
        status=status,
        client_id=client_id,
        date_from=date_from,
        date_to=date_to,
        assigned_specialist_id=assigned_specialist_id,
        q=q,
    )
    total = await count_rows(session, stmt)
    from src.services.planning import update_options

    rows = list(
        (
            await session.scalars(
                stmt.options(*update_options())
                .order_by(ScheduledUpdate.created_at.desc())
                .limit(page.limit)
                .offset(page.offset)
            )
        ).all()
    )
    return Page(
        items=[scheduled_update_read(row) for row in rows],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@updates.get("/{update_id}", response_model=ScheduledUpdateDetail, summary="4.3–4.4 View an update and its status history")
async def read_update(update_id: UUID, actor: CurrentUser, session: Db) -> ScheduledUpdateDetail:
    """Заявка и история статусов."""
    row = await get_scheduled_update(session, update_id, with_history=True)
    ensure_can_view(actor, row)
    return scheduled_update_detail(row)


@updates.patch("/{update_id}", response_model=ScheduledUpdateDetail, summary="4.2 Change the chosen date")
async def patch_update(
    update_id: UUID,
    payload: ScheduledUpdatePatch,
    actor: CurrentUser,
    session: Db,
) -> ScheduledUpdateDetail:
    """Смена выбранной даты или комментария, пока работу ещё не начали."""
    row = await get_scheduled_update(session, update_id, with_history=True)
    ensure_can_view(actor, row)
    if payload.slot_id is None and payload.comment is None:
        raise HTTPException(status_code=422, detail="Nothing to update")
    if payload.slot_id is not None:
        await assign_slot(session, row, actor=actor, slot_id=payload.slot_id, comment=payload.comment)
    elif payload.comment is not None:
        if actor_role(actor) == RoleCode.MANAGER:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        row.comment = payload.comment
        await flush_session(session)
    await commit_session(session)
    return scheduled_update_detail(await get_scheduled_update(session, update_id, with_history=True))


@updates.patch("/{update_id}/status", response_model=ScheduledUpdateDetail, summary="4.4 Change update status")
async def patch_status(
    update_id: UUID,
    payload: StatusChange,
    actor: WriterUser,
    session: Db,
) -> ScheduledUpdateDetail:
    """Смена статуса сотрудником сопровождения."""
    row = await get_scheduled_update(session, update_id, with_history=True)
    await change_status(session, row, actor=actor, new_status=payload.status, comment=payload.comment)
    await commit_session(session)
    return scheduled_update_detail(await get_scheduled_update(session, update_id, with_history=True))

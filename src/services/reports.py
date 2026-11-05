from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import and_, cast, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload
from sqlalchemy.sql.sqltypes import Date

from src.api.schemas import (
    UpdateBrief,
    UpdatedClientReport,
    UpdatedClientsReport,
    UpdatedConfigurationReport,
    UpdatesReport,
)
from src.api.serializers import update_brief
from src.data.models import (
    Client,
    ClientConfiguration,
    ScheduledUpdate,
    UpdateSlot,
    UpdateStatus,
)
from src.services.common import like_pattern

PLANNED = (UpdateStatus.REQUESTED, UpdateStatus.SCHEDULED, UpdateStatus.IN_PROGRESS)


def _completed_bounds(date_from: date | None, date_to: date | None) -> list:
    conds = []
    if date_from is not None:
        conds.append(
            ScheduledUpdate.completed_at
            >= datetime.combine(date_from, time.min, tzinfo=timezone.utc)
        )
    if date_to is not None:
        conds.append(
            ScheduledUpdate.completed_at
            < datetime.combine(date_to + timedelta(days=1), time.min, tzinfo=timezone.utc)
        )
    return conds


async def updated_clients_report(
    session: AsyncSession,
    *,
    date_from: date | None,
    date_to: date | None,
    q: str | None,
) -> UpdatedClientsReport:
    stmt = (
        select(ScheduledUpdate)
        .join(Client, Client.id == ScheduledUpdate.client_id)
        .where(ScheduledUpdate.status == UpdateStatus.COMPLETED)
        .options(
            selectinload(ScheduledUpdate.client),
            selectinload(ScheduledUpdate.client_configuration).selectinload(ClientConfiguration.configuration),
            selectinload(ScheduledUpdate.source_version),
            selectinload(ScheduledUpdate.target_version),
            selectinload(ScheduledUpdate.assigned_specialist),
        )
        .order_by(ScheduledUpdate.completed_at.desc())
    )
    for cond in _completed_bounds(date_from, date_to):
        stmt = stmt.where(cond)
    if q and q.strip():
        stmt = stmt.where(Client.company_name.ilike(like_pattern(q.strip()), escape="\\"))
    rows = list((await session.scalars(stmt)).unique().all())
    grouped: dict = {}
    for row in rows:
        bucket = grouped.get(row.client_id)
        if bucket is None:
            bucket = UpdatedClientReport(
                client_id=row.client_id,
                company_name=row.client.company_name,
                updates=[],
            )
            grouped[row.client_id] = bucket
        bucket.updates.append(
            UpdatedConfigurationReport(
                scheduled_update_id=row.id,
                client_configuration_id=row.client_configuration_id,
                configuration_name=row.client_configuration.configuration.name,
                source_version=row.source_version.version if row.source_version is not None else None,
                target_version=row.target_version.version if row.target_version is not None else None,
                completed_at=row.completed_at,
                assigned_specialist_name=(
                    row.assigned_specialist.full_name if row.assigned_specialist is not None else None
                ),
            )
        )
    return UpdatedClientsReport(
        date_from=date_from,
        date_to=date_to,
        total_clients=len(grouped),
        total_updates=len(rows),
        clients=list(grouped.values()),
    )


async def updates_summary(
    session: AsyncSession,
    *,
    date_from: date | None,
    date_to: date | None,
    q: str | None,
) -> UpdatesReport:
    slot_or_created = func.coalesce(UpdateSlot.slot_date, cast(ScheduledUpdate.created_at, Date))
    stmt = (
        select(ScheduledUpdate)
        .join(Client, Client.id == ScheduledUpdate.client_id)
        .outerjoin(UpdateSlot, UpdateSlot.id == ScheduledUpdate.slot_id)
        .options(
            selectinload(ScheduledUpdate.client),
            selectinload(ScheduledUpdate.client_configuration).selectinload(ClientConfiguration.configuration),
            selectinload(ScheduledUpdate.slot),
        )
        .order_by(ScheduledUpdate.created_at.desc())
    )
    if q and q.strip():
        stmt = stmt.where(Client.company_name.ilike(like_pattern(q.strip()), escape="\\"))
    if date_from is not None or date_to is not None:
        other = []
        if date_from is not None:
            other.append(slot_or_created >= date_from)
        if date_to is not None:
            other.append(slot_or_created <= date_to)
        completed = _completed_bounds(date_from, date_to)
        stmt = stmt.where(
            or_(
                and_(ScheduledUpdate.status == UpdateStatus.COMPLETED, *completed),
                and_(ScheduledUpdate.status != UpdateStatus.COMPLETED, *other),
            )
        )
    rows = list((await session.scalars(stmt)).unique().all())
    by_status = {status.value: 0 for status in UpdateStatus}
    planned: list[UpdateBrief] = []
    completed: list[UpdateBrief] = []
    for row in rows:
        by_status[row.status.value] = by_status.get(row.status.value, 0) + 1
        brief = update_brief(row)
        if row.status == UpdateStatus.COMPLETED:
            completed.append(brief)
        elif row.status in PLANNED:
            planned.append(brief)
    planned.sort(key=lambda item: (item.slot_date is None, item.slot_date or date.min, item.created_at))
    return UpdatesReport(
        date_from=date_from,
        date_to=date_to,
        planned_count=sum(by_status[status.value] for status in PLANNED),
        completed_count=by_status[UpdateStatus.COMPLETED.value],
        cancelled_count=by_status[UpdateStatus.CANCELLED.value],
        by_status=by_status,
        planned=planned,
        completed=completed,
    )

"""Запуск проверки версий, история проверок и список тех, кому пора обновляться."""

from datetime import date, datetime, time, timedelta, timezone
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from src.api.deps import CurrentUser, Db, PageDep, StaffUser, WriterUser
from src.api.schemas import Page, RunChecksRequest, RunChecksResponse, SkippedCheck, VersionCheckRead
from src.api.serializers import version_check_read
from src.data.models import ClientConfiguration, RoleCode, VersionCheck
from src.services.catalog import get_client
from src.services.checks import check_load_options, load_checks, outdated_report, run_version_checks
from src.services.common import actor_role, commit_session, count_rows, ensure_client_scope

router = APIRouter(prefix="/version-checks", tags=["version-checks"])


def _day_start(value: date) -> datetime:
    """Начало календарного дня в UTC для фильтра истории."""
    return datetime.combine(value, time.min, tzinfo=timezone.utc)


@router.post("/run", response_model=RunChecksResponse, status_code=201, summary="2.1 Compare installed and current versions")
async def run_checks(payload: RunChecksRequest, actor: WriterUser, session: Db) -> RunChecksResponse:
    """Запуск сравнения. Пустое тело проверяет все установки."""
    if actor_role(actor) == RoleCode.CLIENT:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    created, skipped = await run_version_checks(
        session,
        actor,
        client_id=payload.client_id,
        client_configuration_id=payload.client_configuration_id,
    )
    await commit_session(session)
    loaded = await load_checks(session, created)
    return RunChecksResponse(
        created=[version_check_read(row) for row in loaded],
        skipped=[SkippedCheck.model_validate(item) for item in skipped],
    )


@router.get("/outdated", summary="2.2 Clients whose configurations need an update")
async def list_outdated(
    actor: StaffUser,
    session: Db,
    q: str | None = Query(default=None, max_length=255),
    client_id: UUID | None = None,
):
    """Клиенты, у которых установленный релиз не актуален. Считается по каталогу, а не по архиву."""
    if client_id is not None:
        await get_client(session, client_id)
    return await outdated_report(session, q=q, client_id=client_id)


@router.get("", response_model=Page[VersionCheckRead], summary="2.3 Version check history")
async def list_checks(
    _actor: StaffUser,
    session: Db,
    page: PageDep,
    client_id: UUID | None = None,
    client_configuration_id: UUID | None = None,
    is_outdated: bool | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
) -> Page[VersionCheckRead]:
    """Архив проверок с фильтрами."""
    stmt = select(VersionCheck).join(
        ClientConfiguration,
        ClientConfiguration.id == VersionCheck.client_configuration_id,
    )
    if client_configuration_id is not None:
        stmt = stmt.where(VersionCheck.client_configuration_id == client_configuration_id)
    if client_id is not None:
        stmt = stmt.where(ClientConfiguration.client_id == client_id)
    if is_outdated is not None:
        stmt = stmt.where(VersionCheck.is_outdated.is_(is_outdated))
    if date_from is not None:
        stmt = stmt.where(VersionCheck.checked_at >= _day_start(date_from))
    if date_to is not None:
        stmt = stmt.where(VersionCheck.checked_at < _day_start(date_to + timedelta(days=1)))
    total = await count_rows(session, stmt)
    rows = list(
        (
            await session.scalars(
                stmt.options(*check_load_options())
                .order_by(VersionCheck.checked_at.desc())
                .limit(page.limit)
                .offset(page.offset)
            )
        ).all()
    )
    return Page(
        items=[version_check_read(row) for row in rows],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/{check_id}", response_model=VersionCheckRead, summary="2.3 One saved version check")
async def read_check(check_id: UUID, actor: CurrentUser, session: Db) -> VersionCheckRead:
    """Одна сохранённая проверка."""
    row = await session.scalar(
        select(VersionCheck).where(VersionCheck.id == check_id).options(*check_load_options())
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Version check not found")
    if actor_role(actor) == RoleCode.CLIENT:
        ensure_client_scope(actor, row.client_configuration.client_id)
    elif actor_role(actor) not in (RoleCode.ADMIN, RoleCode.SPECIALIST, RoleCode.MANAGER):
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return version_check_read(row)

from datetime import date
from uuid import UUID

from fastapi import APIRouter, Query

from src.api.deps import Db, ReportUser
from src.api.schemas import OutdatedReport, UpdatedClientsReport, UpdatesReport
from src.services.catalog import get_client
from src.services.checks import outdated_report
from src.services.reports import updated_clients_report, updates_summary

router = APIRouter(prefix="/reports", tags=["reports"])


@router.get("/updated-clients", response_model=UpdatedClientsReport, summary="5.1 Clients whose configurations were updated")
async def updated_clients(
    _actor: ReportUser,
    session: Db,
    date_from: date | None = None,
    date_to: date | None = None,
    q: str | None = Query(default=None, max_length=255),
) -> UpdatedClientsReport:
    return await updated_clients_report(session, date_from=date_from, date_to=date_to, q=q)


@router.get("/updates", response_model=UpdatesReport, summary="5.2 Completed and planned updates")
async def updates(
    _actor: ReportUser,
    session: Db,
    date_from: date | None = None,
    date_to: date | None = None,
    q: str | None = Query(default=None, max_length=255),
) -> UpdatesReport:
    return await updates_summary(session, date_from=date_from, date_to=date_to, q=q)


@router.get("/outdated-clients", response_model=OutdatedReport, summary="Clients with outdated configurations")
async def outdated_clients(
    _actor: ReportUser,
    session: Db,
    q: str | None = Query(default=None, max_length=255),
    client_id: UUID | None = None,
) -> OutdatedReport:
    if client_id is not None:
        await get_client(session, client_id)
    return await outdated_report(session, q=q, client_id=client_id)

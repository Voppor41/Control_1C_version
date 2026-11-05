from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from src.api.deps import CurrentUser, Db, PageDep, WriterUser
from src.api.schemas import (
    ClientConfigurationCreate,
    ClientConfigurationRead,
    ClientConfigurationUpdate,
    Page,
)
from src.api.serializers import installation_read
from src.data.models import Client, ClientConfiguration, Configuration, ConfigurationVersion, RoleCode, ScheduledUpdate
from src.services.catalog import (
    ensure_version_of_configuration,
    get_client,
    get_configuration,
    get_installation,
    installation_options,
    map_current_versions,
    map_last_checks,
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

router = APIRouter(prefix="/client-configurations", tags=["installations"])
nested = APIRouter(prefix="/clients", tags=["installations"])


async def _to_reads(session: AsyncSession, rows: list[ClientConfiguration]) -> list[ClientConfigurationRead]:
    currents = await map_current_versions(session, {row.configuration_id for row in rows})
    checks = await map_last_checks(session, {row.id for row in rows})
    return [
        installation_read(row, currents.get(row.configuration_id), checks.get(row.id)) for row in rows
    ]


async def list_installations(
    session: AsyncSession,
    *,
    actor,
    page_limit: int,
    page_offset: int,
    client_id: UUID | None = None,
    configuration_id: UUID | None = None,
    outdated: bool | None = None,
    q: str | None = None,
) -> Page[ClientConfigurationRead]:
    if actor_role(actor) == RoleCode.CLIENT:
        if actor_client_id(actor) is None:
            return Page(items=[], total=0, limit=page_limit, offset=page_offset)
        if client_id is not None:
            ensure_client_scope(actor, client_id)
        client_id = actor_client_id(actor)

    stmt = (
        select(ClientConfiguration)
        .join(Client, Client.id == ClientConfiguration.client_id)
        .join(Configuration, Configuration.id == ClientConfiguration.configuration_id)
    )
    if client_id is not None:
        stmt = stmt.where(ClientConfiguration.client_id == client_id)
    if configuration_id is not None:
        stmt = stmt.where(ClientConfiguration.configuration_id == configuration_id)
    if q and q.strip():
        pattern = like_pattern(q.strip())
        stmt = stmt.where(
            or_(
                Client.company_name.ilike(pattern, escape="\\"),
                Configuration.name.ilike(pattern, escape="\\"),
                ClientConfiguration.infobase_name.ilike(pattern, escape="\\"),
            )
        )
    if outdated is not None:
        current_alias = aliased(ConfigurationVersion)
        stmt = stmt.join(
            current_alias,
            and_(
                current_alias.configuration_id == ClientConfiguration.configuration_id,
                current_alias.is_current.is_(True),
            ),
        )
        if outdated:
            stmt = stmt.where(ClientConfiguration.installed_version_id != current_alias.id)
        else:
            stmt = stmt.where(ClientConfiguration.installed_version_id == current_alias.id)
    total = await count_rows(session, stmt)
    rows = list(
        (
            await session.scalars(
                stmt.options(*installation_options())
                .order_by(Client.company_name, Configuration.name)
                .limit(page_limit)
                .offset(page_offset)
            )
        ).all()
    )
    return Page(
        items=await _to_reads(session, rows),
        total=total,
        limit=page_limit,
        offset=page_offset,
    )


@nested.get(
    "/{client_id}/configurations",
    response_model=Page[ClientConfigurationRead],
    summary="1.4 List configurations installed for a client",
)
async def list_client_configurations(
    client_id: UUID,
    actor: CurrentUser,
    session: Db,
    page: PageDep,
    outdated: bool | None = None,
    q: str | None = Query(default=None, max_length=255),
) -> Page[ClientConfigurationRead]:
    ensure_client_scope(actor, client_id)
    await get_client(session, client_id)
    return await list_installations(
        session,
        actor=actor,
        page_limit=page.limit,
        page_offset=page.offset,
        client_id=client_id,
        outdated=outdated,
        q=q,
    )


@nested.post(
    "/{client_id}/configurations",
    response_model=ClientConfigurationRead,
    status_code=201,
    summary="1.3 Store a configuration installed for a client",
)
async def create_installation(
    client_id: UUID,
    payload: ClientConfigurationCreate,
    _actor: WriterUser,
    session: Db,
) -> ClientConfigurationRead:
    await get_client(session, client_id)
    await get_configuration(session, payload.configuration_id)
    await ensure_version_of_configuration(session, payload.installed_version_id, payload.configuration_id)
    existing = await session.scalar(
        select(ClientConfiguration.id).where(
            ClientConfiguration.client_id == client_id,
            ClientConfiguration.configuration_id == payload.configuration_id,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="This client already has that configuration")
    row = ClientConfiguration(
        client_id=client_id,
        configuration_id=payload.configuration_id,
        installed_version_id=payload.installed_version_id,
        infobase_name=payload.infobase_name,
    )
    session.add(row)
    await flush_session(session)
    await commit_session(session)
    fresh = await get_installation(session, row.id)
    return (await _to_reads(session, [fresh]))[0]


@router.get("", response_model=Page[ClientConfigurationRead], summary="1.4 Search installed configurations")
async def search_installations(
    actor: CurrentUser,
    session: Db,
    page: PageDep,
    client_id: UUID | None = None,
    configuration_id: UUID | None = None,
    outdated: bool | None = None,
    q: str | None = Query(default=None, max_length=255),
) -> Page[ClientConfigurationRead]:
    return await list_installations(
        session,
        actor=actor,
        page_limit=page.limit,
        page_offset=page.offset,
        client_id=client_id,
        configuration_id=configuration_id,
        outdated=outdated,
        q=q,
    )


@router.get("/{installation_id}", response_model=ClientConfigurationRead, summary="1.4 Get an installation")
async def read_installation(installation_id: UUID, actor: CurrentUser, session: Db) -> ClientConfigurationRead:
    row = await get_installation(session, installation_id)
    ensure_client_scope(actor, row.client_id)
    return (await _to_reads(session, [row]))[0]


@router.patch("/{installation_id}", response_model=ClientConfigurationRead, summary="1.3 Change the installed version")
async def update_installation(
    installation_id: UUID,
    payload: ClientConfigurationUpdate,
    _actor: WriterUser,
    session: Db,
) -> ClientConfigurationRead:
    row = await get_installation(session, installation_id)
    if payload.installed_version_id is not None:
        await ensure_version_of_configuration(
            session,
            payload.installed_version_id,
            row.configuration_id,
        )
        row.installed_version_id = payload.installed_version_id
    if "infobase_name" in payload.model_fields_set:
        row.infobase_name = payload.infobase_name
    await flush_session(session)
    await commit_session(session)
    fresh = await get_installation(session, row.id)
    return (await _to_reads(session, [fresh]))[0]


@router.delete("/{installation_id}", status_code=204, summary="1.3 Delete an installation without update history")
async def delete_installation(installation_id: UUID, _actor: WriterUser, session: Db) -> Response:
    row = await get_installation(session, installation_id)
    used = await session.scalar(
        select(func.count())
        .select_from(ScheduledUpdate)
        .where(ScheduledUpdate.client_configuration_id == row.id)
    )
    if used:
        raise HTTPException(status_code=409, detail="Cannot delete a configuration that has update history")
    await session.delete(row)
    await commit_session(session)
    return Response(status_code=204)

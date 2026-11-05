from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.deps import CurrentUser, Db, PageDep, WriterUser
from src.api.schemas import (
    ConfigurationCreate,
    ConfigurationDetail,
    ConfigurationRead,
    ConfigurationUpdate,
    Page,
    VersionCreate,
    VersionRead,
    VersionUpdate,
)
from src.api.serializers import configuration_detail, configuration_read
from src.data.models import ClientConfiguration, Configuration, ConfigurationVersion
from src.services.catalog import (
    clear_current,
    get_configuration,
    list_versions,
    map_current_versions,
    touch_current_flag,
    version_reference_count,
)
from src.services.common import commit_session, count_rows, flush_session, like_pattern

router = APIRouter(prefix="/configurations", tags=["configurations"])


async def _reads(session: AsyncSession, rows: list[Configuration]) -> list[ConfigurationRead]:
    currents = await map_current_versions(session, {row.id for row in rows})
    return [
        configuration_read(row, currents[row.id].version if row.id in currents else None) for row in rows
    ]


@router.post("", response_model=ConfigurationRead, status_code=201, summary="1.3 Create a configuration")
async def create_configuration(payload: ConfigurationCreate, _actor: WriterUser, session: Db) -> ConfigurationRead:
    existing = await session.scalar(select(Configuration.id).where(Configuration.name == payload.name))
    if existing is not None:
        raise HTTPException(status_code=409, detail="Configuration with this name already exists")
    row = Configuration(name=payload.name, description=payload.description)
    session.add(row)
    await flush_session(session)
    await commit_session(session)
    return configuration_read(await get_configuration(session, row.id), None)


@router.get("", response_model=Page[ConfigurationRead], summary="1.3 List configurations")
async def list_configurations(
    _actor: CurrentUser,
    session: Db,
    page: PageDep,
    q: str | None = Query(default=None, max_length=255),
) -> Page[ConfigurationRead]:
    stmt = select(Configuration)
    if q and q.strip():
        stmt = stmt.where(Configuration.name.ilike(like_pattern(q.strip()), escape="\\"))
    total = await count_rows(session, stmt)
    rows = list(
        (
            await session.scalars(
                stmt.order_by(Configuration.name).limit(page.limit).offset(page.offset)
            )
        ).all()
    )
    return Page(items=await _reads(session, rows), total=total, limit=page.limit, offset=page.offset)


@router.get("/{configuration_id}", response_model=ConfigurationDetail, summary="1.3 Configuration and its versions")
async def read_configuration(configuration_id: UUID, _actor: CurrentUser, session: Db) -> ConfigurationDetail:
    row = await get_configuration(session, configuration_id)
    return configuration_detail(row, await list_versions(session, row.id))


@router.patch("/{configuration_id}", response_model=ConfigurationDetail, summary="1.3 Update a configuration")
async def update_configuration(
    configuration_id: UUID,
    payload: ConfigurationUpdate,
    _actor: WriterUser,
    session: Db,
) -> ConfigurationDetail:
    row = await get_configuration(session, configuration_id)
    if payload.name is not None:
        row.name = payload.name
    if "description" in payload.model_fields_set:
        row.description = payload.description
    await flush_session(session)
    await commit_session(session)
    fresh = await get_configuration(session, row.id)
    return configuration_detail(fresh, await list_versions(session, fresh.id))


@router.delete("/{configuration_id}", status_code=204, summary="1.3 Delete an unused configuration")
async def delete_configuration(configuration_id: UUID, _actor: WriterUser, session: Db) -> Response:
    row = await get_configuration(session, configuration_id)
    used = await session.scalar(
        select(func.count())
        .select_from(ClientConfiguration)
        .where(ClientConfiguration.configuration_id == row.id)
    )
    if used:
        raise HTTPException(status_code=409, detail="Configuration is installed for a client")
    await session.delete(row)
    await commit_session(session)
    return Response(status_code=204)


@router.post(
    "/{configuration_id}/versions",
    response_model=VersionRead,
    status_code=201,
    summary="1.3 Add a configuration version",
)
async def create_version(
    configuration_id: UUID,
    payload: VersionCreate,
    _actor: WriterUser,
    session: Db,
) -> VersionRead:
    configuration = await get_configuration(session, configuration_id)
    existing = await session.scalar(
        select(ConfigurationVersion.id).where(
            ConfigurationVersion.configuration_id == configuration.id,
            ConfigurationVersion.version == payload.version,
        )
    )
    if existing is not None:
        raise HTTPException(status_code=409, detail="This version already exists")
    versions = await list_versions(session, configuration.id)
    make_current = payload.is_current or not any(item.is_current for item in versions)
    if make_current:
        await clear_current(session, configuration.id)
    row = ConfigurationVersion(
        configuration_id=configuration.id,
        version=payload.version,
        released_at=payload.released_at,
        is_current=make_current,
        notes=payload.notes,
    )
    session.add(row)
    await flush_session(session)
    await commit_session(session)
    fresh = await session.get(ConfigurationVersion, row.id)
    return VersionRead.model_validate(fresh)


@router.patch(
    "/{configuration_id}/versions/{version_id}",
    response_model=VersionRead,
    summary="1.3 Update a version or mark it current",
)
async def update_version(
    configuration_id: UUID,
    version_id: UUID,
    payload: VersionUpdate,
    _actor: WriterUser,
    session: Db,
) -> VersionRead:
    await get_configuration(session, configuration_id)
    version = await session.get(ConfigurationVersion, version_id)
    if version is None or version.configuration_id != configuration_id:
        raise HTTPException(status_code=404, detail="Version not found")
    if "released_at" in payload.model_fields_set:
        version.released_at = payload.released_at
    if "notes" in payload.model_fields_set:
        version.notes = payload.notes
    if payload.is_current is not None:
        await touch_current_flag(session, version, payload.is_current)
    await flush_session(session)
    await commit_session(session)
    fresh = await session.get(ConfigurationVersion, version.id)
    return VersionRead.model_validate(fresh)


@router.delete(
    "/{configuration_id}/versions/{version_id}",
    status_code=204,
    summary="1.3 Delete an unused version",
)
async def delete_version(
    configuration_id: UUID,
    version_id: UUID,
    _actor: WriterUser,
    session: Db,
) -> Response:
    await get_configuration(session, configuration_id)
    version = await session.get(ConfigurationVersion, version_id)
    if version is None or version.configuration_id != configuration_id:
        raise HTTPException(status_code=404, detail="Version not found")
    if await version_reference_count(session, version.id):
        raise HTTPException(status_code=409, detail="Version is referenced and cannot be deleted")
    others = await list_versions(session, configuration_id)
    if version.is_current and any(item.id != version.id for item in others):
        raise HTTPException(
            status_code=422,
            detail="Mark another version as current before deleting this one",
        )
    await session.delete(version)
    await commit_session(session)
    return Response(status_code=204)

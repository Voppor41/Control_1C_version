from datetime import datetime
from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.data.models import (
    Client,
    ClientConfiguration,
    Configuration,
    ConfigurationVersion,
    RoleCode,
    User,
    VersionCheck,
)
from src.services.common import flush_session


async def get_client(session: AsyncSession, client_id: UUID) -> Client:
    client = await session.scalar(
        select(Client)
        .where(Client.id == client_id)
        .options(selectinload(Client.responsible_employee))
    )
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


async def ensure_staff_user(session: AsyncSession, user_id: UUID) -> User:
    user = await session.scalar(
        select(User).where(User.id == user_id).options(selectinload(User.role))
    )
    if user is None or not user.is_active or user.role.code == RoleCode.CLIENT:
        raise HTTPException(
            status_code=422,
            detail="Responsible employee must be an active staff user",
        )
    return user


async def get_configuration(session: AsyncSession, configuration_id: UUID) -> Configuration:
    row = await session.get(Configuration, configuration_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Configuration not found")
    return row


async def list_versions(session: AsyncSession, configuration_id: UUID) -> list[ConfigurationVersion]:
    return list(
        (
            await session.scalars(
                select(ConfigurationVersion)
                .where(ConfigurationVersion.configuration_id == configuration_id)
                .order_by(
                    ConfigurationVersion.released_at.desc().nullslast(),
                    ConfigurationVersion.version.desc(),
                )
            )
        ).all()
    )


async def clear_current(session: AsyncSession, configuration_id: UUID, except_id: UUID | None = None) -> None:
    stmt = update(ConfigurationVersion).where(
        ConfigurationVersion.configuration_id == configuration_id,
        ConfigurationVersion.is_current.is_(True),
    )
    if except_id is not None:
        stmt = stmt.where(ConfigurationVersion.id != except_id)
    await session.execute(stmt.values(is_current=False))
    await session.flush()


async def get_current_version(
    session: AsyncSession,
    configuration_id: UUID,
) -> ConfigurationVersion | None:
    return await session.scalar(
        select(ConfigurationVersion).where(
            ConfigurationVersion.configuration_id == configuration_id,
            ConfigurationVersion.is_current.is_(True),
        )
    )


async def map_current_versions(
    session: AsyncSession,
    configuration_ids: set[UUID],
) -> dict[UUID, ConfigurationVersion]:
    if not configuration_ids:
        return {}
    rows = (
        await session.scalars(
            select(ConfigurationVersion).where(
                ConfigurationVersion.configuration_id.in_(configuration_ids),
                ConfigurationVersion.is_current.is_(True),
            )
        )
    ).all()
    return {row.configuration_id: row for row in rows}


async def map_last_checks(session: AsyncSession, installation_ids: set[UUID]) -> dict[UUID, datetime]:
    if not installation_ids:
        return {}
    rows = (
        await session.execute(
            select(VersionCheck.client_configuration_id, func.max(VersionCheck.checked_at))
            .where(VersionCheck.client_configuration_id.in_(installation_ids))
            .group_by(VersionCheck.client_configuration_id)
        )
    ).all()
    return {installation_id: checked_at for installation_id, checked_at in rows}


def installation_options():
    return (
        selectinload(ClientConfiguration.client),
        selectinload(ClientConfiguration.configuration),
        selectinload(ClientConfiguration.installed_version),
    )


async def get_installation(session: AsyncSession, installation_id: UUID) -> ClientConfiguration:
    row = await session.scalar(
        select(ClientConfiguration)
        .where(ClientConfiguration.id == installation_id)
        .options(*installation_options())
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Client configuration not found")
    return row


async def ensure_version_of_configuration(
    session: AsyncSession,
    version_id: UUID,
    configuration_id: UUID,
) -> ConfigurationVersion:
    version = await session.get(ConfigurationVersion, version_id)
    if version is None or version.configuration_id != configuration_id:
        raise HTTPException(
            status_code=422,
            detail="installed_version_id does not belong to the configuration",
        )
    return version


async def version_reference_count(session: AsyncSession, version_id: UUID) -> int:
    from src.data.models import ScheduledUpdate

    installed = await session.scalar(
        select(func.count())
        .select_from(ClientConfiguration)
        .where(ClientConfiguration.installed_version_id == version_id)
    )
    checks = await session.scalar(
        select(func.count())
        .select_from(VersionCheck)
        .where(
            (VersionCheck.installed_version_id == version_id)
            | (VersionCheck.actual_version_id == version_id)
        )
    )
    updates = await session.scalar(
        select(func.count())
        .select_from(ScheduledUpdate)
        .where(
            (ScheduledUpdate.source_version_id == version_id)
            | (ScheduledUpdate.target_version_id == version_id)
        )
    )
    return int(installed or 0) + int(checks or 0) + int(updates or 0)


async def touch_current_flag(session: AsyncSession, version: ConfigurationVersion, is_current: bool) -> None:
    if is_current:
        await clear_current(session, version.configuration_id, except_id=version.id)
        version.is_current = True
        return
    if version.is_current:
        raise HTTPException(
            status_code=422,
            detail="Mark another version as current before unsetting this one",
        )
    version.is_current = False
    await flush_session(session)

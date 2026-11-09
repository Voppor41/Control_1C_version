"""Сравнение установленной версии с актуальной и список клиентов, которым нужно обновление."""

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from src.api.schemas import OutdatedClient, OutdatedConfiguration, OutdatedReport
from src.data.models import (
    Account,
    Client,
    ClientConfiguration,
    Configuration,
    ConfigurationVersion,
    VersionCheck,
)
from src.services.catalog import get_current_version, installation_options
from src.services.common import flush_session, like_pattern


async def run_version_checks(
    session: AsyncSession,
    actor: Account,
    *,
    client_id: UUID | None,
    client_configuration_id: UUID | None,
) -> tuple[list[VersionCheck], list[dict]]:
    """Сравнивает установки с актуальным релизом и пишет строки в version_checks.

    Параметры:
        client_id: ограничить одним клиентом.
        client_configuration_id: проверить одну установку.

    Возвращает:
        Созданные проверки и установки, у которых нет актуального релиза.
    """
    stmt = select(ClientConfiguration).options(*installation_options())
    if client_configuration_id is not None:
        stmt = stmt.where(ClientConfiguration.id == client_configuration_id)
    elif client_id is not None:
        stmt = stmt.where(ClientConfiguration.client_id == client_id)
    rows = list((await session.scalars(stmt)).all())
    if client_configuration_id is not None and not rows:
        raise HTTPException(status_code=404, detail="Client configuration not found")
    if client_id is not None and not rows:
        exists = await session.get(Client, client_id)
        if exists is None:
            raise HTTPException(status_code=404, detail="Client not found")

    created: list[VersionCheck] = []
    skipped: list[dict] = []
    for installation in rows:
        current = await get_current_version(session, installation.configuration_id)
        if current is None:
            skipped.append(
                {
                    "client_configuration_id": installation.id,
                    "reason": "Configuration has no current version",
                }
            )
            continue
        check = VersionCheck(
            client_configuration_id=installation.id,
            installed_version_id=installation.installed_version_id,
            actual_version_id=current.id,
            # Номера сравниваем по записи релиза, а не по тексту: актуальным считается is_current.
            is_outdated=installation.installed_version_id != current.id,
            checked_by_id=actor.id,
        )
        session.add(check)
        created.append(check)
    if created:
        await flush_session(session)
    return created, skipped


def check_load_options():
    """Связи, нужные карточке проверки: клиент, конфигурация, обе версии, автор."""
    return (
        selectinload(VersionCheck.client_configuration).selectinload(ClientConfiguration.client),
        selectinload(VersionCheck.client_configuration).selectinload(ClientConfiguration.configuration),
        selectinload(VersionCheck.installed_version),
        selectinload(VersionCheck.actual_version),
        selectinload(VersionCheck.checked_by),
    )


async def load_checks(session: AsyncSession, checks: list[VersionCheck]) -> list[VersionCheck]:
    """Перечитывает только что созданные проверки со связями."""
    if not checks:
        return []
    ids = [item.id for item in checks]
    return list(
        (
            await session.scalars(
                select(VersionCheck)
                .where(VersionCheck.id.in_(ids))
                .options(*check_load_options())
                .order_by(VersionCheck.checked_at.desc())
            )
        ).all()
    )


async def outdated_report(
    session: AsyncSession,
    *,
    q: str | None = None,
    client_id: UUID | None = None,
) -> OutdatedReport:
    """Живое сравнение, не архив проверок: установленный id релиза не равен актуальному.

    Параметры:
        q: подстрока названия клиента, конфигурации или базы.
        client_id: один клиент.
    """
    current_version = aliased(ConfigurationVersion)
    installed_version = aliased(ConfigurationVersion)
    stmt = (
        select(Client, ClientConfiguration, Configuration, installed_version, current_version)
        .join(ClientConfiguration, ClientConfiguration.client_id == Client.id)
        .join(Configuration, Configuration.id == ClientConfiguration.configuration_id)
        .join(installed_version, installed_version.id == ClientConfiguration.installed_version_id)
        .join(
            current_version,
            and_(
                current_version.configuration_id == ClientConfiguration.configuration_id,
                current_version.is_current.is_(True),
            ),
        )
        # Живой список «кому пора»: установленный релиз не тот, что помечен актуальным.
        .where(ClientConfiguration.installed_version_id != current_version.id)
        .order_by(Client.company_name, Configuration.name)
    )
    if client_id is not None:
        stmt = stmt.where(Client.id == client_id)
    if q and q.strip():
        pattern = like_pattern(q.strip())
        stmt = stmt.where(
            or_(
                Client.company_name.ilike(pattern, escape="\\"),
                Configuration.name.ilike(pattern, escape="\\"),
                ClientConfiguration.infobase_name.ilike(pattern, escape="\\"),
            )
        )
    rows = (await session.execute(stmt)).all()
    grouped: dict[UUID, OutdatedClient] = {}
    total_configurations = 0
    for client, installation, configuration, installed_row, current_row in rows:
        bucket = grouped.get(client.id)
        if bucket is None:
            bucket = OutdatedClient(
                client_id=client.id,
                company_name=client.company_name,
                email=client.email,
                phone=client.phone,
                configurations=[],
            )
            grouped[client.id] = bucket
        bucket.configurations.append(
            OutdatedConfiguration(
                client_configuration_id=installation.id,
                configuration_id=configuration.id,
                configuration_name=configuration.name,
                infobase_name=installation.infobase_name,
                installed_version_id=installed_row.id,
                installed_version=installed_row.version,
                current_version_id=current_row.id,
                current_version=current_row.version,
            )
        )
        total_configurations += 1
    return OutdatedReport(
        total_clients=len(grouped),
        total_configurations=total_configurations,
        clients=list(grouped.values()),
    )

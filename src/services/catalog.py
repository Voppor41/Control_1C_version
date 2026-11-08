"""Клиенты, каталог конфигураций и установки: поиск, актуальный релиз, запрет удаления занятой версии."""

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
    Employee,
    VersionCheck,
)
from src.services.common import flush_session


async def get_client(session: AsyncSession, client_id: UUID) -> Client:
    """Клиент по id вместе с ответственным сотрудником. 404, если нет."""
    client = await session.scalar(
        select(Client)
        .where(Client.id == client_id)
        .options(selectinload(Client.responsible_employee))
    )
    if client is None:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


async def ensure_staff_user(session: AsyncSession, user_id: UUID) -> Employee:
    """Проверяет, что ответственный — активный сотрудник, а не пользователь компании."""
    user = await session.get(Employee, user_id)
    if user is None or not user.is_active:
        raise HTTPException(
            status_code=422,
            detail="Responsible employee must be an active staff user",
        )
    return user


async def get_configuration(session: AsyncSession, configuration_id: UUID) -> Configuration:
    """Конфигурация каталога по id. 404, если нет."""
    row = await session.get(Configuration, configuration_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Configuration not found")
    return row


async def list_versions(session: AsyncSession, configuration_id: UUID) -> list[ConfigurationVersion]:
    """Релизы конфигурации: сначала более новые по дате выпуска."""
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
    """Снимает is_current с релизов конфигурации, кроме except_id. Нужен перед назначением нового актуального."""
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
    """Релиз с is_current. None, если актуальный ещё не отмечен."""
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
    """Актуальный релиз для каждой конфигурации из списка id. Один запрос на страницу."""
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
    """Время последней проверки для каждой установки."""
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
    """Жадная загрузка клиента, конфигурации и установленного релиза."""
    return (
        selectinload(ClientConfiguration.client),
        selectinload(ClientConfiguration.configuration),
        selectinload(ClientConfiguration.installed_version),
    )


async def get_installation(session: AsyncSession, installation_id: UUID) -> ClientConfiguration:
    """Установка по id. 404, если нет."""
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
    """Релиз должен принадлежать указанной конфигурации, иначе 422."""
    version = await session.get(ConfigurationVersion, version_id)
    if version is None or version.configuration_id != configuration_id:
        raise HTTPException(
            status_code=422,
            detail="installed_version_id does not belong to the configuration",
        )
    return version


async def version_reference_count(session: AsyncSession, version_id: UUID) -> int:
    """Сколько установок, проверок и заявок ссылаются на релиз. Ненулевое значение запрещает удаление."""
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
    """Делает релиз актуальным или отказывается снять флаг, пока не выбран другой."""
    if is_current:
        # Сначала снимаем флаг с остальных, иначе частичный уникальный индекс не пустит второй is_current.
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

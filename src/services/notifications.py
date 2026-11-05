from uuid import UUID

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.data.models import (
    ClientConfiguration,
    Notification,
    NotificationType,
    Role,
    RoleCode,
    User,
)
from src.services.catalog import get_client, get_current_version, get_installation
from src.services.common import flush_session


def notification_options():
    return (
        selectinload(Notification.client),
        selectinload(Notification.client_configuration).selectinload(ClientConfiguration.configuration),
    )


async def notify_client_users(
    session: AsyncSession,
    *,
    client_id: UUID,
    type: NotificationType,
    title: str,
    message: str,
    created_by_id: UUID | None,
    client_configuration_id: UUID | None = None,
    scheduled_update_id: UUID | None = None,
    strict: bool = False,
) -> list[Notification]:
    recipients = list(
        (
            await session.scalars(
                select(User)
                .join(Role, User.role_id == Role.id)
                .where(
                    User.client_id == client_id,
                    User.is_active.is_(True),
                    Role.code == RoleCode.CLIENT,
                )
            )
        ).all()
    )
    if not recipients:
        if strict:
            raise HTTPException(
                status_code=422,
                detail="Client has no active portal user. Register a user with the client role first.",
            )
        return []
    notes: list[Notification] = []
    for recipient in recipients:
        note = Notification(
            type=type,
            title=title,
            message=message,
            is_read=False,
            recipient_id=recipient.id,
            created_by_id=created_by_id,
            client_id=client_id,
            client_configuration_id=client_configuration_id,
            scheduled_update_id=scheduled_update_id,
        )
        session.add(note)
        notes.append(note)
    await flush_session(session)
    return notes


async def create_update_notification(
    session: AsyncSession,
    *,
    actor: User,
    client_id: UUID,
    client_configuration_id: UUID | None,
    title: str | None,
    message: str | None,
) -> list[Notification]:
    client = await get_client(session, client_id)
    installation = None
    if client_configuration_id is not None:
        installation = await get_installation(session, client_configuration_id)
        if installation.client_id != client.id:
            raise HTTPException(status_code=422, detail="Configuration does not belong to this client")
    if installation is None and not (message and message.strip()):
        raise HTTPException(
            status_code=422,
            detail="message is required when client_configuration_id is omitted",
        )
    if installation is not None:
        current = await get_current_version(session, installation.configuration_id)
        current_label = current.version if current is not None else "не задана"
        infobase = installation.infobase_name or "информационная база"
        resolved_title = title or f"Доступно обновление: {installation.configuration.name}"
        resolved_message = message or (
            f"Конфигурация «{installation.configuration.name}» ({infobase}): "
            f"установлена версия {installation.installed_version.version}, актуальная {current_label}. "
            "Выберите дату обновления."
        )
    else:
        resolved_title = title or "Необходимо обновление конфигурации"
        resolved_message = message or ""
    return await notify_client_users(
        session,
        client_id=client.id,
        type=NotificationType.UPDATE_AVAILABLE,
        title=resolved_title,
        message=resolved_message,
        created_by_id=actor.id,
        client_configuration_id=installation.id if installation is not None else None,
        strict=True,
    )

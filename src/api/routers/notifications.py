"""Сообщение клиенту о необходимости обновления и просмотр этого сообщения."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, select

from src.api.deps import CurrentUser, Db, PageDep, WriterUser
from src.api.schemas import NotificationCreate, NotificationList, NotificationRead
from src.api.serializers import notification_read
from src.data.models import Notification, NotificationType, RoleCode
from src.services.common import actor_client_id, actor_role, commit_session, count_rows
from src.services.notifications import create_update_notification, notification_options

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _visible(actor, stmt, client_id: UUID | None, recipient_id: UUID | None):
    """Клиент видит только свои сообщения. Сотрудник может сузить ленту клиентом или получателем."""
    if actor_role(actor) == RoleCode.CLIENT:
        return stmt.where(Notification.recipient_id == actor.id)
    if client_id is not None:
        stmt = stmt.where(Notification.client_id == client_id)
    if recipient_id is not None:
        stmt = stmt.where(Notification.recipient_id == recipient_id)
    return stmt


@router.post("", response_model=list[NotificationRead], status_code=201, summary="3.1–3.2 Notify a client about an update")
async def create_notification(
    payload: NotificationCreate,
    actor: WriterUser,
    session: Db,
) -> list[NotificationRead]:
    """Рассылает уведомление всем портальным пользователям организации."""
    notes = await create_update_notification(
        session,
        actor=actor,
        client_id=payload.client_id,
        client_configuration_id=payload.client_configuration_id,
        title=payload.title,
        message=payload.message,
    )
    note_ids = [note.id for note in notes]
    await commit_session(session)
    rows = list(
        (
            await session.scalars(
                select(Notification)
                .where(Notification.id.in_(note_ids))
                .options(*notification_options())
                .order_by(Notification.created_at)
            )
        ).all()
    )
    return [notification_read(row) for row in rows]


@router.get("", response_model=NotificationList, summary="3.3 List notifications")
async def list_notifications(
    actor: CurrentUser,
    session: Db,
    page: PageDep,
    is_read: bool | None = None,
    type: NotificationType | None = None,
    client_id: UUID | None = None,
    recipient_id: UUID | None = None,
) -> NotificationList:
    """Лента и число непрочитанных. unread не зависит от фильтра is_read."""
    if actor_role(actor) == RoleCode.CLIENT and client_id not in (None, actor_client_id(actor)):
        raise HTTPException(status_code=403, detail="You can only access your own client data")
    audience = _visible(actor, select(Notification), client_id, recipient_id)
    unread_stmt = audience.where(Notification.is_read.is_(False))
    stmt = audience
    if is_read is not None:
        stmt = stmt.where(Notification.is_read.is_(is_read))
    if type is not None:
        stmt = stmt.where(Notification.type == type)
    total = await count_rows(session, stmt)
    unread = int(await session.scalar(select(func.count()).select_from(unread_stmt.order_by(None).subquery())) or 0)
    rows = list(
        (
            await session.scalars(
                stmt.options(*notification_options())
                .order_by(Notification.created_at.desc())
                .limit(page.limit)
                .offset(page.offset)
            )
        ).all()
    )
    return NotificationList(
        items=[notification_read(row) for row in rows],
        total=total,
        unread=unread,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/{notification_id}", response_model=NotificationRead, summary="3.3 Read one notification")
async def read_notification(notification_id: UUID, actor: CurrentUser, session: Db) -> NotificationRead:
    """Одно сообщение. Чужое клиенту недоступно."""
    row = await session.scalar(
        select(Notification).where(Notification.id == notification_id).options(*notification_options())
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    if actor_role(actor) == RoleCode.CLIENT and row.recipient_id != actor.id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    if actor_role(actor) == RoleCode.CLIENT or actor_role(actor) in (
        RoleCode.ADMIN,
        RoleCode.SPECIALIST,
        RoleCode.MANAGER,
    ):
        return notification_read(row)
    raise HTTPException(status_code=403, detail="Insufficient permissions")


@router.post("/{notification_id}/read", response_model=NotificationRead, summary="3.3 Mark a notification as read")
async def mark_read(notification_id: UUID, actor: CurrentUser, session: Db) -> NotificationRead:
    """Отмечает прочитанным. Это может сделать только получатель."""
    row = await session.scalar(
        select(Notification).where(Notification.id == notification_id).options(*notification_options())
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Notification not found")
    if row.recipient_id != actor.id:
        raise HTTPException(status_code=403, detail="Only the recipient can mark this notification as read")
    row.is_read = True
    await commit_session(session)
    fresh = await session.scalar(
        select(Notification).where(Notification.id == notification_id).options(*notification_options())
    )
    return notification_read(fresh)

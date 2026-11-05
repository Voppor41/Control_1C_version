from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from src.api.deps import CurrentUser, Db, PageDep, WriterUser
from src.api.schemas import ClientCreate, ClientRead, ClientUpdate, Page
from src.api.serializers import client_read
from src.data.models import Client, RoleCode, ScheduledUpdate
from src.services.catalog import ensure_staff_user, get_client
from src.services.common import (
    actor_client_id,
    actor_role,
    commit_session,
    count_rows,
    ensure_client_scope,
    flush_session,
    like_pattern,
)

router = APIRouter(prefix="/clients", tags=["clients"])


def _scoped_client_filter(user, stmt, client_id: UUID | None):
    if actor_role(user) == RoleCode.CLIENT:
        if actor_client_id(user) is None:
            return None
        ensure_client_scope(user, actor_client_id(user))
        return stmt.where(Client.id == actor_client_id(user))
    if client_id is not None:
        return stmt.where(Client.id == client_id)
    return stmt


@router.post("", response_model=ClientRead, status_code=201, summary="1.2 Register a client")
async def create_client(payload: ClientCreate, _actor: WriterUser, session: Db) -> ClientRead:
    if payload.responsible_employee_id is not None:
        await ensure_staff_user(session, payload.responsible_employee_id)
    duplicate = await session.scalar(
        select(Client.id).where(
            or_(
                Client.company_name == payload.company_name,
                Client.email == payload.email,
                Client.phone == payload.phone,
            )
        )
    )
    if duplicate is not None:
        raise HTTPException(status_code=409, detail="Client with this name, email, or phone already exists")
    client = Client(
        company_name=payload.company_name,
        phone=payload.phone,
        email=payload.email,
        responsible_employee_id=payload.responsible_employee_id,
    )
    session.add(client)
    await flush_session(session)
    await commit_session(session)
    return client_read(await get_client(session, client.id))


@router.get("", response_model=Page[ClientRead], summary="1.2 List clients")
async def list_clients(
    actor: CurrentUser,
    session: Db,
    page: PageDep,
    q: str | None = Query(default=None, max_length=255),
    responsible_employee_id: UUID | None = None,
) -> Page[ClientRead]:
    stmt = select(Client)
    scoped = _scoped_client_filter(actor, stmt, None)
    if scoped is None:
        return Page(items=[], total=0, limit=page.limit, offset=page.offset)
    stmt = scoped
    if q and q.strip():
        pattern = like_pattern(q.strip())
        stmt = stmt.where(
            or_(
                Client.company_name.ilike(pattern, escape="\\"),
                Client.email.ilike(pattern, escape="\\"),
                Client.phone.ilike(pattern, escape="\\"),
            )
        )
    if responsible_employee_id is not None and actor_role(actor) != RoleCode.CLIENT:
        stmt = stmt.where(Client.responsible_employee_id == responsible_employee_id)
    total = await count_rows(session, stmt)
    rows = list(
        (
            await session.scalars(
                stmt.options(selectinload(Client.responsible_employee))
                .order_by(Client.company_name)
                .limit(page.limit)
                .offset(page.offset)
            )
        ).all()
    )
    return Page(
        items=[client_read(row) for row in rows],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


@router.get("/{client_id}", response_model=ClientRead, summary="1.2 Get a client")
async def read_client(client_id: UUID, actor: CurrentUser, session: Db) -> ClientRead:
    ensure_client_scope(actor, client_id)
    return client_read(await get_client(session, client_id))


@router.patch("/{client_id}", response_model=ClientRead, summary="1.2 Update a client")
async def update_client(
    client_id: UUID,
    payload: ClientUpdate,
    _actor: WriterUser,
    session: Db,
) -> ClientRead:
    client = await get_client(session, client_id)
    if "responsible_employee_id" in payload.model_fields_set and payload.responsible_employee_id is not None:
        await ensure_staff_user(session, payload.responsible_employee_id)
    if payload.company_name is not None:
        client.company_name = payload.company_name
    if payload.phone is not None:
        client.phone = payload.phone
    if payload.email is not None:
        client.email = payload.email
    if "responsible_employee_id" in payload.model_fields_set:
        client.responsible_employee_id = payload.responsible_employee_id
    await flush_session(session)
    await commit_session(session)
    return client_read(await get_client(session, client.id))


@router.delete("/{client_id}", status_code=204, summary="1.2 Delete a client without update history")
async def delete_client(client_id: UUID, _actor: WriterUser, session: Db) -> Response:
    client = await get_client(session, client_id)
    used = await session.scalar(
        select(func.count()).select_from(ScheduledUpdate).where(ScheduledUpdate.client_id == client.id)
    )
    if used:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete a client that has update history",
        )
    await session.delete(client)
    await commit_session(session)
    return Response(status_code=204)

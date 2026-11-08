"""Регистрация сотрудников и пользователей компании. Пишет только администратор."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, or_, select, union_all
from sqlalchemy.orm import selectinload

from src.api.deps import AdminUser, CurrentUser, Db, PageDep, StaffUser
from src.api.schemas import Page, RoleRead, UserCreate, UserRead, UserUpdate
from src.api.serializers import user_read
from src.core.security import hash_password
from src.data.models import Account, ClientUser, Employee, Role, RoleCode
from src.services.accounts import assert_email_available, get_account
from src.services.catalog import get_client
from src.services.common import (
    actor_role,
    commit_session,
    count_rows,
    flush_session,
    get_role,
    like_pattern,
)

router = APIRouter(tags=["users"])

_STAFF = {RoleCode.ADMIN, RoleCode.SPECIALIST, RoleCode.MANAGER}


def _apply_profile(target: Account, payload: UserUpdate) -> None:
    """Имя, телефон, пароль и активность. Поля вне запроса не затираются."""
    if payload.full_name is not None:
        target.full_name = payload.full_name
    if "phone" in payload.model_fields_set:
        target.phone = payload.phone
    if payload.password is not None:
        target.hashed_password = hash_password(payload.password)
    if payload.is_active is not None:
        target.is_active = payload.is_active


async def _validate_role_link(session, role: RoleCode, client_id: UUID | None) -> None:
    """Пользователь компании обязан иметь client_id. Сотрудник к организации не привязывается."""
    if role == RoleCode.CLIENT and client_id is None:
        raise HTTPException(status_code=422, detail="Client role requires client_id")
    if role != RoleCode.CLIENT and client_id is not None:
        raise HTTPException(status_code=422, detail="Only client users can be linked to a client company")
    if client_id is not None:
        await get_client(session, client_id)


async def _guard_last_admin(session, target: Employee, actor: Account, payload: UserUpdate) -> None:
    """Нельзя снять или отключить последнего активного администратора и самого себя."""
    if target.id == actor.id and payload.is_active is False:
        raise HTTPException(status_code=422, detail="You cannot deactivate yourself")
    if target.id == actor.id and payload.role not in (None, RoleCode.ADMIN):
        raise HTTPException(status_code=422, detail="You cannot remove your own administrator role")
    removes_admin = target.role.code == RoleCode.ADMIN and (
        payload.role not in (None, RoleCode.ADMIN) or payload.is_active is False
    )
    if not removes_admin:
        return
    others = await session.scalar(
        select(func.count())
        .select_from(Employee)
        .join(Role, Employee.role_id == Role.id)
        .where(Role.code == RoleCode.ADMIN, Employee.is_active.is_(True), Employee.id != target.id)
    )
    if not others:
        raise HTTPException(
            status_code=422,
            detail="Cannot remove or deactivate the last active administrator",
        )


def _person_filters(stmt, model, q: str | None, is_active: bool | None):
    if q and q.strip():
        pattern = like_pattern(q.strip())
        stmt = stmt.where(
            or_(
                model.full_name.ilike(pattern, escape="\\"),
                model.email.ilike(pattern, escape="\\"),
            )
        )
    if is_active is not None:
        stmt = stmt.where(model.is_active.is_(is_active))
    return stmt


@router.get("/roles", response_model=list[RoleRead], summary="1.1 List roles")
async def list_roles(_user: StaffUser, session: Db) -> list[Role]:
    """Справочник должностей сотрудников. Пользователь компании в нём не хранится."""
    return list((await session.scalars(select(Role).order_by(Role.code))).all())


@router.post("/users", response_model=UserRead, status_code=201, summary="1.1 Register a user and assign a role")
async def create_user(payload: UserCreate, _actor: AdminUser, session: Db) -> UserRead:
    """Регистрация. role=client создаёт пользователя компании, остальные коды — сотрудника."""
    await _validate_role_link(session, payload.role, payload.client_id)
    await assert_email_available(session, payload.email)
    if payload.role == RoleCode.CLIENT:
        person: Account = ClientUser(
            full_name=payload.full_name,
            email=payload.email,
            hashed_password=hash_password(payload.password),
            phone=payload.phone,
            is_active=True,
            client_id=payload.client_id,
        )
    else:
        role = await get_role(session, payload.role)
        person = Employee(
            full_name=payload.full_name,
            email=payload.email,
            hashed_password=hash_password(payload.password),
            phone=payload.phone,
            is_active=True,
            role_id=role.id,
        )
    session.add(person)
    await flush_session(session)
    await commit_session(session)
    return user_read(await get_account(session, person.id))


@router.get("/users", response_model=Page[UserRead], summary="1.1 List users")
async def list_users(
    _actor: StaffUser,
    session: Db,
    page: PageDep,
    q: str | None = Query(default=None, max_length=255),
    role: RoleCode | None = None,
    is_active: bool | None = None,
) -> Page[UserRead]:
    """Сотрудники и пользователи компании одним списком. role отбирает должность или client."""
    if role == RoleCode.CLIENT:
        return await _page_client_users(session, page, q, is_active)
    if role in _STAFF:
        return await _page_employees(session, page, q, role, is_active)
    return await _page_everyone(session, page, q, is_active)


async def _page_employees(session, page: PageDep, q, role: RoleCode | None, is_active) -> Page[UserRead]:
    stmt = select(Employee).join(Role, Employee.role_id == Role.id)
    stmt = _person_filters(stmt, Employee, q, is_active)
    if role is not None:
        stmt = stmt.where(Role.code == role)
    total = await count_rows(session, stmt)
    rows = list(
        (
            await session.scalars(
                stmt.options(selectinload(Employee.role))
                .order_by(Employee.full_name, Employee.id)
                .limit(page.limit)
                .offset(page.offset)
            )
        ).all()
    )
    return Page(
        items=[user_read(row) for row in rows],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


async def _page_client_users(session, page: PageDep, q, is_active) -> Page[UserRead]:
    stmt = _person_filters(select(ClientUser), ClientUser, q, is_active)
    total = await count_rows(session, stmt)
    rows = list(
        (
            await session.scalars(
                stmt.options(selectinload(ClientUser.client))
                .order_by(ClientUser.full_name, ClientUser.id)
                .limit(page.limit)
                .offset(page.offset)
            )
        ).all()
    )
    return Page(
        items=[user_read(row) for row in rows],
        total=total,
        limit=page.limit,
        offset=page.offset,
    )


async def _page_everyone(session, page: PageDep, q, is_active) -> Page[UserRead]:
    staff_ids = _person_filters(
        select(Employee.id.label("id"), Employee.full_name.label("full_name")),
        Employee,
        q,
        is_active,
    )
    client_ids = _person_filters(
        select(ClientUser.id.label("id"), ClientUser.full_name.label("full_name")),
        ClientUser,
        q,
        is_active,
    )
    combined = union_all(staff_ids, client_ids).subquery()
    total = int(await session.scalar(select(func.count()).select_from(combined)) or 0)
    id_rows = (
        await session.execute(
            select(combined.c.id)
            .order_by(combined.c.full_name, combined.c.id)
            .limit(page.limit)
            .offset(page.offset)
        )
    ).all()
    ids = [row[0] for row in id_rows]
    if not ids:
        return Page(items=[], total=total, limit=page.limit, offset=page.offset)
    employees = {
        row.id: row
        for row in (
            await session.scalars(
                select(Employee).where(Employee.id.in_(ids)).options(selectinload(Employee.role))
            )
        ).all()
    }
    company_users = {
        row.id: row
        for row in (
            await session.scalars(
                select(ClientUser).where(ClientUser.id.in_(ids)).options(selectinload(ClientUser.client))
            )
        ).all()
    }
    items = []
    for person_id in ids:
        person = employees.get(person_id) or company_users.get(person_id)
        if person is not None:
            items.append(user_read(person))
    return Page(items=items, total=total, limit=page.limit, offset=page.offset)


@router.get("/users/{user_id}", response_model=UserRead, summary="1.1 Get a user")
async def get_user(user_id: UUID, actor: CurrentUser, session: Db) -> UserRead:
    """Карточка. Пользователь компании может открыть только себя."""
    if actor_role(actor) == RoleCode.CLIENT and actor.id != user_id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    return user_read(await get_account(session, user_id))


@router.patch("/users/{user_id}", response_model=UserRead, summary="1.1 Assign a role or update access")
async def update_user(user_id: UUID, payload: UserUpdate, actor: AdminUser, session: Db) -> UserRead:
    """Смена должности сотрудника или организации пользователя компании.

    Перенос между таблицами здесь не делается: сотрудник и пользователь компании — разные сущности.
    """
    target = await get_account(session, user_id)
    if isinstance(target, Employee):
        await _update_employee(session, target, actor, payload)
    else:
        await _update_client_user(session, target, payload)
    await flush_session(session)
    await commit_session(session)
    return user_read(await get_account(session, target.id))


async def _update_employee(session, target: Employee, actor: Account, payload: UserUpdate) -> None:
    await _guard_last_admin(session, target, actor, payload)
    if payload.role == RoleCode.CLIENT:
        raise HTTPException(
            status_code=422,
            detail="Cannot turn an employee into a company user. Register a company user instead.",
        )
    _apply_profile(target, payload)
    if payload.role is not None:
        role = await get_role(session, payload.role)
        target.role = role
        target.role_id = role.id
    if "client_id" in payload.model_fields_set and payload.client_id is not None:
        raise HTTPException(status_code=422, detail="Only client users can be linked to a client company")


async def _update_client_user(session, target: ClientUser, payload: UserUpdate) -> None:
    if payload.role not in (None, RoleCode.CLIENT):
        raise HTTPException(
            status_code=422,
            detail="Cannot assign an employee position to a company user. Register an employee instead.",
        )
    _apply_profile(target, payload)
    if "client_id" in payload.model_fields_set:
        if payload.client_id is None:
            raise HTTPException(status_code=422, detail="Client role requires client_id")
        await get_client(session, payload.client_id)
        target.client_id = payload.client_id

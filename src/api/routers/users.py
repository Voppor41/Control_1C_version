from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import selectinload

from src.api.deps import AdminUser, CurrentUser, Db, PageDep, StaffUser
from src.api.schemas import Page, RoleRead, UserCreate, UserRead, UserUpdate
from src.api.serializers import user_read
from src.core.security import hash_password
from src.data.models import Role, RoleCode, User
from src.services.catalog import get_client
from src.services.common import commit_session, count_rows, flush_session, get_role, like_pattern

router = APIRouter(tags=["users"])


def _user_options():
    return (selectinload(User.role), selectinload(User.client))


async def _load_user(session, user_id: UUID) -> User:
    user = await session.scalar(select(User).where(User.id == user_id).options(*_user_options()))
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user


async def _validate_role_link(session, role: RoleCode, client_id: UUID | None) -> None:
    if role == RoleCode.CLIENT and client_id is None:
        raise HTTPException(status_code=422, detail="Client role requires client_id")
    if role != RoleCode.CLIENT and client_id is not None:
        raise HTTPException(status_code=422, detail="Only client users can be linked to a client company")
    if client_id is not None:
        await get_client(session, client_id)


async def _guard_last_admin(session, target: User, actor: User, payload: UserUpdate) -> None:
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
        .select_from(User)
        .join(Role, User.role_id == Role.id)
        .where(Role.code == RoleCode.ADMIN, User.is_active.is_(True), User.id != target.id)
    )
    if not others:
        raise HTTPException(
            status_code=422,
            detail="Cannot remove or deactivate the last active administrator",
        )


@router.get("/roles", response_model=list[RoleRead], summary="1.1 List roles")
async def list_roles(_user: StaffUser, session: Db) -> list[Role]:
    return list((await session.scalars(select(Role).order_by(Role.code))).all())


@router.post("/users", response_model=UserRead, status_code=201, summary="1.1 Register a user and assign a role")
async def create_user(payload: UserCreate, _actor: AdminUser, session: Db) -> UserRead:
    await _validate_role_link(session, payload.role, payload.client_id)
    existing = await session.scalar(select(User.id).where(User.email == payload.email))
    if existing is not None:
        raise HTTPException(status_code=409, detail="User with this email already exists")
    role = await get_role(session, payload.role)
    user = User(
        full_name=payload.full_name,
        email=payload.email,
        hashed_password=hash_password(payload.password),
        phone=payload.phone,
        is_active=True,
        role_id=role.id,
        client_id=payload.client_id,
    )
    session.add(user)
    await flush_session(session)
    await commit_session(session)
    return user_read(await _load_user(session, user.id))


@router.get("/users", response_model=Page[UserRead], summary="1.1 List users")
async def list_users(
    _actor: StaffUser,
    session: Db,
    page: PageDep,
    q: str | None = Query(default=None, max_length=255),
    role: RoleCode | None = None,
    is_active: bool | None = None,
) -> Page[UserRead]:
    stmt = select(User).join(Role, User.role_id == Role.id)
    if q and q.strip():
        pattern = like_pattern(q.strip())
        stmt = stmt.where(
            or_(
                User.full_name.ilike(pattern, escape="\\"),
                User.email.ilike(pattern, escape="\\"),
            )
        )
    if role is not None:
        stmt = stmt.where(Role.code == role)
    if is_active is not None:
        stmt = stmt.where(User.is_active.is_(is_active))
    total = await count_rows(session, stmt)
    rows = list(
        (
            await session.scalars(
                stmt.options(*_user_options())
                .order_by(User.full_name)
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


@router.get("/users/{user_id}", response_model=UserRead, summary="1.1 Get a user")
async def get_user(user_id: UUID, actor: CurrentUser, session: Db) -> UserRead:
    if actor.role.code == RoleCode.CLIENT and actor.id != user_id:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    if actor.role.code == RoleCode.CLIENT or actor.role.code in (
        RoleCode.ADMIN,
        RoleCode.SPECIALIST,
        RoleCode.MANAGER,
    ):
        return user_read(await _load_user(session, user_id))
    raise HTTPException(status_code=403, detail="Insufficient permissions")


@router.patch("/users/{user_id}", response_model=UserRead, summary="1.1 Assign a role or update access")
async def update_user(user_id: UUID, payload: UserUpdate, actor: AdminUser, session: Db) -> UserRead:
    target = await _load_user(session, user_id)
    await _guard_last_admin(session, target, actor, payload)
    if payload.full_name is not None:
        target.full_name = payload.full_name
    if "phone" in payload.model_fields_set:
        target.phone = payload.phone
    if payload.password is not None:
        target.hashed_password = hash_password(payload.password)
    if payload.is_active is not None:
        target.is_active = payload.is_active
    if payload.role is not None:
        role = await get_role(session, payload.role)
        target.role = role
        target.role_id = role.id
    if "client_id" in payload.model_fields_set:
        target.client_id = payload.client_id
    await _validate_role_link(session, target.role.code, target.client_id)
    await flush_session(session)
    await commit_session(session)
    return user_read(await _load_user(session, target.id))

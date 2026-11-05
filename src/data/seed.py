from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.data.models import Role, RoleCode

ROLE_TITLES = {
    RoleCode.ADMIN: "Администратор",
    RoleCode.SPECIALIST: "Специалист по сопровождению",
    RoleCode.MANAGER: "Руководитель отдела сопровождения",
    RoleCode.CLIENT: "Клиент",
}


async def seed_initial_data(session: AsyncSession) -> None:
    existing = set((await session.execute(select(Role.code))).scalars().all())
    for code, title in ROLE_TITLES.items():
        if code not in existing:
            session.add(Role(code=code, name=title))
    await session.commit()

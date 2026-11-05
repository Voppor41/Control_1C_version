import asyncio
from urllib.parse import urlparse

import asyncpg

from src.core.config import settings


async def main() -> None:
    parsed = urlparse(settings.database_url.replace("+asyncpg", ""))
    db_name = parsed.path.lstrip("/")
    admin = await asyncpg.connect(
        user=parsed.username,
        password=parsed.password,
        host=parsed.hostname,
        port=parsed.port or 5432,
        database="postgres",
        ssl=False,
    )
    exists = await admin.fetchval(
        "SELECT 1 FROM pg_database WHERE datname = $1",
        db_name,
    )
    if not exists:
        await admin.execute(f'CREATE DATABASE "{db_name}"')
        print("DATABASE_CREATED")
    else:
        print("DATABASE_EXISTS")
    await admin.close()


if __name__ == "__main__":
    asyncio.run(main())

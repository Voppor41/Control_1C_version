#!/bin/sh
set -eu

python - <<'PY'
import asyncio
import sys

from sqlalchemy import text

from src.core.database import engine


async def main() -> None:
    last_error = None
    for _ in range(30):
        try:
            async with engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            await engine.dispose()
            return
        except Exception as exc:  # noqa: BLE001 - startup retry
            last_error = exc
            await asyncio.sleep(1)
    print(f"database is not ready: {last_error}", file=sys.stderr)
    sys.exit(1)


asyncio.run(main())
PY

echo "Applying migrations..."
alembic upgrade head
echo "Starting API..."
exec uvicorn main:app --host 0.0.0.0 --port 8000

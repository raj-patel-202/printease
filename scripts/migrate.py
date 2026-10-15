"""Apply versioned schema upgrades; require explicit adoption of legacy databases.

The original application created tables without recording migration history.
Never guess a baseline or delete those tables to make a deployment start.
"""

import asyncio
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from sqlalchemy import inspect, text  # noqa: E402
from sqlalchemy.ext.asyncio import create_async_engine  # noqa: E402
from sqlalchemy.pool import NullPool  # noqa: E402

from config import settings  # noqa: E402


class LegacyDatabaseError(Exception):
    pass


async def check_migration_history():
    """Read only: an empty database or a versioned database may be upgraded."""
    engine = create_async_engine(settings.database_url, poolclass=NullPool)
    try:
        async with engine.connect() as connection:
            tables = set(await connection.run_sync(lambda sync: inspect(sync).get_table_names()))
            if not tables - {"alembic_version"}:
                return
            if "alembic_version" in tables:
                revisions = (await connection.execute(text("SELECT version_num FROM alembic_version"))).all()
                if revisions:
                    return
            raise LegacyDatabaseError(
                "Existing database tables were found without Alembic migration history.\n"
                "No schema changes were made. Do not delete your database volume.\n"
                "Back up PostgreSQL and uploaded PDFs, then verify the legacy schema with:\n"
                "  docker compose run --rm --no-deps migrate python scripts/check_baseline.py\n"
                "Follow 'Existing database created by the old application' in docs/DEPLOYMENT.md\n"
                "to record the verified baseline before retrying deployment."
            )
    finally:
        await engine.dispose()


def main():
    try:
        asyncio.run(check_migration_history())
    except LegacyDatabaseError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from None
    command.upgrade(Config(str(ROOT / "alembic.ini")), "head")
    print("Database schema is at the latest migration.")


if __name__ == "__main__":
    main()

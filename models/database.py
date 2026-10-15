from typing import Annotated

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from fastapi import Depends
from config import settings

SQLALCHEMY_DATABASE_URL = settings.database_url

engine = create_async_engine(
    SQLALCHEMY_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_max_overflow,
    pool_timeout=settings.db_pool_timeout_seconds,
    pool_recycle=1800,
    connect_args={
        "server_settings": {
            "statement_timeout": str(settings.db_statement_timeout_ms),
            "idle_in_transaction_session_timeout": "60000",
            "application_name": "printease",
        }
    },
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    """One session per request; services explicitly commit successful changes."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise


async def acquire_transaction_advisory_lock(
    db: AsyncSession,
    namespace: int,
    key: int,
) -> None:
    """Serialize a critical section for the current transaction on PostgreSQL."""
    bind = db.get_bind()
    if bind.dialect.name != "postgresql":
        return

    await db.execute(
        text("SELECT pg_advisory_xact_lock(:namespace, :key)"),
        {"namespace": namespace, "key": key},
    )


DBSession = Annotated[AsyncSession, Depends(get_db)]

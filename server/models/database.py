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
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        yield session


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

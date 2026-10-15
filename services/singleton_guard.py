"""Own and revalidate the PostgreSQL session lock across connection failures."""

import asyncio
import logging

from sqlalchemy import text

log = logging.getLogger("printease.singleton")


class SingletonGuard:
    def __init__(self, engine):
        self.engine = engine
        self.connection = None
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        async with self._lock:
            await self._discard()
            try:
                self.connection = await self.engine.connect()
                held = await self.connection.scalar(text("SELECT pg_try_advisory_lock(734910, 1)"))
                await self.connection.commit()
                if not held:
                    await self._discard()
                return bool(held)
            except Exception:
                await self._discard()
                raise

    async def check(self) -> bool:
        async with self._lock:
            if self.connection is None:
                return False
            try:
                held = await self.connection.scalar(
                    text("""SELECT EXISTS (
                    SELECT 1 FROM pg_locks WHERE pid=pg_backend_pid() AND locktype='advisory'
                    AND classid=734910::oid AND objid=1::oid AND objsubid=2 AND granted
                )""")
                )
                await self.connection.commit()
                if not held:
                    await self._discard()
                return bool(held)
            except Exception:
                await self._discard()
                return False

    async def _discard(self):
        if self.connection is not None:
            try:
                # Returning a session-locked connection to a pool is unsafe. Close
                # the physical connection so PostgreSQL releases any remaining lock.
                await self.connection.invalidate()
            finally:
                await self.connection.close()
                self.connection = None

    async def close(self):
        async with self._lock:
            await self._discard()

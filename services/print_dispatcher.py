import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import update

from config import settings
from models import models
from models.database import AsyncSessionLocal

log = logging.getLogger("printease.dispatcher")


class PrintDispatcher:
    """
    Shared state between the admin page and the printer agent.

    The agent (printer_pc) *pulls* jobs from /api/agent/next - nothing is pushed to it,
    so the printer PC only needs normal outbound internet.

    - `is_running` is the admin's Start/Stop switch. It is False after every server
      restart, so nothing prints until an admin presses Start.
    - State is in memory, so run a single uvicorn worker (as the Dockerfile does).
    """

    def __init__(self):
        self.lock = asyncio.Lock()
        self.is_running = False
        self.agent_last_seen: datetime | None = None
        self.agent_printer: str | None = None
        self.current: dict | None = None  # {"order_id", "session", "started_at"}

    @property
    def agent_online(self) -> bool:
        if not self.agent_last_seen:
            return False
        age = datetime.now(timezone.utc) - self.agent_last_seen
        return age < timedelta(seconds=settings.agent_online_seconds)

    def touch_agent(self, printer: str | None):
        self.agent_last_seen = datetime.now(timezone.utc)
        if printer:
            self.agent_printer = printer

    def begin_job(self, order_id: int, session: str):
        self.current = {
            "order_id": order_id,
            "session": session,
            "started_at": datetime.now(timezone.utc),
        }

    def end_job(self):
        self.current = None

    async def fail_order(self, order_id: int):
        async with AsyncSessionLocal() as db:
            await db.execute(
                update(models.Order)
                .where(models.Order.id == order_id, models.Order.print_status == "printing")
                .values(print_status="failed")
            )
            await db.commit()

    async def recover_on_startup(self):
        """Anything left in 'printing' belongs to a run that no longer exists."""
        async with AsyncSessionLocal() as db:
            res = await db.execute(
                update(models.Order).where(models.Order.print_status == "printing").values(print_status="failed")
            )
            await db.commit()
        if res.rowcount:
            log.warning("Marked %s interrupted job(s) as failed on startup", res.rowcount)

    async def run(self):
        """Reaper: fail a job whose agent never reported back."""
        timeout = timedelta(minutes=settings.print_job_timeout_minutes)
        while True:
            await asyncio.sleep(30)
            try:
                async with self.lock:
                    cur = self.current
                    if cur and datetime.now(timezone.utc) - cur["started_at"] > timeout:
                        log.error("Order %s timed out while printing - marking failed", cur["order_id"])
                        await self.fail_order(cur["order_id"])
                        self.end_job()
            except Exception:
                log.exception("Dispatcher reaper error")


dispatcher = PrintDispatcher()

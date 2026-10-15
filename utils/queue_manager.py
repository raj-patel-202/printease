import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import select, case, func, or_
from sqlalchemy.ext.asyncio import AsyncSession
from models import models


class PrintQueueManager:
    def __init__(self, cache_ttl_seconds: int = 15, printer_ppm: int = 20, max_queue_size: int = 100):
        self._queue_map: dict[int, dict] = {}
        self._last_updated: datetime | None = None
        self._ttl = timedelta(seconds=cache_ttl_seconds)
        self._lock = asyncio.Lock()

        self.printer_ppm = printer_ppm
        self.max_queue_size = max_queue_size

    async def _refresh_cache(self, db: AsyncSession):
        stmt = (
            select(models.Order.id, models.Order.print_status, models.Order.total_pages, models.Order.copies)
            .join(models.Payment)
            .where(
                models.Order.print_status.in_(["pending", "printing"]),
                models.Payment.payment_status == "completed",
            )
            .order_by(
                case((models.Order.print_status == "printing", 0), else_=1).asc(),
                models.Order.date_ordered.asc(),
                models.Order.id.asc(),
            )
            .limit(self.max_queue_size)
        )

        result = await db.execute(stmt)
        rows = result.all()

        new_queue_map = {}
        running_pages_total = 0

        for index, row in enumerate(rows):
            new_queue_map[row.id] = {
                "print_status": row.print_status,
                "queue_position": index + 1,
                "pages_ahead": running_pages_total,
            }
            running_pages_total += row.total_pages * row.copies

        self._queue_map = new_queue_map
        self._last_updated = datetime.now(timezone.utc)

    async def get_order_status(self, order_id: int, db: AsyncSession) -> dict | None:
        now = datetime.now(timezone.utc)

        async with self._lock:
            if not self._last_updated or (now - self._last_updated) > self._ttl:
                await self._refresh_cache(db)

        order_data = self._queue_map.get(order_id)

        if not order_data:
            # The bounded cache is an optimization, not a limit on queue visibility.
            order = await db.scalar(
                select(models.Order)
                .join(models.Payment)
                .where(
                    models.Order.id == order_id,
                    models.Order.print_status.in_(["pending", "printing"]),
                    models.Payment.payment_status == "completed",
                )
            )
            if not order:
                return None
            ahead = (
                (models.Order.id < 0)
                if order.print_status == "printing"
                else or_(
                    models.Order.print_status == "printing",
                    models.Order.date_ordered < order.date_ordered,
                    (models.Order.date_ordered == order.date_ordered) & (models.Order.id < order.id),
                )
            )
            row = (
                await db.execute(
                    select(func.count(), func.coalesce(func.sum(models.Order.total_pages * models.Order.copies), 0))
                    .select_from(models.Order)
                    .join(models.Payment)
                    .where(
                        models.Order.id != order_id,
                        models.Order.print_status.in_(["pending", "printing"]),
                        models.Payment.payment_status == "completed",
                        ahead,
                    )
                )
            ).one()
            return {
                "id": order_id,
                "print_status": order.print_status,
                "queue_position": row[0] + 1,
                "estimated_wait_minutes": round(row[1] / self.printer_ppm, 1) if self.printer_ppm > 0 else 0,
            }

        pages_ahead = order_data["pages_ahead"]
        estimated_wait_minutes = round(pages_ahead / self.printer_ppm, 1) if self.printer_ppm > 0 else 0

        return {
            "id": order_id,
            "print_status": order_data["print_status"],
            "queue_position": order_data["queue_position"],
            "estimated_wait_minutes": estimated_wait_minutes,
        }


# Instantiate global instance
queue_manager = PrintQueueManager(cache_ttl_seconds=15, printer_ppm=20, max_queue_size=100)

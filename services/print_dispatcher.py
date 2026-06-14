import asyncio
import json
from httpx import AsyncClient
import aiofiles
from sqlalchemy import select, update
from models.database import AsyncSessionLocal
from models import models
from config import settings

class PrintDispatcher:
    def __init__(self): 
        self.is_running = True

    async def run(self):
        while True:
            if not self.is_running:
                await asyncio.sleep(5)
                continue
            
            try:
                await self._process_next_job()
            except Exception as e:
                await asyncio.sleep(5)

    async def _process_next_job(self):
        async with AsyncSessionLocal() as session:
            await session.execute(
                update(models.Order)
                .where(models.Order.print_status == "printing")
                .values(print_status="failed")
            )
            await session.commit()

            result = await session.execute(
                select(models.Order)
                .join(models.Payment)
                .where(
                    models.Order.print_status == "pending",
                    models.Payment.payment_status == "completed"
                )
                .order_by(models.Order.date_ordered.asc())
                .limit(1)
            )
            order = result.scalar_one_or_none()
            
            if not order:
                await asyncio.sleep(2)
                return

            try:
                async with AsyncClient(timeout=5) as client:
                    base_url = settings.printer_pc_tailscale_url.rstrip('/')
                    health_res = await client.get(f"{base_url}/api/health")
                    health_res.raise_for_status()
            except Exception as e:
                await asyncio.sleep(5)
                return
            

            try:
                file_path = order.file_path
                if not await asyncio.to_thread(file_path.exists):
                    await session.execute(
                        update(models.Order)
                        .where(models.Order.id == order.id)
                        .values(print_status="failed")
                    )
                    await session.commit()
                    return

                options_json = {
                    "copies": order.copies,
                    "color_mode": order.color_mode,
                    "side_mode": order.side_mode,
                    "orientation": order.orientation,
                    "paper_size": order.paper_size,
                    "order_id": order.id,
                }
                
                async with aiofiles.open(file_path, "rb") as f:
                    file_bytes = await f.read()

                claim_result = await session.execute(
                    update(models.Order)
                    .where(
                        models.Order.id == order.id,
                        models.Order.print_status == "pending"
                    )
                    .values(print_status="printing")
                )
                if claim_result.rowcount == 0:
                    await session.rollback()
                    return
                await session.commit()

                async with AsyncClient(timeout=600) as client:
                    files = {"file": (order.file_name, file_bytes, "application/pdf")}
                    data = {"options": json.dumps(options_json)}
                    base_url = settings.printer_pc_tailscale_url.rstrip('/')
                    response = await client.post(
                        f"{base_url}/api/print",
                        data=data,
                        files=files
                    )
                    response.raise_for_status()

                await session.execute(
                    update(models.Order)
                    .where(models.Order.id == order.id)
                    .values(print_status="completed")
                )
                await session.commit()

            except Exception as e:
                await session.execute(
                    update(models.Order)
                    .where(models.Order.id == order.id)
                    .values(print_status="failed")
                )
                await session.commit()
                await asyncio.sleep(10) # Backoff before retrying

dispatcher = PrintDispatcher()

"""
Endpoints used by the printer agent (printer_pc). The agent polls; the server never
connects to the printer PC.

Flow:  GET /next  ->  GET /jobs/{id}/file  ->  (print)  ->  POST /jobs/{id}/result
Auth:  Authorization: Bearer <AGENT_TOKEN>
       X-Agent-Session: random id the agent generates on each start
"""
import json
import logging
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, Header, HTTPException, Response, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select, update

from config import settings
from models import models
from models.database import DBSession
from services.print_dispatcher import dispatcher

log = logging.getLogger("printease.agent")


def require_agent(authorization: Annotated[str | None, Header()] = None):
    token = (authorization or "").removeprefix("Bearer ").strip()
    expected = settings.agent_token.get_secret_value()
    if not secrets.compare_digest(token.encode(), expected.encode()):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid agent token")


router = APIRouter(prefix="/api/agent", tags=["agent"], dependencies=[Depends(require_agent)])

Session = Annotated[str, Header(alias="X-Agent-Session", min_length=8, max_length=64)]
PrinterName = Annotated[str | None, Header(alias="X-Agent-Printer", max_length=200)]


def _no_job():
    state = "running" if dispatcher.is_running else "stopped"
    return Response(status_code=status.HTTP_204_NO_CONTENT, headers={"X-Dispatcher": state})


def _require_current(order_id: int, session: str):
    cur = dispatcher.current
    if not cur or cur["order_id"] != order_id or cur["session"] != session:
        raise HTTPException(status.HTTP_409_CONFLICT, "This job is not assigned to this agent session")


@router.get("/next")
async def next_job(db: DBSession, x_agent_session: Session, x_agent_printer: PrinterName = None):
    dispatcher.touch_agent(x_agent_printer)

    cur = dispatcher.current
    if cur and cur["session"] != x_agent_session:
        # The agent that owned this job restarted without reporting back.
        log.warning("Agent restarted mid-job; failing order %s", cur["order_id"])
        await dispatcher.fail_order(cur["order_id"])
        dispatcher.end_job()
    elif cur:
        return _no_job()  # same session still busy; it should not be asking

    if not dispatcher.is_running:
        return _no_job()

    result = await db.execute(
        select(models.Order)
        .join(models.Payment)
        .where(
            models.Order.print_status == "pending",
            models.Payment.payment_status == "completed",
        )
        .order_by(models.Order.date_ordered.asc())
        .limit(1)
    )
    order = result.scalar_one_or_none()
    if not order:
        return _no_job()

    if not order.file_path.exists():
        log.error("Order %s: PDF missing on disk", order.id)
        await db.execute(
            update(models.Order).where(models.Order.id == order.id).values(print_status="failed")
        )
        await db.commit()
        return _no_job()

    claim = await db.execute(
        update(models.Order)
        .where(models.Order.id == order.id, models.Order.print_status == "pending")
        .values(print_status="printing")
    )
    if claim.rowcount == 0:
        await db.rollback()
        return _no_job()
    await db.commit()

    dispatcher.begin_job(order.id, x_agent_session)
    log.info("Order %s handed to agent", order.id)
    return {
        "order_id": order.id,
        "total_pages": order.total_pages,
        "options": {
            "copies": order.copies,
            "color_mode": order.color_mode,
            "side_mode": order.side_mode,
            "orientation": order.orientation,
            "paper_size": order.paper_size,
            "order_id": order.id,
        },
    }


@router.get("/jobs/{order_id}/file")
async def job_file(order_id: int, db: DBSession, x_agent_session: Session):
    _require_current(order_id, x_agent_session)
    order = await db.get(models.Order, order_id)
    if not order or not order.file_path.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "PDF not found")
    return FileResponse(str(order.file_path), media_type="application/pdf")


class JobResult(BaseModel):
    success: bool
    error: str | None = Field(default=None, max_length=500)


@router.post("/jobs/{order_id}/result")
async def job_result(order_id: int, body: JobResult, db: DBSession, x_agent_session: Session):
    _require_current(order_id, x_agent_session)
    new_status = "completed" if body.success else "failed"
    await db.execute(
        update(models.Order)
        .where(models.Order.id == order_id, models.Order.print_status == "printing")
        .values(print_status=new_status)
    )
    await db.commit()
    dispatcher.end_job()
    if body.success:
        log.info("Order %s printed", order_id)
    else:
        log.warning("Order %s failed on agent: %s", order_id, body.error)
    return {"status": new_status}

import asyncio
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status, Request, Query
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from utils.rate_limiter import limiter
from authentication.auth import CurrentAdmin, create_access_token, verify_password_async, DUMMY_PASSWORD_HASH
from services.audit_service import record_admin_action
import logging
from config import settings
from models import models
from models.database import DBSession
from schemas.schemas import OrderListResponse, AdminFailedPaymentResponse, PaginatedResponse
import math
from pathlib import Path
from fastapi.responses import FileResponse
from services.print_dispatcher import dispatcher
from schemas.admin import AuditEntry, UserAccessUpdate, UserAdministration

log = logging.getLogger("printease.admin")
router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/token")
@limiter.limit("5/minute")
async def login_admin(
    request: Request, response: Response, form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: DBSession
):
    result = await db.execute(select(models.Admin).where(func.lower(models.Admin.email) == form_data.username.lower()))
    admin = result.scalar_one_or_none()

    if not admin:
        await verify_password_async(form_data.password, DUMMY_PASSWORD_HASH)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    if not await verify_password_async(form_data.password, admin.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(
        data={
            "sub": str(admin.id),
            "type": "admin",
            "ver": admin.token_version,
        },
        expires_delta=access_token_expires,
    )

    response.set_cookie(
        key=settings.admin_cookie_name,
        value=access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=settings.access_token_expire_minutes * 60,
    )
    return {"message": "Successfully logged in as admin"}


@router.post("/logout")
async def logout_admin(response: Response, db: DBSession, current_admin: CurrentAdmin):
    from sqlalchemy import update

    await db.execute(
        update(models.Admin)
        .where(models.Admin.id == current_admin.id)
        .values(token_version=models.Admin.token_version + 1)
    )
    record_admin_action(db, current_admin.id, "admin.logout")
    await db.commit()
    response.delete_cookie(
        key=settings.admin_cookie_name, httponly=True, secure=settings.cookie_secure, samesite="strict"
    )
    return {"message": "Successfully logged out"}


@router.get("/orders", response_model=PaginatedResponse[OrderListResponse])
async def get_active_orders(
    db: DBSession,
    current_admin: CurrentAdmin,
    page: Annotated[int, Query(ge=1, le=10000)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    base_query = (
        select(models.Order)
        .join(models.Payment)
        .where(
            models.Payment.payment_status == "completed",
            models.Order.print_status.in_(["pending", "printing", "completed", "failed"]),
        )
    )

    count_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total = count_result.scalar() or 0

    result = await db.execute(
        base_query.options(joinedload(models.Order.payment))
        .order_by(models.Order.date_ordered.asc())
        .limit(size)
        .offset((page - 1) * size)
    )
    orders = result.scalars().all()

    return PaginatedResponse(
        items=orders, total=total, page=page, size=size, pages=math.ceil(total / size) if size > 0 else 0
    )


@router.get("/failed-payments", response_model=PaginatedResponse[AdminFailedPaymentResponse])
async def get_failed_payments(
    db: DBSession,
    current_admin: CurrentAdmin,
    page: Annotated[int, Query(ge=1, le=10000)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    base_query = (
        select(models.Order)
        .join(models.Payment)
        .where(
            models.Payment.payment_status.in_(
                ["failed", "refunded", "refund_pending", "refund_failed", "amount_mismatch_error"]
            )
        )
    )

    count_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total = count_result.scalar() or 0

    result = await db.execute(
        base_query.options(joinedload(models.Order.payment))
        .order_by(models.Order.date_ordered.desc())
        .limit(size)
        .offset((page - 1) * size)
    )
    orders = result.scalars().all()

    failed_payments = []
    for order in orders:
        failed_payments.append(
            AdminFailedPaymentResponse(
                order_id=order.id,
                order_date=order.date_ordered,
                cost=order.total_cost,
                payment_status=order.payment.payment_status if order.payment else "unknown",
                payment_datetime=order.payment.payment_datetime if order.payment else None,
            )
        )

    return PaginatedResponse(
        items=failed_payments, total=total, page=page, size=size, pages=math.ceil(total / size) if size > 0 else 0
    )


@router.post("/orders/{order_id}/deliver")
@limiter.limit("20/minute")
async def mark_order_delivered(request: Request, order_id: int, db: DBSession, current_admin: CurrentAdmin):
    result = await db.execute(select(models.Order).where(models.Order.id == order_id))
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if order.print_status != "completed":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Only completed prints can be marked as delivered"
        )

    order.print_status = "delivered"
    record_admin_action(db, current_admin.id, "order.deliver", order_id)
    await db.commit()

    file_path = Path(order.file_path)
    if await asyncio.to_thread(file_path.exists):
        try:
            await asyncio.to_thread(file_path.unlink)
        except Exception:
            log.exception("delivered_pdf_cleanup_failed", extra={"target_id": order_id})
            return {"message": "Order delivered; file cleanup requires operator attention"}

    await db.commit()
    return {"message": "Order marked as delivered and file deleted"}


@router.post("/orders/{order_id}/retry")
@limiter.limit("20/minute")
async def retry_failed_print(request: Request, order_id: int, db: DBSession, current_admin: CurrentAdmin):
    from models.database import acquire_transaction_advisory_lock

    await acquire_transaction_advisory_lock(db, namespace=2, key=order_id)
    result = await db.execute(
        select(models.Order).options(joinedload(models.Order.payment)).where(models.Order.id == order_id)
    )
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if order.print_status != "failed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only failed prints can be retried")
    if not order.payment or order.payment.payment_status != "completed":
        raise HTTPException(409, "Only paid orders without refunds can be retried")

    order.print_status = "pending"
    record_admin_action(db, current_admin.id, "order.retry", order_id)
    await db.commit()
    return {"message": "Order print status reset to pending"}


@router.get("/orders/{order_id}/pdf")
@limiter.limit("10/minute")
async def get_admin_order_pdf(request: Request, order_id: int, db: DBSession, current_admin: CurrentAdmin):

    result = await db.execute(
        select(models.Order).options(joinedload(models.Order.payment)).where(models.Order.id == order_id)
    )
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")

    if order.payment and order.payment.payment_status in [
        "failed",
        "refunded",
        "refund_pending",
        "amount_mismatch_error",
    ]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view PDF for orders with failed or pending refund payments.",
        )

    file_path = Path(order.file_path)
    if not await asyncio.to_thread(file_path.exists):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF file not found on disk.")

    return FileResponse(path=str(file_path), media_type="application/pdf", filename=f"order_{order.id}.pdf")


@router.get("/users", response_model=PaginatedResponse[UserAdministration])
async def list_users(
    db: DBSession,
    current_admin: CurrentAdmin,
    page: Annotated[int, Query(ge=1, le=10000)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    total = await db.scalar(select(func.count()).select_from(models.User)) or 0
    users = (
        await db.scalars(select(models.User).order_by(models.User.id.desc()).limit(size).offset((page - 1) * size))
    ).all()
    return {"items": users, "total": total, "page": page, "size": size, "pages": math.ceil(total / size)}


@router.patch("/users/{user_id}/access", response_model=UserAdministration)
@limiter.limit("20/minute")
async def update_user_access(
    request: Request, user_id: int, body: UserAccessUpdate, db: DBSession, current_admin: CurrentAdmin
):
    user = await db.get(models.User, user_id)
    if not user:
        raise HTTPException(404, "User not found")
    user.is_active = body.is_active
    from sqlalchemy import update

    await db.execute(
        update(models.User).where(models.User.id == user_id).values(token_version=models.User.token_version + 1)
    )
    record_admin_action(db, current_admin.id, "user.enable" if body.is_active else "user.disable", user_id)
    # A reason is required to encourage deliberate changes but is not logged as free text.
    await db.commit()
    return user


@router.get("/audit", response_model=PaginatedResponse[AuditEntry])
async def list_audit(
    db: DBSession,
    current_admin: CurrentAdmin,
    page: Annotated[int, Query(ge=1, le=10000)] = 1,
    size: Annotated[int, Query(ge=1, le=100)] = 20,
):
    total = await db.scalar(select(func.count()).select_from(models.AuditLog)) or 0
    rows = (
        await db.scalars(
            select(models.AuditLog).order_by(models.AuditLog.id.desc()).limit(size).offset((page - 1) * size)
        )
    ).all()
    return {"items": rows, "total": total, "page": page, "size": size, "pages": math.ceil(total / size)}


@router.get("/system")
async def system_status(db: DBSession, current_admin: CurrentAdmin):
    from models.database import engine

    failed = await db.scalar(
        select(func.count()).select_from(models.Order).where(models.Order.print_status == "failed")
    )
    anomalies = await db.scalar(
        select(func.count())
        .select_from(models.Payment)
        .where(models.Payment.payment_status.in_(["refund_pending", "refund_failed", "amount_mismatch_error"]))
    )
    return {
        "environment": settings.environment,
        "database_pool": engine.pool.status(),
        "failed_prints": failed,
        "payment_anomalies": anomalies,
        "agent_online": dispatcher.agent_online,
    }


@router.post("/orders/{order_id}/refund")
@limiter.limit("5/minute")
async def refund_order(request: Request, order_id: int, db: DBSession, current_admin: CurrentAdmin):
    from services.payment_service import issue_refund, RefundServiceError
    from models.database import acquire_transaction_advisory_lock

    await acquire_transaction_advisory_lock(db, namespace=2, key=order_id)
    order = await db.get(models.Order, order_id)
    if not order:
        raise HTTPException(404, "Order not found")
    if order.print_status not in {"failed", "cancelled", "refunded"}:
        raise HTTPException(409, "Only failed or cancelled prints can be refunded")
    record_admin_action(db, current_admin.id, "order.refund_requested", order_id)
    # issue_refund commits the pending state and audit before calling the provider.
    try:
        payment = await issue_refund(db, order_id)
    except RefundServiceError as exc:
        raise HTTPException(502, {"code": exc.code, "message": exc.message}) from exc
    return {"payment_status": payment.payment_status, "refund_status": payment.refund_status}


@router.post("/printer/pause")
async def pause_printer(request: Request, current_admin: CurrentAdmin, db: DBSession):
    async with dispatcher.lock:
        record_admin_action(db, current_admin.id, "printer.pause")
        await db.commit()
        dispatcher.is_running = False
    return {"message": "Stopped handing out print jobs"}


@router.post("/printer/resume")
async def resume_printer(request: Request, current_admin: CurrentAdmin, db: DBSession):
    ensure_authority = getattr(request.app.state, "ensure_authority", None)
    if ensure_authority and not await ensure_authority():
        raise HTTPException(503, "Printer coordination is temporarily unavailable")
    async with dispatcher.lock:
        record_admin_action(db, current_admin.id, "printer.resume")
        await db.commit()
        dispatcher.is_running = True
    return {"message": "Started handing out print jobs"}


@router.get("/printer/status")
async def printer_status(current_admin: CurrentAdmin):
    return {
        "is_running": dispatcher.is_running,
        "status": "active" if dispatcher.is_running else "paused",
        "agent_online": dispatcher.agent_online,
        "agent_printer": dispatcher.agent_printer,
        "current_order_id": dispatcher.current["order_id"] if dispatcher.current else None,
    }

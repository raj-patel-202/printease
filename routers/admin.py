import asyncio
from datetime import timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status, Request
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.orm import joinedload

from utils.rate_limiter import limiter
from authentication.auth import CurrentAdmin, create_access_token, verify_password_async
from config import settings
from models import models
from models.database import DBSession
from schemas.schemas import OrderListResponse, AdminFailedPaymentResponse, PaginatedResponse
import math
from pathlib import Path
from fastapi.responses import FileResponse

router = APIRouter(prefix="/api/admin", tags=["admin"])

@router.post("/token")
@limiter.limit("5/minute")
async def login_admin(request: Request, response: Response, form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: DBSession):
    result = await db.execute(select(models.Admin).where(func.lower(models.Admin.email) == form_data.username.lower()))
    admin = result.scalar_one_or_none()

    if not admin:
        await verify_password_async(form_data.password, "$argon2id$v=19$m=65536,t=3,p=4$0000000000000000000000$0000000000000000000000000000000000000000000")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")
    
    if not await verify_password_async(form_data.password, admin.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(data={"sub": str(admin.id), "type": "admin",}, expires_delta=access_token_expires)

    response.set_cookie(
        key=settings.admin_cookie_name,
        value=access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict",
        max_age=settings.access_token_expire_minutes * 60
    )
    return {"message": "Successfully logged in as admin"}

@router.post("/logout")
async def logout_admin(response: Response):
    response.delete_cookie(
        key=settings.admin_cookie_name,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="strict"
    )
    return {"message": "Successfully logged out"}

@router.get("/orders", response_model=PaginatedResponse[OrderListResponse])
async def get_active_orders(db: DBSession, current_admin: CurrentAdmin, page: int = 1, size: int = 20):
    base_query = (
        select(models.Order)
        .join(models.Payment)
        .where(
            models.Payment.payment_status == 'completed',
            models.Order.print_status.in_(["pending", "printing", "completed", "failed"])
        )
    )

    count_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total = count_result.scalar() or 0

    result = await db.execute(
        base_query
        .options(joinedload(models.Order.payment))
        .order_by(models.Order.date_ordered.asc())
        .limit(size)
        .offset((page - 1) * size)
    )
    orders = result.scalars().all()
    
    return PaginatedResponse(
        items=orders,
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if size > 0 else 0
    )

@router.get("/failed-payments", response_model=PaginatedResponse[AdminFailedPaymentResponse])
async def get_failed_payments(db: DBSession, current_admin: CurrentAdmin, page: int = 1, size: int = 20):
    base_query = (
        select(models.Order)
        .join(models.Payment)
        .where(
            models.Payment.payment_status.in_(["failed", "refunded", "refund_pending", "amount_mismatch_error"])
        )
    )

    count_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total = count_result.scalar() or 0

    result = await db.execute(
        base_query
        .options(joinedload(models.Order.payment))
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
                payment_status=order.payment.payment_status if order.payment else 'unknown',
                payment_datetime=order.payment.payment_datetime if order.payment else None
            )
        )
        
    return PaginatedResponse(
        items=failed_payments,
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if size > 0 else 0
    )


@router.post("/orders/{order_id}/deliver")
@limiter.limit("20/minute")
async def mark_order_delivered(request: Request, order_id: int, db: DBSession, current_admin: CurrentAdmin):
    result = await db.execute(select(models.Order).where(models.Order.id == order_id))
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")

    if order.print_status != "completed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only completed prints can be marked as delivered")
        
    order.print_status = "delivered"
    
    file_path = Path(order.file_path)
    if await asyncio.to_thread(file_path.exists):
        try:
            await asyncio.to_thread(file_path.unlink)
        except Exception as e:
            print(f"Failed to delete file {file_path}: {e}")

    await db.commit()
    return {"message": "Order marked as delivered and file deleted"}


@router.post("/orders/{order_id}/retry")
@limiter.limit("20/minute")
async def retry_failed_print(request: Request, order_id: int, db: DBSession, current_admin: CurrentAdmin):
    result = await db.execute(select(models.Order).where(models.Order.id == order_id))
    order = result.scalar_one_or_none()
    
    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found")
        
    if order.print_status != "failed":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Only failed prints can be retried")
        
    order.print_status = "pending"
    await db.commit()
    return {"message": "Order print status reset to pending"}


@router.get("/orders/{order_id}/pdf")
@limiter.limit("10/minute")
async def get_admin_order_pdf(request: Request, order_id: int, db: DBSession, current_admin: CurrentAdmin):

    result = await db.execute(
        select(models.Order)
        .options(joinedload(models.Order.payment))
        .where(models.Order.id == order_id)
    )
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found."
        )

    if order.payment and order.payment.payment_status in ["failed", "refunded", "refund_pending", "amount_mismatch_error"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot view PDF for orders with failed or pending refund payments."
        )

    file_path = Path(order.file_path)
    if not await asyncio.to_thread(file_path.exists):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="PDF file not found on disk."
        )

    return FileResponse(
        path=str(file_path),
        media_type="application/pdf",
        filename=f"order_{order.id}.pdf"
    )

from services.print_dispatcher import dispatcher

@router.post("/printer/pause")
async def pause_printer(request: Request, current_admin: CurrentAdmin):
    dispatcher.is_running = False
    return {"message": "Stopped handing out print jobs"}

@router.post("/printer/resume")
async def resume_printer(request: Request, current_admin: CurrentAdmin):
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

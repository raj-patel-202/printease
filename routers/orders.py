import asyncio
import aiofiles
from pathlib import Path
from fastapi import APIRouter, File, Form, HTTPException, Response, UploadFile, status, Request
from fastapi.responses import FileResponse
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from authentication.auth import CurrentUser
from config import settings
from models import models
from models.database import DBSession, acquire_transaction_advisory_lock
from schemas.schemas import (
    OrderCreate,
    OrderBase,
    OrderResponsePrivate,
    OrderStatusResponse,
    CheckoutResponse,
    ReceiptResponse,
)
from utils.file_validation import (
    generate_secure_filename,
    validate_and_count_pdf,
    FileSizeExceededError,
    InvalidFormatError,
    PDFProcessingError,
)
from utils.printing_cost import cost_calculation
from utils.queue_manager import queue_manager
from utils.rate_limiter import limiter
from utils.api_errors import api_error
import logging
import shutil

log = logging.getLogger("printease.orders")

router = APIRouter(prefix="/api/orders", tags=["orders"])


async def _unlink_if_exists(path: Path) -> None:
    await asyncio.to_thread(path.unlink, missing_ok=True)


@router.post("/uploads", response_model=OrderResponsePrivate)
@limiter.limit("10/minute")
async def create_upload_file(
    request: Request,
    db: DBSession,
    current_user: CurrentUser,
    file: UploadFile = File(..., description="The PDF document to print"),
    options: str = Form(..., description="JSON string of PrintOptions"),
):
    await acquire_transaction_advisory_lock(db, namespace=1, key=current_user.id)

    result = await db.execute(
        select(models.Order)
        .join(models.Payment)
        .options(joinedload(models.Order.payment))
        .where(models.Order.user_id == current_user.id, models.Payment.payment_status == "pending")
    )

    existing_pending_order = result.scalars().first()

    if existing_pending_order and existing_pending_order.payment:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={
                "message": "You already have an order waiting for checkout.",
                "existing_token": existing_pending_order.payment.receipt_token,
            },
        )

    try:
        print_metadata = OrderBase.model_validate_json(options)
    except ValidationError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=e.errors(include_input=False, include_context=False),
        )
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON string provided in 'options'."
        )

    try:
        actual_total_pages = await validate_and_count_pdf(file, max_size_mb=settings.max_file_size_mb)
    except FileSizeExceededError as e:
        raise HTTPException(status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE, detail=str(e))
    except InvalidFormatError as e:
        raise HTTPException(status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE, detail=str(e))
    except PDFProcessingError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))

    UPLOAD_DIR = settings.upload_dir / str(current_user.id)
    await asyncio.to_thread(UPLOAD_DIR.mkdir, parents=True, exist_ok=True)
    free_bytes = (await asyncio.to_thread(shutil.disk_usage, UPLOAD_DIR)).free
    if free_bytes < (settings.min_free_upload_mb + settings.max_file_size_mb) * 1024 * 1024:
        raise HTTPException(503, "Document storage is temporarily unavailable; retry later")

    safe_filename = generate_secure_filename(file.filename)
    file_path = UPLOAD_DIR / safe_filename

    try:
        async with aiofiles.open(file_path, "wb") as out_file:
            while content := await file.read(1024 * 1024):
                await out_file.write(content)
    except BaseException:
        await _unlink_if_exists(file_path)
        raise

    final_cost = cost_calculation(
        print_metadata.color_mode,
        settings.cost_per_page_bw,
        settings.cost_per_page_co,
        print_metadata.copies,
        actual_total_pages,
        print_metadata.side_mode,
        settings.double_sided_discount_pct,
    )

    try:
        valid_db_order = OrderCreate(
            **print_metadata.model_dump(),
            file_name=safe_filename,
            user_id=current_user.id,
            total_pages=actual_total_pages,
            total_cost=final_cost,
            print_status="pending",
        )
    except ValidationError:
        await _unlink_if_exists(file_path)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Internal validation error while compiling order."
        )

    new_order = models.Order(**valid_db_order.model_dump())
    new_payment = models.Payment(order=new_order, currency=settings.currency)

    try:
        db.add(new_order)
        db.add(new_payment)
        await db.commit()

        res = await db.execute(
            select(models.Order).options(joinedload(models.Order.payment)).where(models.Order.id == new_order.id)
        )
        new_order = res.scalar_one()
        return new_order

    except IntegrityError:
        await db.rollback()
        await _unlink_if_exists(file_path)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="An order with these details already exists."
        )
    except Exception:
        await db.rollback()
        await _unlink_if_exists(file_path)
        log.exception("order_save_failed")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="An error occurred while saving the order."
        )


@router.get("/checkout-details", response_model=CheckoutResponse)
async def get_checkout_details(order: str, db: DBSession, current_user: CurrentUser):
    if not order:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Order ID missing.")

    result = await db.execute(
        select(models.Order)
        .join(models.Payment)
        .options(joinedload(models.Order.payment))
        .where(models.Payment.receipt_token == order)
    )
    db_order = result.scalar_one_or_none()

    if not db_order or db_order.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")

    if not db_order.payment:
        raise api_error(status.HTTP_404_NOT_FOUND, "payment_not_found", "Payment record not found.")
    if db_order.payment.payment_status == "amount_mismatch_error":
        raise api_error(
            status.HTTP_409_CONFLICT,
            "amount_mismatch_review",
            "This order has a payment amount discrepancy and requires manual review by staff. Please contact support.",
        )
    if db_order.payment.payment_status != "pending":
        raise api_error(
            status.HTTP_409_CONFLICT,
            db_order.payment.payment_status,
            "This order has already been paid or cancelled.",
        )

    price_per_page = settings.cost_per_page_bw if db_order.color_mode == "bw" else settings.cost_per_page_co
    total_pages_printed = db_order.total_pages * db_order.copies
    db_order.base_cost = float(total_pages_printed * price_per_page)
    db_order.discount_amount = float(db_order.base_cost - db_order.total_cost)
    return db_order


@router.get("/receipt-details", response_model=ReceiptResponse)
async def get_receipt_details(receipt: str, db: DBSession, current_user: CurrentUser):
    if not receipt:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Receipt token missing.")

    result = await db.execute(
        select(models.Order)
        .join(models.Payment)
        .options(joinedload(models.Order.payment))
        .where(models.Payment.receipt_token == receipt)
    )
    order = result.scalar_one_or_none()

    if not order or order.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")

    price_per_page = settings.cost_per_page_bw if order.color_mode == "bw" else settings.cost_per_page_co
    total_pages_printed = order.total_pages * order.copies
    order.base_cost = float(total_pages_printed * price_per_page)
    order.discount_amount = float(order.base_cost - order.total_cost)
    return order


@router.get("/{order_id}/status", response_model=OrderStatusResponse)
async def get_queue_position(order_id: int, db: DBSession, current_user: CurrentUser):
    result = await db.execute(
        select(models.Order.print_status, models.Payment.payment_status)
        .where(models.Order.id == order_id, models.Order.user_id == current_user.id)
        .join(models.Payment)
    )

    order = result.one_or_none()
    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Order not found or you are not authorized to view it."
        )

    if order.payment_status not in ["completed", "cancelled", "refunded"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Order has not been placed yet. Complete payment first."
        )

    queue_data = await queue_manager.get_order_status(order_id, db)

    if queue_data:
        return queue_data

    return {"id": order_id, "print_status": order.print_status, "queue_position": None, "estimated_wait_minutes": 0}


@router.get("/{order_id}/pdf")
@limiter.limit("10/minute")
async def get_order_pdf(request: Request, order_id: int, db: DBSession, current_user: CurrentUser):
    result = await db.execute(
        select(models.Order).where(models.Order.id == order_id, models.Order.user_id == current_user.id)
    )
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Order not found or you are not authorized to view it."
        )

    if order.print_status == "delivered":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="PDF files are permanently deleted after the order is delivered.",
        )

    file_path = Path(order.file_path)
    if not await asyncio.to_thread(file_path.exists):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="PDF file not found on disk.")

    return FileResponse(path=str(file_path), media_type="application/pdf", filename=f"order_{order.id}.pdf")


@router.delete("/{token}")
async def cancel_order(token: str, db: DBSession, current_user: CurrentUser):
    result = await db.execute(
        select(models.Order)
        .join(models.Payment)
        .options(joinedload(models.Order.payment))
        .where(models.Payment.receipt_token == token)
    )
    order = result.scalar_one_or_none()

    if not order:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Order not found.")

    if order.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to cancel this order.")

    await acquire_transaction_advisory_lock(db, namespace=2, key=order.id)
    await db.refresh(order, attribute_names=["payment", "print_status"])

    if not order.payment or order.payment.payment_status != "pending":
        raise api_error(
            status.HTTP_409_CONFLICT,
            "order_not_cancellable",
            "Only an unpaid pending order can be cancelled.",
        )

    file_path = Path(order.file_path)

    order.payment.payment_status = "cancelled"
    order.print_status = "cancelled"
    await db.commit()

    try:
        await _unlink_if_exists(file_path)
    except Exception:
        log.exception("cancelled_pdf_cleanup_failed", extra={"target_id": order.id})

    return Response(status_code=status.HTTP_204_NO_CONTENT)

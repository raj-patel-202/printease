import json
from datetime import UTC, datetime

import razorpay
from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import RedirectResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from authentication.auth import CurrentUser
from config import settings
from models import models
from models.database import DBSession, acquire_transaction_advisory_lock
from services.payment_service import (
    PAYMENT_TERMINAL_STATES,
    PaymentServiceError,
    RefundServiceError,
    create_razorpay_order as create_provider_order,
    fetch_razorpay_order,
    fetch_razorpay_payment,
    get_payment_by_order_id,
    process_captured_payment,
    set_razorpay_order_id_if_null,
    verify_browser_signature_async,
    verify_webhook_signature_async,
)
from utils.rate_limiter import limiter

router = APIRouter(prefix="/api/payments", tags=["payments"])


def checkout_redirect(code: str, receipt_token: str | None = None) -> RedirectResponse:
    if receipt_token:
        url = f"/checkout?order={receipt_token}&error={code}"
    else:
        url = f"/?error={code}"
    return RedirectResponse(url=url, status_code=status.HTTP_303_SEE_OTHER)


@router.post("/verify-payment")
async def verify_payment(request: Request, db: DBSession):
    form_data = await request.form()
    razorpay_payment_id = form_data.get("razorpay_payment_id")
    razorpay_order_id = form_data.get("razorpay_order_id")
    razorpay_signature = form_data.get("razorpay_signature")

    if not all([razorpay_payment_id, razorpay_order_id, razorpay_signature]):
        return checkout_redirect("missing_parameters")

    # We don't have a receipt_token yet — try to obtain it early
    receipt_token = None

    try:
        await verify_browser_signature_async(
            {
                "razorpay_order_id": razorpay_order_id,
                "razorpay_payment_id": razorpay_payment_id,
                "razorpay_signature": razorpay_signature,
            }
        )
        provider_payment = await fetch_razorpay_payment(razorpay_payment_id)
        provider_order = await fetch_razorpay_order(razorpay_order_id)
        local_order_id = provider_order.get("notes", {}).get("db_order_id")
        if not local_order_id:
            return checkout_redirect("missing_order_metadata", receipt_token)

        payment = await get_payment_by_order_id(db, int(local_order_id))
        if not payment:
            return checkout_redirect("order_not_found", receipt_token)

        receipt_token = payment.receipt_token

        if provider_payment.get("status") != "captured":
            return RedirectResponse(
                url=f"/checkout?order={receipt_token}&status=processing",
                status_code=status.HTTP_303_SEE_OTHER,
            )

        payment = await process_captured_payment(
            db,
            provider_payment,
            razorpay_order_id,
            int(local_order_id),
        )
        if payment.payment_status in {"refund_pending", "refunded"}:
            return checkout_redirect("order_cancelled_refund_initiated", receipt_token)
        if payment.payment_status == "refund_failed":
            return checkout_redirect("refund_failed", receipt_token)

        response = RedirectResponse(
            url=f"/order?receipt={receipt_token}",
            status_code=status.HTTP_303_SEE_OTHER,
        )
        response.delete_cookie("pending_checkout")
        return response
    except razorpay.errors.SignatureVerificationError:
        return checkout_redirect("verification_failed", receipt_token)
    except RefundServiceError as exc:
        await db.rollback()
        return checkout_redirect(exc.code, receipt_token)
    except PaymentServiceError as exc:
        await db.rollback()
        return checkout_redirect(exc.code, receipt_token)
    except Exception as exc:
        print(f"Payment verification error: {exc}")
        await db.rollback()
        return checkout_redirect("internal_server_error", receipt_token)


@router.post("/webhook")
@limiter.exempt
async def razorpay_webhook(request: Request, db: DBSession):
    body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature")
    event_id = request.headers.get("X-Razorpay-Event-Id")

    if not signature:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Razorpay signature")
    if not event_id:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Missing Razorpay event ID")

    try:
        await verify_webhook_signature_async(body.decode("utf-8"), signature)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid webhook signature")

    try:
        payload = json.loads(body)
    except Exception:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid JSON body")

    event_type = payload.get("event", "unknown")
    event = models.RazorpayWebhookEvent(event_id=event_id, event_type=event_type, payload=payload)
    db.add(event)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        existing = await db.get(models.RazorpayWebhookEvent, event_id)
        if existing and existing.status in {"processed", "ignored"}:
            return {"status": "ok", "message": "Duplicate event ignored"}
        event = existing

    if not event:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Webhook event unavailable")

    if event_type != "payment.captured":
        event.status = "ignored"
        event.processed_at = datetime.now(UTC)
        await db.commit()
        return {"status": "ok", "message": "Unsupported event ignored"}

    entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
    razorpay_payment_id = entity.get("id")
    razorpay_order_id = entity.get("order_id")
    if not razorpay_payment_id or not razorpay_order_id or entity.get("status") != "captured":
        event.status = "failed"
        event.error_message = "Invalid captured payment payload"
        await db.commit()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid captured payment payload")

    try:
        provider_order = await fetch_razorpay_order(razorpay_order_id)
        local_order_id = provider_order.get("notes", {}).get("db_order_id")
        if not local_order_id:
            raise PaymentServiceError("missing_order_metadata", "Order metadata is missing.")

        await process_captured_payment(db, entity, razorpay_order_id, int(local_order_id))
        event.status = "processed"
        event.processed_at = datetime.now(UTC)
        event.error_message = None
        await db.commit()
        return {"status": "ok"}
    except Exception as exc:
        await db.rollback()
        event = await db.get(models.RazorpayWebhookEvent, event_id)
        if event:
            event.status = "failed"
            event.error_message = str(exc)
            await db.commit()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Webhook processing failed")


@router.post("/{order_id}/create-razorpay-order")
@limiter.limit("5/minute")
async def create_razorpay_order(request: Request, order_id: int, db: DBSession, current_user: CurrentUser):
    await acquire_transaction_advisory_lock(db, namespace=2, key=order_id)

    payment = await get_payment_by_order_id(db, order_id)
    if not payment or payment.order.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "order_not_found", "message": "Order not found."})
    if payment.payment_status in PAYMENT_TERMINAL_STATES:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "terminal_payment_state", "message": "This order can no longer be paid."},
        )

    amount = payment.order.total_cost * 100

    # If a Razorpay order already exists, reuse it if it matches
    if payment.razorpay_order_id:
        try:
            provider_order = await fetch_razorpay_order(payment.razorpay_order_id)
            if provider_order.get("amount") == amount and provider_order.get("currency") == payment.currency:
                await db.commit()
                return provider_order
        except Exception:
            pass

    # Create a new Razorpay order
    provider_order = await create_provider_order(
        {
            "amount": amount,
            "currency": payment.currency,
            "receipt": payment.receipt_token,
            "notes": {"db_order_id": payment.order_id},
        }
    )

    was_set = await set_razorpay_order_id_if_null(db, payment.id, provider_order["id"])
    if not was_set:
        await db.refresh(payment)
        if payment.razorpay_order_id:
            try:
                existing_order = await fetch_razorpay_order(payment.razorpay_order_id)
                await db.commit()
                return existing_order
            except Exception:
                pass

    await db.commit()
    return provider_order

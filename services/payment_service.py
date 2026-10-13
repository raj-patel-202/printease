import asyncio
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any, Callable

import razorpay
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import joinedload

from config import settings
from models import models

PAYMENT_TERMINAL_STATES = {
    "completed",
    "cancelled",
    "refund_pending",
    "refunded",
    "refund_failed",
    "amount_mismatch_error",
}
PAYMENT_ANOMALY_STATES = {"amount_mismatch_error", "refund_pending", "refund_failed"}

def get_razorpay_client():
    return razorpay.Client(
        auth=(settings.razorpay_api_key, settings.razorpay_api_secret.get_secret_value())
    )


@dataclass
class PaymentServiceError(Exception):
    code: str
    message: str

    def __str__(self) -> str:
        return self.message


@dataclass
class RefundServiceError(PaymentServiceError):
    pass


async def call_razorpay(func: Callable[..., Any], *args, **kwargs) -> Any:
    kwargs.setdefault("timeout", settings.razorpay_timeout_seconds)
    return await asyncio.wait_for(
        asyncio.to_thread(func, *args, **kwargs),
        timeout=settings.razorpay_timeout_seconds + 1,
    )


async def fetch_razorpay_payment(payment_id: str) -> dict:
    client = get_razorpay_client()
    return await call_razorpay(client.payment.fetch, payment_id)


async def fetch_razorpay_order(order_id: str) -> dict:
    client = get_razorpay_client()
    return await call_razorpay(client.order.fetch, order_id)


async def create_razorpay_order(data: dict) -> dict:
    client = get_razorpay_client()
    return await call_razorpay(client.order.create, data=data)


def verify_browser_signature(params: dict) -> None:
    client = get_razorpay_client()
    client.utility.verify_payment_signature(params)


async def verify_browser_signature_async(params: dict) -> None:
    await asyncio.to_thread(verify_browser_signature, params)


def verify_webhook_signature(body: str, signature: str) -> None:
    client = get_razorpay_client()
    client.utility.verify_webhook_signature(
        body, signature, settings.razorpay_webhook_secret.get_secret_value()
    )


async def verify_webhook_signature_async(body: str, signature: str) -> None:
    await asyncio.to_thread(verify_webhook_signature, body, signature)


async def get_payment_by_order_id(db: AsyncSession, order_id: int) -> models.Payment | None:
    result = await db.execute(
        select(models.Payment)
        .options(joinedload(models.Payment.order))
        .where(models.Payment.order_id == order_id)
    )
    return result.scalar_one_or_none()


async def set_razorpay_order_id_if_null(db: AsyncSession, payment_id: int, rzp_order_id: str) -> bool:
    stmt = (
        update(models.Payment)
        .where(models.Payment.id == payment_id, models.Payment.razorpay_order_id.is_(None))
        .values(razorpay_order_id=rzp_order_id)
    )
    result = await db.execute(stmt)
    return result.rowcount > 0


async def process_captured_payment(
    db: AsyncSession, provider_payment: dict, razorpay_order_id: str, local_order_id: int
) -> models.Payment:
    payment = await get_payment_by_order_id(db, local_order_id)
    if not payment:
        raise PaymentServiceError("payment_not_found", f"No payment record for order {local_order_id}")

    if payment.payment_status in PAYMENT_TERMINAL_STATES:
        return payment

    if payment.razorpay_order_id and payment.razorpay_order_id != razorpay_order_id:
        raise PaymentServiceError("order_mismatch", "Razorpay order ID mismatch.")

    if not payment.razorpay_order_id:
        payment.razorpay_order_id = razorpay_order_id

    payment.razorpay_payment_id = provider_payment.get("id")
    payment.payment_method = provider_payment.get("method")
    
    amount_paid = provider_payment.get("amount", 0)
    expected_amount = int(payment.order.total_cost * 100)

    if amount_paid != expected_amount:
        payment.payment_status = "amount_mismatch_error"
        payment.order.print_status = "failed"
        await db.commit()
        
        try:
            await issue_refund(db, local_order_id)
        except Exception as e:
            pass

        raise PaymentServiceError("amount_mismatch", "Amount paid does not match the order total.")

    payment.payment_status = "completed"
    payment.payment_datetime = datetime.now(UTC)
    await db.commit()
    return payment


async def issue_refund(db: AsyncSession, order_id: int) -> models.Payment:
    payment = await get_payment_by_order_id(db, order_id)
    if not payment:
        raise RefundServiceError("payment_not_found", "Payment record not found.")

    if payment.payment_status in {"refunded", "refund_pending"}:
        return payment

    if not payment.razorpay_payment_id:
        raise RefundServiceError("no_payment_id", "Cannot refund: no Razorpay payment ID.")

    payment.payment_status = "refund_pending"
    await db.commit()

    try:
        client = get_razorpay_client()
        refund_data = await call_razorpay(
            client.payment.refund,
            payment.razorpay_payment_id,
            {"notes": {"reason": "Amount mismatch or admin requested"}}
        )
        payment.payment_status = "refunded"
        payment.order.print_status = "refunded"
        payment.refund_id = refund_data.get("id")
        await db.commit()
        return payment
    except Exception as exc:
        payment.payment_status = "refund_failed"
        await db.commit()
        raise RefundServiceError("refund_api_error", f"Razorpay refund failed: {exc}")

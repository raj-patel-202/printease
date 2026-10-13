from typing import Optional
import uuid
from pathlib import Path
from datetime import datetime, UTC

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship


from models.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    username: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    orders: Mapped[list["Order"]] = relationship(
        "Order",
        back_populates="user",
        cascade="all, delete-orphan"
    )

class Order(Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)

    # Print Job Data
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    copies: Mapped[int] = mapped_column(Integer, nullable=False)
    orientation: Mapped[str] = mapped_column(String(20), nullable=False)
    side_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    paper_size: Mapped[str] = mapped_column(String(16), nullable=False)
    total_pages: Mapped[int] = mapped_column(Integer, nullable=False)
    color_mode: Mapped[str] = mapped_column(String(20), nullable=False)
    total_cost: Mapped[int] = mapped_column(Integer, nullable=False)

    date_ordered: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        index=True
    )

    print_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)

    user: Mapped["User"] = relationship("User", back_populates="orders")
    payment: Mapped[Optional["Payment"]] = relationship("Payment", back_populates="order", uselist=False, cascade="all, delete-orphan")

    @property
    def file_path(self) -> Path:
        UPLOAD_DIR = Path("resource/uploads")
        return UPLOAD_DIR / str(self.user_id) / self.file_name


class Payment(Base):
    __tablename__ = "payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id", ondelete="CASCADE"), unique=True)

    payment_status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    receipt_token: Mapped[str] = mapped_column(String(255), default=lambda: str(uuid.uuid4()), unique=True)
    razorpay_payment_id: Mapped[str] = mapped_column(String(100), nullable=True, unique=True)
    razorpay_order_id: Mapped[str] = mapped_column(String(100), nullable=True, unique=True)
    payment_datetime: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None,
        index=True
    )
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    refund_id: Mapped[Optional[str]] = mapped_column(String(100), nullable=True, unique=True)
    refund_status: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    refund_idempotency_key: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, unique=True)

    order: Mapped["Order"] = relationship("Order", back_populates="payment")


class RazorpayWebhookEvent(Base):
    __tablename__ = "razorpay_webhook_events"

    event_id: Mapped[str] = mapped_column(String(100), primary_key=True)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="received", index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)


class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(200), nullable=False)

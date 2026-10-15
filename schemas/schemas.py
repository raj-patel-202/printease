from datetime import datetime, timezone
from typing import Annotated, Literal, Optional, Generic, TypeVar, List
from pydantic import BaseModel, ConfigDict, EmailStr, Field, StringConstraints, field_serializer

T = TypeVar("T")


class PaginatedResponse(BaseModel, Generic[T]):
    items: List[T]
    total: int
    page: int
    size: int
    pages: int


def _ensure_utc(v: datetime | None) -> str | None:
    if v is None:
        return None
    if v.tzinfo is None:
        v = v.replace(tzinfo=timezone.utc)
    return v.isoformat()


# USER SCHEMAS
class UserBase(BaseModel):
    username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
    email: EmailStr


class UserCreate(UserBase):
    password: Annotated[str, Field(min_length=8, max_length=128, repr=False)]


class UserPublic(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: Annotated[str, Field(min_length=1, max_length=50)]
    email: EmailStr


class UserPrivate(UserPublic):
    email: EmailStr
    created_at: datetime

    @field_serializer("created_at")
    def serialize_created_at(self, v: datetime | None, _info) -> str | None:
        return _ensure_utc(v)


class UsernameUpdate(BaseModel):
    new_username: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=50)]
    password: Annotated[str, Field(min_length=8, max_length=128, repr=False)]


class DeleteAccountRequest(BaseModel):
    password: Annotated[str, Field(min_length=8, max_length=128, repr=False)]


class PasswordUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: Annotated[str, Field(min_length=8, max_length=128, repr=False)]
    new_password: Annotated[str, Field(min_length=12, max_length=128, repr=False)]


# ORDER SCHEMAS
class OrderBase(BaseModel):
    copies: Annotated[int, Field(ge=1, le=10, description="Number of copies to print")]
    color_mode: Literal["bw", "color"]
    side_mode: Literal["single", "double"]
    paper_size: Literal["A4", "A3", "Letter", "Legal"]
    orientation: Literal["portrait", "landscape"]


class OrderCreate(OrderBase):
    file_name: Annotated[str, Field(min_length=1, max_length=255, description="file name")]
    user_id: Annotated[int, Field(description="ID of the user placing the order")]
    total_pages: Annotated[int, Field(ge=1, description="Total pages in the document")]
    total_cost: Annotated[int, Field(ge=0, description="Total calculated cost of the job")]

    print_status: Literal["pending", "printing", "completed", "delivered", "failed", "cancelled", "refunded"] = (
        "pending"
    )


# PAYMENT SCHEMAS
class PaymentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    order_id: int
    payment_status: str
    receipt_token: str
    razorpay_payment_id: Optional[str] = None
    razorpay_order_id: Optional[str] = None
    payment_datetime: Optional[datetime] = None
    currency: str
    refund_id: Optional[str] = None
    refund_status: Optional[str] = None

    @field_serializer("payment_datetime")
    def serialize_payment_datetime(self, v: datetime | None, _info) -> str | None:
        return _ensure_utc(v)


# RESPONSE SCHEMAS
class OrderResponsePrivate(OrderBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_name: str
    total_pages: Annotated[int, Field(ge=1, description="Total pages in the document")]
    total_cost: Annotated[int, Field(ge=0, description="Total calculated cost of the job")]

    print_status: str
    date_ordered: datetime
    payment: Optional[PaymentResponse] = None

    @field_serializer("date_ordered")
    def serialize_date_ordered(self, v: datetime | None, _info) -> str | None:
        return _ensure_utc(v)


class OrderListResponse(OrderBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_name: str
    total_pages: Annotated[int, Field(ge=1, description="Total pages in the document")]
    total_cost: Annotated[int, Field(ge=1, description="Total calculated cost of the job")]
    print_status: str
    date_ordered: datetime
    payment: Optional[PaymentResponse] = None

    @field_serializer("date_ordered")
    def serialize_date_ordered(self, v: datetime | None, _info) -> str | None:
        return _ensure_utc(v)


class OrderStatusResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    print_status: str
    queue_position: int | None = None
    estimated_wait_minutes: float = 0.0


class CheckoutResponse(OrderBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    total_pages: Annotated[int, Field(ge=1)]
    total_cost: Annotated[int, Field(ge=1)]
    date_ordered: datetime
    base_cost: float
    discount_amount: float

    @field_serializer("date_ordered")
    def serialize_date_ordered(self, v: datetime | None, _info) -> str | None:
        return _ensure_utc(v)


class ReceiptResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    file_name: str
    copies: int
    total_pages: int
    color_mode: str
    side_mode: str
    paper_size: str
    orientation: str
    total_cost: int
    print_status: str
    date_ordered: datetime
    payment: Optional[PaymentResponse] = None
    base_cost: float
    discount_amount: float

    @field_serializer("date_ordered")
    def serialize_date_ordered(self, v: datetime | None, _info) -> str | None:
        return _ensure_utc(v)


class AdminFailedPaymentResponse(BaseModel):
    order_id: int
    order_date: datetime
    cost: int
    payment_status: str
    payment_datetime: Optional[datetime] = None

    @field_serializer("order_date", "payment_datetime")
    def serialize_date(self, v: datetime | None, _info) -> str | None:
        return _ensure_utc(v)

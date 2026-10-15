"""Validate signed provider data before it can touch persisted financial state."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field

ProviderID = Annotated[str, Field(min_length=1, max_length=100, strict=True)]


class WebhookEnvelope(BaseModel):
    event: ProviderID
    payload: dict = Field(default_factory=dict)


class CapturedPayment(BaseModel):
    id: ProviderID
    order_id: ProviderID
    currency: Annotated[str, Field(pattern=r"^[A-Z]{3}$", strict=True)]
    amount: Annotated[int, Field(gt=0, strict=True)]
    status: Literal["captured"]


class RefundEntity(BaseModel):
    id: ProviderID
    payment_id: ProviderID
    amount: Annotated[int, Field(gt=0, strict=True)]
    status: Literal["processed", "failed"]

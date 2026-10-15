"""Administrative request/response contracts; never expose password hashes."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class UserAdministration(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    username: str
    email: str
    is_active: bool
    created_at: datetime


class UserAccessUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    is_active: bool
    reason: str = Field(min_length=5, max_length=200)


class AuditEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    actor_id: int
    action: str
    target_id: int | None
    request_id: str
    created_at: datetime

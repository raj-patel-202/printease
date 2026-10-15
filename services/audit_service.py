"""Audit metadata deliberately excludes passwords, tokens, emails and documents."""

from core.logging import request_id
from models.models import AuditLog


def record_admin_action(db, admin_id: int, action: str, target_id: int | None = None) -> None:
    db.add(AuditLog(actor_id=admin_id, action=action, target_id=target_id, request_id=request_id.get()))

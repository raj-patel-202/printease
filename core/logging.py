"""JSON stdout logs for Docker/journald collectors, correlated by request ID."""

import json
import logging
from contextvars import ContextVar
from datetime import UTC, datetime

request_id: ContextVar[str] = ContextVar("request_id", default="-")


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(UTC).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": request_id.get(),
        }
        for name in ("method", "route", "status_code", "duration_ms", "action", "actor_id", "target_id"):
            if hasattr(record, name):
                payload[name] = getattr(record, name)
        if record.exc_info:
            # Keep exception types and stack locations without secret-bearing exception messages.
            import traceback

            payload["exception_type"] = record.exc_info[0].__name__
            payload["stack"] = [
                f"{frame.filename}:{frame.lineno}:{frame.name}" for frame in traceback.extract_tb(record.exc_info[2])
            ]
        return json.dumps(payload, ensure_ascii=False)


def configure_logging(level: str) -> None:
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    for name in ("uvicorn", "uvicorn.error"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True
    access = logging.getLogger("uvicorn.access")
    access.handlers = []
    access.propagate = False
    access.disabled = True
    # SQL statements and HTTP provider URLs can contain sensitive data.
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)

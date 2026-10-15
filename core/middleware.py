"""Request correlation, access logging, response security and cookie CSRF protection."""

import logging
import re
import time
import uuid
from urllib.parse import urlsplit

from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import JSONResponse

from core.logging import request_id

log = logging.getLogger("printease.access")


class RequestMiddleware:
    def __init__(self, app, settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        headers = Headers(scope=scope)
        supplied = headers.get("x-request-id", "")
        correlation = supplied if re.fullmatch(r"[A-Za-z0-9_-]{8,64}", supplied) else uuid.uuid4().hex
        scope.setdefault("state", {})["request_id"] = correlation
        token = request_id.set(correlation)
        started = time.perf_counter()
        status_code = 500

        async def wrapped_send(message):
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
                response_headers = MutableHeaders(scope=message)
                response_headers["X-Request-ID"] = correlation
                response_headers["X-Content-Type-Options"] = "nosniff"
                response_headers["X-Frame-Options"] = "DENY"
                response_headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
                if scope["path"].startswith("/api") or scope["path"].startswith("/admin"):
                    response_headers["Cache-Control"] = "no-store"
                elif scope["path"].startswith("/static/"):
                    # Relative ES module imports also need revalidation between releases.
                    response_headers["Cache-Control"] = "no-cache"
                if self.settings.environment == "production":
                    response_headers["Strict-Transport-Security"] = "max-age=31536000"
            await send(message)

        try:
            # These provider endpoints authenticate signed payloads, independent of cookies.
            exempt = scope["path"] in {"/api/payments/webhook", "/api/payments/verify-payment"} or scope[
                "path"
            ].startswith("/api/agent/")
            if scope["method"] not in {"GET", "HEAD", "OPTIONS"} and not exempt:
                origin = headers.get("origin")
                referer = headers.get("referer")
                if not origin and referer:
                    parsed = urlsplit(referer)
                    origin = f"{parsed.scheme}://{parsed.netloc}"
                # Production cookie endpoints require an origin, including login (login CSRF).
                if (origin and origin not in self.settings.trusted_origins) or (
                    not origin and self.settings.environment == "production"
                ):
                    response = JSONResponse(
                        {"detail": {"code": "csrf_rejected", "message": "Untrusted request origin"}}, status_code=403
                    )
                    return await response(scope, receive, wrapped_send)
            await self.app(scope, receive, wrapped_send)
        finally:
            route = scope.get("route")
            log.info(
                "request_completed",
                extra={
                    "method": scope["method"],
                    "route": getattr(route, "path", "unmatched"),
                    "status_code": status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1000, 2),
                },
            )
            request_id.reset(token)

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exception_handlers import (
    http_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import JSONResponse
from pathlib import Path
from starlette.middleware.trustedhost import TrustedHostMiddleware
from core.logging import configure_logging
from core.middleware import RequestMiddleware
from core.assets import static_asset
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import ClientDisconnect
from fastapi.responses import Response

from config import settings
from models.database import DBSession, engine
from routers import orders, payments, users, admin, agent
from utils.rate_limiter import limiter

import asyncio
import logging
from services.print_dispatcher import dispatcher

configure_logging(settings.log_level)
log = logging.getLogger("printease.app")
ROOT = Path(__file__).parent


@asynccontextmanager
async def lifespan(_app: FastAPI):
    from alembic.script import ScriptDirectory
    from alembic.config import Config
    from services.singleton_guard import SingletonGuard

    guard = SingletonGuard(engine)
    dispatcher_task = None
    guard_task = None
    recovery_lock = asyncio.Lock()

    async def ensure_authority():
        async with recovery_lock:
            if await guard.check():
                return True
            # A reconnect does not restore PostgreSQL session advisory locks.
            _app.state.ready = False
            dispatcher.is_running = False
            try:
                if not await guard.acquire():
                    return False
                async with dispatcher.lock:
                    await dispatcher.recover_on_startup()
                    dispatcher.end_job()
                _app.state.ready = True
                log.warning("database_authority_recovered_dispatch_paused")
                return True
            except Exception:
                log.exception("database_authority_unavailable")
                return False

    async def watch_authority():
        while True:
            await asyncio.sleep(5)
            await ensure_authority()

    try:
        if not await guard.acquire():
            raise RuntimeError("PrintEase requires one application worker; another instance holds the dispatcher lock")
        expected = ScriptDirectory.from_config(Config(str(ROOT / "alembic.ini"))).get_current_head()
        current = await guard.connection.scalar(text("SELECT version_num FROM alembic_version"))
        await guard.connection.commit()
        if current != expected:
            raise RuntimeError("Database schema is outdated; run alembic upgrade head before starting")
        await asyncio.to_thread(settings.upload_dir.mkdir, parents=True, exist_ok=True)
        await dispatcher.recover_on_startup()
        _app.state.ensure_authority = ensure_authority
        _app.state.ready = True
        dispatcher_task = asyncio.create_task(dispatcher.run(), name="print-reaper")
        guard_task = asyncio.create_task(watch_authority(), name="database-authority")
        log.info("application_started")
        yield
    finally:
        _app.state.ready = False
        dispatcher.is_running = False
        for task in (guard_task, dispatcher_task):
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        try:
            await guard.close()
        finally:
            await engine.dispose()
        log.info("application_stopped")


app = FastAPI(
    title="PrintEase",
    version="1.0.0",
    lifespan=lifespan,
    docs_url=None if settings.environment == "production" else "/docs",
    redoc_url=None if settings.environment == "production" else "/redoc",
    openapi_url=None if settings.environment == "production" else "/openapi.json",
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
app.add_middleware(RequestMiddleware, settings=settings)

# Setup Rate Limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")
templates = Jinja2Templates(directory=ROOT / "templates")
templates.env.globals["static_asset"] = static_asset

# API Routers
app.include_router(users.router)
app.include_router(orders.router)
app.include_router(payments.router)
app.include_router(admin.router)
app.include_router(agent.router)


@app.get("/api/health", tags=["health"])
@app.get("/api/health/ready", tags=["health"])
async def health_check(request: Request, db: DBSession):
    try:
        ensure_authority = getattr(request.app.state, "ensure_authority", None)
        if ensure_authority and not await asyncio.wait_for(ensure_authority(), timeout=3):
            return JSONResponse({"status": "not_ready"}, status_code=503)
        if not getattr(request.app.state, "ready", False):
            return JSONResponse({"status": "not_ready"}, status_code=503)
        await asyncio.wait_for(db.execute(text("SELECT 1")), timeout=3)
        return {"status": "ok"}
    except Exception:
        log.exception("readiness_check_failed")
        return JSONResponse({"status": "not_ready"}, status_code=503)


@app.get("/api/health/live", tags=["health"])
async def liveness_check():
    return {"status": "ok"}


# Frontend HTML Routes
@app.get("/", include_in_schema=False)
@app.get("/home", include_in_schema=False)
async def home(request: Request):
    return templates.TemplateResponse(request, "home.html", {"title": "Smart Printing Service"})


@app.get("/contact", include_in_schema=False)
async def contact(request: Request):
    return templates.TemplateResponse(
        request, "contact.html", {"title": "Contact Us", "web3forms_access_key": settings.web3forms_access_key}
    )


@app.get("/login", include_in_schema=False)
async def login(request: Request):
    return templates.TemplateResponse(request, "login.html", {"title": "Login"})


@app.get("/register", include_in_schema=False)
async def register(request: Request):
    return templates.TemplateResponse(request, "register.html", {"title": "Register"})


@app.get("/upload", include_in_schema=False)
async def upload(request: Request):
    return templates.TemplateResponse(request, "upload.html", {"title": "Upload"})


@app.get("/order", include_in_schema=False)
async def order(request: Request):
    return templates.TemplateResponse(request, "order.html", {"title": "Order Receipt"})


@app.get("/checkout", include_in_schema=False)
async def checkout(request: Request):
    return templates.TemplateResponse(
        request, "checkout.html", {"title": "Secure Checkout", "razorpay_api_key": settings.razorpay_api_key}
    )


@app.get("/my_orders", include_in_schema=False)
async def my_orders(request: Request):
    return templates.TemplateResponse(request, "my_orders.html", {"title": "My Orders"})


@app.get("/admin/login", include_in_schema=False)
async def admin_login(request: Request):
    return templates.TemplateResponse(request, "admin_login.html", {"title": "Admin Login"})


@app.get("/admin/dashboard", include_in_schema=False)
async def admin_dashboard(request: Request):
    return templates.TemplateResponse(request, "admin_dashboard.html", {"title": "Admin Dashboard"})


@app.get("/admin/operations", include_in_schema=False)
async def admin_operations(request: Request):
    return templates.TemplateResponse(request, "admin_operations.html", {"title": "Operations"})


@app.get("/account", include_in_schema=False)
async def account_settings(request: Request):
    return templates.TemplateResponse(request, "account_settings.html", {"title": "Account Settings"})


# Global Exception Handlers
@app.exception_handler(ClientDisconnect)
async def disconnected_client_handler(request: Request, exception: ClientDisconnect):
    # The edge proxy can stop an oversized upload mid-stream. This is an aborted
    # client request, not an internal server failure.
    log.info("request_body_disconnected")
    return Response(status_code=499)


@app.exception_handler(Exception)
async def unexpected_exception_handler(request: Request, exception: Exception):
    correlation = getattr(request.state, "request_id", "-")
    from core.logging import request_id

    token = request_id.set(correlation)
    try:
        log.error("unhandled_request_error", exc_info=(type(exception), exception, exception.__traceback__))
    finally:
        request_id.reset(token)
    return JSONResponse(
        {
            "detail": {"code": "internal_server_error", "message": "An unexpected error occurred"},
            "request_id": correlation,
        },
        status_code=500,
        headers={"X-Request-ID": correlation, "Cache-Control": "no-store", "X-Content-Type-Options": "nosniff"},
    )


@app.exception_handler(StarletteHTTPException)
async def general_http_exception_handler(
    request: Request,
    exception: StarletteHTTPException,
):
    if request.url.path.startswith("/api"):
        return await http_exception_handler(request, exception)

    return templates.TemplateResponse(
        request,
        "error.html",
        {"title": f"Error {exception.status_code}", "status_code": exception.status_code, "detail": exception.detail},
        status_code=exception.status_code,
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request,
    exception: RequestValidationError,
):
    if request.url.path.startswith("/api"):
        # Never echo submitted passwords, tokens or uploaded data in validation errors.
        return JSONResponse(
            {
                "detail": [
                    {"loc": error["loc"], "msg": error["msg"], "type": error["type"]} for error in exception.errors()
                ]
            },
            status_code=422,
        )

    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "title": "Validation Error",
            "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "detail": "The data submitted was invalid or incomplete.",
        },
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
    )

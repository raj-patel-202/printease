from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.exception_handlers import (
    http_exception_handler,
    request_validation_exception_handler,
)
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from config import settings
from models.database import DBSession, engine, Base
from routers import orders, payments, users, admin
from utils.rate_limiter import limiter

import asyncio
from services.print_dispatcher import dispatcher

@asynccontextmanager
async def lifespan(_app: FastAPI):
    dispatcher_task = asyncio.create_task(dispatcher.run())
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    dispatcher.is_running = False
    dispatcher_task.cancel()
    try:
        await dispatcher_task
    except asyncio.CancelledError:
        pass
    await engine.dispose()

app = FastAPI(lifespan=lifespan)

# Setup Rate Limiting
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# API Routers
app.include_router(users.router)
app.include_router(orders.router)
app.include_router(payments.router)
app.include_router(admin.router)

@app.get("/api/health", tags=["health"])
async def health_check(db: DBSession):
    await db.execute(text("SELECT 1"))
    return {"status": "ok"}


# Frontend HTML Routes
@app.get("/", include_in_schema=False)
@app.get("/home", include_in_schema=False)
async def home(request: Request):
    return templates.TemplateResponse(
        request, "home.html", {"title": "Smart Printing Service"}
    )


@app.get("/contact", include_in_schema=False)
async def contact(request: Request):
    return templates.TemplateResponse(
        request, "contact.html", {
            "title": "Contact Us",
            "web3forms_access_key": settings.web3forms_access_key
        }
    )


@app.get("/login", include_in_schema=False)
async def login(request: Request):
    return templates.TemplateResponse(
        request, "login.html", {"title": "Login"}
    )


@app.get("/register", include_in_schema=False)
async def register(request: Request):
    return templates.TemplateResponse(
        request, "register.html", {"title": "Register"}
    )


@app.get("/upload", include_in_schema=False)
async def upload(request: Request):
    return templates.TemplateResponse(
        request, "upload.html", {"title": "Upload"}
    )


@app.get("/order", include_in_schema=False)
async def order(request: Request):
    return templates.TemplateResponse(
        request, "order.html", {"title": "Order Receipt"}
    )

@app.get("/checkout", include_in_schema=False)
async def checkout(request: Request):
    return templates.TemplateResponse(
        request,
        "checkout.html",
        {
            "title": "Secure Checkout",
            "razorpay_api_key": settings.razorpay_api_key
        }
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


@app.get("/account", include_in_schema=False)
async def account_settings(request: Request):
    return templates.TemplateResponse(request, "account_settings.html", {"title": "Account Settings"})

# Global Exception Handlers
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
        {
            "title": f"Error {exception.status_code}",
            "status_code": exception.status_code,
            "detail": exception.detail
        },
        status_code=exception.status_code
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
        request: Request,
        exception: RequestValidationError,
):
    if request.url.path.startswith("/api"):
        return await request_validation_exception_handler(request, exception)

    return templates.TemplateResponse(
        request,
        "error.html",
        {
            "title": "Validation Error",
            "status_code": status.HTTP_422_UNPROCESSABLE_ENTITY,
            "detail": "The data submitted was invalid or incomplete."
        },
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY
    )

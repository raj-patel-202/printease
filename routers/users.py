from datetime import timedelta
from typing import Annotated
import asyncio
import shutil
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Response, status, Request
from utils.rate_limiter import limiter
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from authentication.auth import (
    CurrentUser,
    create_access_token,
    hash_password_async,
    verify_password_async,
)
from config import settings
from models import models
from models.database import DBSession
from schemas.schemas import UserCreate, UserPrivate, UsernameUpdate, DeleteAccountRequest, OrderListResponse, PaginatedResponse
import math

router = APIRouter(prefix="/api/users", tags=["users"])

@router.post("", response_model=UserPrivate, status_code=status.HTTP_201_CREATED)
async def create_user(db: DBSession, user: UserCreate):
    result = await db.execute(select(models.User).where(func.lower(models.User.username) == user.username.strip().lower()))
    if result.scalars().first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username already exists!")

    result = await db.execute(select(models.User).where(func.lower(models.User.email) == user.email.strip().lower()))
    if result.scalars().first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Email already exists!")

    new_user = models.User(
        username=user.username,
        email=user.email.lower(),
        password_hash=await hash_password_async(user.password),
    )
    db.add(new_user)

    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username or email already exists")

    await db.refresh(new_user)
    return new_user

@router.get("/me", response_model=UserPrivate)
async def get_current_user(current_user: CurrentUser):
    return current_user


@router.patch("/me/username", response_model=UserPrivate)
@limiter.limit("5/minute")
async def update_username(request: Request, body: UsernameUpdate, db: DBSession, current_user: CurrentUser):
    if not await verify_password_async(body.password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")

    result = await db.execute(
        select(models.User).where(
            func.lower(models.User.username) == body.new_username.lower(),
            models.User.id != current_user.id
        )
    )
    if result.scalars().first():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Username is already taken")

    current_user.username = body.new_username
    await db.commit()
    await db.refresh(current_user)
    return current_user


@router.post("/token")
@limiter.limit("10/minute")
async def get_current_token(request: Request, response: Response, form_data: Annotated[OAuth2PasswordRequestForm, Depends()], db: DBSession):
    result = await db.execute(select(models.User).where(func.lower(models.User.email) == form_data.username.lower()))
    user = result.scalar_one_or_none()

    if not user:
        await verify_password_async(form_data.password, "$argon2id$v=19$m=65536,t=3,p=4$0000000000000000000000$0000000000000000000000000000000000000000000")
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    if not await verify_password_async(form_data.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect email or password")

    access_token_expires = timedelta(minutes=settings.access_token_expire_minutes)
    access_token = create_access_token(data={"sub": str(user.id), "type": "user"}, expires_delta=access_token_expires)

    response.set_cookie(
        key=settings.cookie_name,
        value=access_token,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        max_age=settings.access_token_expire_minutes * 60
    )
    return {"message": "Successfully logged in"}


@router.get("/orders", response_model=PaginatedResponse[OrderListResponse])
async def get_my_orders(db: DBSession, current_user: CurrentUser, page: int = 1, size: int = 20):
    base_query = select(models.Order).where(models.Order.user_id == current_user.id)

    count_result = await db.execute(select(func.count()).select_from(base_query.subquery()))
    total = count_result.scalar() or 0

    result = await db.execute(
        base_query
        .options(joinedload(models.Order.payment))
        .order_by(models.Order.date_ordered.desc())
        .limit(size)
        .offset((page - 1) * size)
    )

    user_orders = result.scalars().all()
    
    return PaginatedResponse(
        items=user_orders,
        total=total,
        page=page,
        size=size,
        pages=math.ceil(total / size) if size > 0 else 0
    )


@router.get("/orders/paid-count")
async def get_paid_order_count(db: DBSession, current_user: CurrentUser):
    """Returns count of orders where payment is completed (successfully paid)."""
    result = await db.execute(
        select(func.count())
        .select_from(models.Order)
        .join(models.Payment)
        .where(
            models.Order.user_id == current_user.id,
            models.Payment.payment_status == "completed",
        )
    )
    return {"count": result.scalar() or 0}


@router.post("/logout")
async def logout(response: Response):
    response.delete_cookie(
        key=settings.cookie_name,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax"
    )
    return {"message": "Successfully logged out"}


@router.delete("/delete/{user_id}")
@limiter.limit("3/minute")
async def delete_user(request: Request, user_id: int, body: DeleteAccountRequest, db: DBSession, current_user: CurrentUser):
    if user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete this user")

    if not await verify_password_async(body.password, current_user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect password")

    result = await db.execute(select(models.User).where(models.User.id == user_id))
    user = result.scalars().first()
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    await db.delete(user)
    try:
        await db.commit()
        
        # Delete user's PDF files
        user_upload_dir = Path("resource/uploads") / str(user_id)
        if await asyncio.to_thread(user_upload_dir.exists):
            try:
                await asyncio.to_thread(shutil.rmtree, user_upload_dir)
            except Exception:
                pass
                
        return Response(status_code=status.HTTP_204_NO_CONTENT)
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Cannot delete user because they have associated records.")

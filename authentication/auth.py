from datetime import UTC, datetime, timedelta
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status, Request
from fastapi.concurrency import run_in_threadpool
from pwdlib import PasswordHash
from sqlalchemy import select

from models import models
from config import settings
from models.database import DBSession

password_hash = PasswordHash.recommended()

def get_token_from_cookie(request: Request) -> str:
    token = request.cookies.get(settings.cookie_name)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    return token

BearerToken = Annotated[str, Depends(get_token_from_cookie)]

def hash_password(password: str) -> str:
    return password_hash.hash(password)

def verify_password(plain_password: str, hashed_password: str) -> bool:
    return password_hash.verify(plain_password, hashed_password)

async def hash_password_async(password: str) -> str:
    return await run_in_threadpool(hash_password, password)

async def verify_password_async(plain_password: str, hashed_password: str) -> bool:
    return await run_in_threadpool(verify_password, plain_password, hashed_password)

def create_access_token(data: dict, expires_delta: timedelta | None = None) -> str:
    to_encode = data.copy()

    if expires_delta:
        expire = datetime.now(UTC) + expires_delta
    else:
        expire = datetime.now(UTC) + timedelta(
            minutes=settings.access_token_expire_minutes,
        )

    to_encode.update({"exp": expire})

    return jwt.encode(
        to_encode,
        settings.secret_key.get_secret_value(),
        algorithm=settings.algorithm
    )

def verify_access_token(token: str) -> str | None:
    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[settings.algorithm],
            options={"require": ["exp", "sub", "type"]},
        )
        
        if payload.get("type") != "user":
            return None
            
    except jwt.InvalidTokenError:
        return None
    else:
        return payload.get("sub")

async def get_current_user(
    token: BearerToken,
    db: DBSession,
) -> models.User:

    user_id = verify_access_token(token)

    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        user_id_int = int(user_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(
        select(models.User).where(models.User.id == user_id_int),
    )

    user = result.scalars().first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return user

CurrentUser = Annotated[models.User, Depends(get_current_user)]


def get_admin_token_from_cookie(request: Request) -> str:
    token = request.cookies.get(settings.admin_cookie_name)

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )

    return token

AdminBearerToken = Annotated[str, Depends(get_admin_token_from_cookie)]

def verify_admin_access_token(token: str) -> str | None:
    """
    Admin token verification.

    Requires:
    {
        "sub": "...",
        "type": "admin"
    }
    """

    try:
        payload = jwt.decode(
            token,
            settings.secret_key.get_secret_value(),
            algorithms=[settings.algorithm],
            options={"require": ["exp", "sub", "type"]},
        )

        if payload.get("type") != "admin":
            return None

        return payload.get("sub")

    except jwt.InvalidTokenError:
        return None

async def get_current_admin(
    token: AdminBearerToken,
    db: DBSession,
) -> models.Admin:

    admin_id = verify_admin_access_token(token)

    if admin_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        admin_id_int = int(admin_id)
    except (TypeError, ValueError):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    result = await db.execute(
        select(models.Admin).where(models.Admin.id == admin_id_int),
    )

    admin = result.scalar_one_or_none()

    if not admin:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return admin


CurrentAdmin = Annotated[models.Admin, Depends(get_current_admin)]

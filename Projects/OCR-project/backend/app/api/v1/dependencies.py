import uuid
from fastapi import Depends, HTTPException, Header
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from jose import JWTError

from app.database import get_db
from app.models.user import User
from app.core.security import decode_token, hash_api_key


async def get_current_user(
    authorization: str = Header(...),
    db: AsyncSession = Depends(get_db),
) -> User:
    if authorization.startswith("ApiKey "):
        raw_key = authorization.removeprefix("ApiKey ")
        hashed = hash_api_key(raw_key)
        user = await db.scalar(select(User).where(User.api_key == hashed))
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="Invalid API key")
        return user

    if authorization.startswith("Bearer "):
        token = authorization.removeprefix("Bearer ")
        try:
            payload = decode_token(token)
            if payload.get("type") != "access":
                raise ValueError
        except Exception:
            raise HTTPException(status_code=401, detail="Invalid token")
        user = await db.get(User, uuid.UUID(payload["sub"]))
        if not user or not user.is_active:
            raise HTTPException(status_code=401, detail="User not found")
        return user

    raise HTTPException(status_code=401, detail="Authorization header required")

"""
FastAPI dependencies — shared across routes.
"""
from __future__ import annotations

import os

from fastapi import Depends, Header, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError

from src.api.auth import decode_token

_bearer = HTTPBearer(auto_error=False)


# ---------------------------------------------------------------------------
# API-key auth (used by n8n / machine-to-machine)
# ---------------------------------------------------------------------------

async def require_api_key(x_api_key: str | None = Header(default=None, alias="X-API-Key")):
    """Require INTERNAL_API_KEY header on all state-changing endpoints."""
    expected = os.getenv("INTERNAL_API_KEY")
    if not expected:
        return  # key not configured → dev mode, skip auth
    if x_api_key != expected:
        raise HTTPException(status_code=403, detail="Forbidden")


# ---------------------------------------------------------------------------
# JWT auth (used by dashboard / human users)
# ---------------------------------------------------------------------------

async def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """Extract and validate JWT from Authorization: Bearer <token> header."""
    if credentials is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_token(credentials.credentials)
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid or expired token")
    return payload


async def require_admin(current_user: dict = Depends(get_current_user)) -> dict:
    """Require JWT with role == 'admin'."""
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


# ---------------------------------------------------------------------------
# Flexible auth: accepts either JWT or API key (for read endpoints)
# ---------------------------------------------------------------------------

async def require_auth(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
) -> dict:
    """Accept either a valid JWT or a valid API key."""
    # Try JWT first
    if credentials:
        try:
            return decode_token(credentials.credentials)
        except JWTError:
            raise HTTPException(status_code=401, detail="Invalid or expired token")

    # Fall back to API key
    expected = os.getenv("INTERNAL_API_KEY")
    if expected and x_api_key == expected:
        return {"sub": "api_key", "role": "admin"}

    if not expected:
        return {"sub": "dev", "role": "admin"}  # dev mode

    raise HTTPException(status_code=401, detail="Not authenticated")

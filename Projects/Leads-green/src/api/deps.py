"""
FastAPI dependencies — shared across routes.
"""
from __future__ import annotations

import os

from fastapi import Header, HTTPException


async def require_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    """Require INTERNAL_API_KEY header on all state-changing endpoints."""
    expected = os.getenv("INTERNAL_API_KEY")
    if not expected:
        return  # key not configured → dev mode, skip auth
    if x_api_key != expected:
        raise HTTPException(status_code=403, detail="Invalid API key")

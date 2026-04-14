"""
POST /auth/login  — exchange credentials for a JWT access token
POST /auth/change-password — change own password (requires valid token)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.auth import create_access_token, hash_password, verify_password
from src.api.deps import get_current_user
from src.persistence.client import get_supabase

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    role: str


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str


@router.post("/login", response_model=TokenResponse)
async def login(req: LoginRequest):
    sb = get_supabase()
    result = (
        sb.table("users")
        .select("username,hashed_password,role,is_active")
        .eq("username", req.username)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user = result.data[0]
    if not user["is_active"]:
        raise HTTPException(status_code=403, detail="Account disabled")
    if not verify_password(req.password, user["hashed_password"]):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token(user["username"], user["role"])
    return TokenResponse(access_token=token, role=user["role"])


@router.post("/change-password")
async def change_password(req: ChangePasswordRequest, current_user: dict = Depends(get_current_user)):
    sb = get_supabase()
    result = (
        sb.table("users")
        .select("hashed_password")
        .eq("username", current_user["sub"])
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")

    if not verify_password(req.current_password, result.data[0]["hashed_password"]):
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    if len(req.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")

    sb.table("users").update({"hashed_password": hash_password(req.new_password)}).eq("username", current_user["sub"]).execute()
    return {"status": "password updated"}

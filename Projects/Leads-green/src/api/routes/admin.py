"""
Admin-only user management.

GET    /admin/users          — list all users
POST   /admin/users          — create a user
PATCH  /admin/users/{username} — update role or active status
DELETE /admin/users/{username} — deactivate (soft delete)
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from src.api.auth import hash_password
from src.api.deps import require_admin
from src.persistence.client import get_supabase

router = APIRouter(prefix="/admin", tags=["admin"], dependencies=[Depends(require_admin)])


class CreateUserRequest(BaseModel):
    username: str
    password: str
    role: str = "viewer"


class UpdateUserRequest(BaseModel):
    role: str | None = None
    is_active: bool | None = None


@router.get("/users")
async def list_users():
    sb = get_supabase()
    result = sb.table("users").select("id,username,role,is_active,created_at,updated_at").order("created_at").execute()
    return {"users": result.data}


@router.post("/users", status_code=201)
async def create_user(req: CreateUserRequest):
    if req.role not in ("admin", "viewer"):
        raise HTTPException(status_code=400, detail="role must be 'admin' or 'viewer'")
    if len(req.password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    sb = get_supabase()
    existing = sb.table("users").select("id").eq("username", req.username).limit(1).execute()
    if existing.data:
        raise HTTPException(status_code=409, detail="Username already exists")

    result = sb.table("users").insert({
        "username": req.username,
        "hashed_password": hash_password(req.password),
        "role": req.role,
    }).execute()
    row = result.data[0]
    return {"id": row["id"], "username": row["username"], "role": row["role"]}


@router.patch("/users/{username}")
async def update_user(username: str, req: UpdateUserRequest):
    if req.role is not None and req.role not in ("admin", "viewer"):
        raise HTTPException(status_code=400, detail="role must be 'admin' or 'viewer'")

    updates = {k: v for k, v in {"role": req.role, "is_active": req.is_active}.items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    sb = get_supabase()
    result = sb.table("users").update(updates).eq("username", username).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "updated", "username": username, **updates}


@router.delete("/users/{username}")
async def deactivate_user(username: str):
    if username == "admin":
        raise HTTPException(status_code=400, detail="Cannot deactivate the root admin account")
    sb = get_supabase()
    result = sb.table("users").update({"is_active": False}).eq("username", username).execute()
    if not result.data:
        raise HTTPException(status_code=404, detail="User not found")
    return {"status": "deactivated", "username": username}

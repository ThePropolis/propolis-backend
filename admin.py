from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from typing import Optional, Literal
from database import supabase
from auth import require_role, VALID_ROLES

router = APIRouter(prefix="/api/admin", tags=["admin"])

Role = Literal["owner", "investor", "operator"]


class CreateUserBody(BaseModel):
    email: str
    full_name: str
    role: Role
    temp_password: str


class UpdateUserBody(BaseModel):
    full_name: Optional[str] = None
    role: Optional[Role] = None
    is_active: Optional[bool] = None


class ResetPasswordBody(BaseModel):
    new_password: str


@router.get("/users")
async def list_users(_: dict = Depends(require_role("owner"))):
    resp = (
        supabase.table("user_profiles")
        .select("id, email, full_name, role, is_active, avatar_url, created_at, updated_at")
        .order("created_at", desc=True)
        .execute()
    )
    profiles = resp.data or []

    # Merge in last_sign_in_at from Supabase auth.users (not exposed via REST)
    last_sign_in_by_id: dict[str, str] = {}
    try:
        auth_users_resp = supabase.auth.admin.list_users()
        # supabase-py returns either a list or an object with .users depending on version
        auth_users = (
            auth_users_resp
            if isinstance(auth_users_resp, list)
            else getattr(auth_users_resp, "users", [])
        )
        for u in auth_users or []:
            uid = getattr(u, "id", None) or (u.get("id") if isinstance(u, dict) else None)
            last = (
                getattr(u, "last_sign_in_at", None)
                or (u.get("last_sign_in_at") if isinstance(u, dict) else None)
            )
            if uid:
                last_sign_in_by_id[uid] = last
    except Exception:
        # If admin SDK can't list users (key without admin scope), just skip the enrichment
        last_sign_in_by_id = {}

    for p in profiles:
        p["last_sign_in_at"] = last_sign_in_by_id.get(p.get("id"))

    return {"users": profiles}


@router.post("/users")
async def create_user(
    body: CreateUserBody,
    _: dict = Depends(require_role("owner")),
):
    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")

    # 1. Create the Supabase auth user with a confirmed email
    try:
        auth_resp = supabase.auth.admin.create_user({
            "email": body.email,
            "password": body.temp_password,
            "email_confirm": True,
            "user_metadata": {"full_name": body.full_name},
        })
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to create auth user: {e}")

    user = getattr(auth_resp, "user", None)
    if not user:
        raise HTTPException(status_code=500, detail="Supabase returned no user")

    # 2. Insert profile row
    try:
        supabase.table("user_profiles").insert({
            "id": user.id,
            "email": body.email,
            "full_name": body.full_name,
            "role": body.role,
            "is_active": True,
        }).execute()
    except Exception as e:
        # Roll back the auth user if profile insert fails
        try:
            supabase.auth.admin.delete_user(user.id)
        except Exception:
            pass
        raise HTTPException(status_code=500, detail=f"Failed to create profile: {e}")

    return {
        "id": user.id,
        "email": body.email,
        "full_name": body.full_name,
        "role": body.role,
        "is_active": True,
    }


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    body: UpdateUserBody,
    _: dict = Depends(require_role("owner")),
):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    if "role" in updates and updates["role"] not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")

    resp = (
        supabase.table("user_profiles")
        .update(updates)
        .eq("id", user_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="User not found")
    return resp.data[0]


@router.patch("/users/{user_id}/deactivate")
async def deactivate_user(
    user_id: str,
    _: dict = Depends(require_role("owner")),
):
    resp = (
        supabase.table("user_profiles")
        .update({"is_active": False})
        .eq("id", user_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="User not found")
    return {"id": user_id, "is_active": False}


@router.post("/users/{user_id}/reset-password")
async def reset_password(
    user_id: str,
    body: ResetPasswordBody,
    _: dict = Depends(require_role("owner")),
):
    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="Password must be at least 8 characters")

    try:
        supabase.auth.admin.update_user_by_id(user_id, {"password": body.new_password})
    except Exception as e:
        msg = str(e)
        if "not allowed" in msg.lower() or "403" in msg:
            raise HTTPException(
                status_code=500,
                detail=(
                    "Supabase rejected the admin call. The API key in SUPABASE_KEY "
                    "needs service_role / admin scope. Swap it for the legacy "
                    "service_role JWT in the Vercel env vars."
                ),
            )
        raise HTTPException(status_code=500, detail=f"Failed to reset password: {e}")

    return {"id": user_id, "password_reset": True}


@router.delete("/users/{user_id}")
async def delete_user(
    user_id: str,
    hard: bool = Query(False, description="If true, permanently delete from Supabase auth"),
    caller: dict = Depends(require_role("owner")),
):
    # Prevent owners from accidentally nuking themselves
    if caller.get("user_id") == user_id:
        raise HTTPException(status_code=400, detail="You cannot delete your own account")

    if not hard:
        # Same as deactivate
        supabase.table("user_profiles").update({"is_active": False}).eq("id", user_id).execute()
        return {"id": user_id, "deleted": False, "is_active": False}

    # Hard delete: remove from auth.users (CASCADE drops the profile row)
    try:
        supabase.auth.admin.delete_user(user_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to delete auth user: {e}")

    # In case the FK cascade didn't fire (shouldn't happen, but be safe)
    supabase.table("user_profiles").delete().eq("id", user_id).execute()
    return {"id": user_id, "deleted": True}

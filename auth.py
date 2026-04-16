from fastapi import APIRouter, HTTPException, Depends, Request, UploadFile, File
from pydantic import BaseModel
from jose import JWTError, jwt
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional
import os
import uuid
from database import supabase
from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY")
ACCESS_TOKEN_EXPIRE_MINUTES = 3600
ALGORITHM = "HS256"

VALID_ROLES = ("owner", "investor", "operator")

router = APIRouter()


class UserCredentials(BaseModel):
    email: str
    password: str


class Token(BaseModel):
    access_token: str
    token_type: str


class User(BaseModel):
    email: str
    full_name: str
    role: str
    avatar_url: Optional[str] = None


class UpdateMeBody(BaseModel):
    full_name: Optional[str] = None


class ChangePasswordBody(BaseModel):
    current_password: str
    new_password: str


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def _decode_token(request: Request) -> dict:
    token = request.headers.get("Authorization")
    if not token or not token.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Token missing or invalid")
    try:
        return jwt.decode(token.split(" ")[1], SECRET_KEY, algorithms=[ALGORITHM])
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")


def get_current_user_payload(request: Request) -> dict:
    """FastAPI dependency: decode JWT and return payload."""
    return _decode_token(request)


def require_role(*allowed: str):
    """FastAPI dependency factory. Usage: Depends(require_role('owner'))"""
    allowed_set = set(allowed)

    def _check(payload: dict = Depends(get_current_user_payload)) -> dict:
        role = payload.get("role")
        if role not in allowed_set:
            raise HTTPException(
                status_code=403,
                detail=f"Forbidden: requires one of {sorted(allowed_set)}",
            )
        return payload

    return _check


@router.post("/api/auth/login")
async def login(credentials: UserCredentials):
    # 1. Validate password via Supabase Auth
    try:
        response = supabase.auth.sign_in_with_password({
            "email": credentials.email,
            "password": credentials.password,
        })
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not response or not response.user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user_id = response.user.id

    # 2. Look up profile (role + active flag) — source of truth, not user_metadata
    profile_resp = (
        supabase.table("user_profiles")
        .select("id, email, full_name, role, is_active, avatar_url")
        .eq("id", user_id)
        .maybe_single()
        .execute()
    )
    profile = getattr(profile_resp, "data", None)

    if not profile:
        raise HTTPException(
            status_code=403,
            detail="User has no profile. Contact an administrator.",
        )

    if not profile.get("is_active", False):
        raise HTTPException(status_code=403, detail="Account deactivated")

    role = profile.get("role")
    if role not in VALID_ROLES:
        raise HTTPException(status_code=403, detail="Invalid role assigned")

    full_name = profile.get("full_name") or ""
    avatar_url = profile.get("avatar_url")

    # 3. Issue JWT
    token_data = {
        "sub": credentials.email,
        "user_id": user_id,
        "full_name": full_name,
        "role": role,
        "avatar_url": avatar_url,
        "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
    }
    access_token = jwt.encode(token_data, SECRET_KEY, algorithm=ALGORITHM)

    return {
        "access_token": access_token,
        "token_type": "bearer",
        "user": {
            "email": credentials.email,
            "full_name": full_name,
            "role": role,
            "avatar_url": avatar_url,
        },
    }


@router.get("/api/auth/me", response_model=User)
async def get_current_user(payload: dict = Depends(get_current_user_payload)):
    # Fetch fresh profile so the UI always has latest avatar / full_name
    user_id = payload.get("user_id")
    if user_id:
        resp = (
            supabase.table("user_profiles")
            .select("email, full_name, role, avatar_url")
            .eq("id", user_id)
            .maybe_single()
            .execute()
        )
        profile = getattr(resp, "data", None)
        if profile:
            return {
                "email": profile.get("email", payload.get("sub", "")),
                "full_name": profile.get("full_name", "") or "",
                "role": profile.get("role", payload.get("role", "")),
                "avatar_url": profile.get("avatar_url"),
            }
    # JWT fallback
    return {
        "email": payload.get("sub", ""),
        "full_name": payload.get("full_name", ""),
        "role": payload.get("role", ""),
        "avatar_url": payload.get("avatar_url"),
    }


@router.patch("/api/auth/me")
async def update_me(body: UpdateMeBody, payload: dict = Depends(get_current_user_payload)):
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    resp = (
        supabase.table("user_profiles")
        .update(updates)
        .eq("id", user_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="Profile not found")
    row = resp.data[0]
    return {
        "email": row.get("email"),
        "full_name": row.get("full_name", ""),
        "role": row.get("role", ""),
        "avatar_url": row.get("avatar_url"),
    }


@router.post("/api/auth/me/password")
async def change_password(
    body: ChangePasswordBody,
    payload: dict = Depends(get_current_user_payload),
):
    email = payload.get("sub")
    user_id = payload.get("user_id")
    if not email or not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    if len(body.new_password) < 8:
        raise HTTPException(status_code=400, detail="New password must be at least 8 characters")
    if body.new_password == body.current_password:
        raise HTTPException(status_code=400, detail="New password must differ from current")

    # Sign in to both verify the current password AND obtain a user-scoped
    # session. Using that session to call update_user works with any API key,
    # so we don't depend on the service_role admin scope (which isn't granted
    # to the sb_secret_ key on some projects).
    try:
        verify = supabase.auth.sign_in_with_password({
            "email": email,
            "password": body.current_password,
        })
        if not verify or not verify.user:
            raise HTTPException(status_code=401, detail="Current password is incorrect")
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(status_code=401, detail="Current password is incorrect")

    try:
        supabase.auth.update_user({"password": body.new_password})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to change password: {e}")
    finally:
        # Don't leave the user-scoped session sitting on the shared client.
        try:
            supabase.auth.sign_out()
        except Exception:
            pass

    return {"password_changed": True}


@router.post("/api/auth/me/avatar")
async def upload_avatar(
    file: UploadFile = File(...),
    payload: dict = Depends(get_current_user_payload),
):
    user_id = payload.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token")

    content_type = (file.content_type or "").lower()
    if not content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    ext = content_type.split("/")[-1].split(";")[0] or "png"
    if ext == "jpeg":
        ext = "jpg"
    key = f"{user_id}/{uuid.uuid4().hex}.{ext}"

    try:
        data = await file.read()
        # upsert in case the user uploads a new one at the same path
        supabase.storage.from_("avatars").upload(
            path=key,
            file=data,
            file_options={"content-type": content_type, "upsert": "true"},
        )
        public = supabase.storage.from_("avatars").get_public_url(key)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Upload failed: {e}")

    # Strip trailing ? that supabase-py sometimes appends
    public = (public or "").rstrip("?")

    upd = (
        supabase.table("user_profiles")
        .update({"avatar_url": public})
        .eq("id", user_id)
        .execute()
    )
    if not upd.data:
        raise HTTPException(status_code=500, detail="Avatar uploaded but profile update failed")
    return {"avatar_url": public}

"""
Publishing — turns inventory rooms into public-ready listings.

Owner-only writes. GETs allow owner + investor (so an investor preview is
trivial later); operators don't need this surface.

Schema: prop_listings + prop_listing_rooms (M2M to prop_rooms).
The future public listings site will read from prop_listings where
status = 'published'.
"""
from __future__ import annotations

import re
from collections import defaultdict
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import require_role
from database import supabase

router = APIRouter(prefix="/api/listings", tags=["listings"])

ListingStatus = Literal["draft", "published", "archived", "rented"]


class _ListingBase(BaseModel):
    building_id: Optional[str] = None
    title: Optional[str] = None
    subtitle: Optional[str] = None
    description: Optional[str] = None
    slug: Optional[str] = None
    meta_description: Optional[str] = None
    cover_photo: Optional[str] = None
    photos: Optional[List[str]] = None
    asking_rent: Optional[float] = None
    deposit: Optional[float] = None
    application_fee: Optional[float] = None
    available_from: Optional[str] = None
    available_until: Optional[str] = None
    min_lease_months: Optional[int] = None
    max_lease_months: Optional[int] = None
    is_furnished: Optional[bool] = None
    utilities_included: Optional[bool] = None
    utilities_note: Optional[str] = None
    pets_allowed: Optional[bool] = None
    smoking_allowed: Optional[bool] = None
    highlights: Optional[List[str]] = None
    tags: Optional[List[str]] = None
    inquiry_email: Optional[str] = None
    inquiry_phone: Optional[str] = None


class ListingCreate(_ListingBase):
    title: str
    room_ids: List[str] = []


class ListingUpdate(_ListingBase):
    room_ids: Optional[List[str]] = None


SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(text: str) -> str:
    base = SLUG_RE.sub("-", (text or "").strip().lower()).strip("-")
    return base or "listing"


def ensure_unique_slug(candidate: str, exclude_id: Optional[str] = None) -> str:
    base = slugify(candidate)
    slug = base
    n = 2
    while True:
        existing = (
            supabase.table("prop_listings").select("id, slug").eq("slug", slug).execute().data or []
        )
        existing = [r for r in existing if r["id"] != exclude_id]
        if not existing:
            return slug
        slug = f"{base}-{n}"
        n += 1


def _replace_listing_rooms(listing_id: str, room_ids: List[str]) -> None:
    supabase.table("prop_listing_rooms").delete().eq("listing_id", listing_id).execute()
    if not room_ids:
        return
    supabase.table("prop_listing_rooms").insert(
        [{"listing_id": listing_id, "room_id": rid, "display_order": i} for i, rid in enumerate(room_ids)]
    ).execute()


def _expand_listing(listing_row: dict) -> dict:
    lr = (
        supabase.table("prop_listing_rooms")
        .select("room_id, display_order")
        .eq("listing_id", listing_row["id"])
        .order("display_order")
        .execute()
        .data
        or []
    )
    room_ids = [r["room_id"] for r in lr]
    rooms: list = []
    if room_ids:
        rooms_resp = supabase.table("prop_rooms").select("*").in_("id", room_ids).execute()
        room_by_id = {r["id"]: r for r in (rooms_resp.data or [])}
        fin_resp = supabase.table("prop_financials").select("*").in_("room_id", room_ids).execute()
        fin_by_room = {f["room_id"]: f for f in (fin_resp.data or [])}
        unit_ids = list({r["unit_id"] for r in room_by_id.values()})
        unit_by_id = {}
        if unit_ids:
            ur = (
                supabase.table("prop_units")
                .select("id, building_id, name, unit_type")
                .in_("id", unit_ids)
                .execute()
            )
            unit_by_id = {u["id"]: u for u in (ur.data or [])}
        for entry in lr:
            r = room_by_id.get(entry["room_id"])
            if not r:
                continue
            rooms.append({**r, "financials": fin_by_room.get(r["id"]), "unit": unit_by_id.get(r["unit_id"])})
    building = None
    if listing_row.get("building_id"):
        b = (
            supabase.table("prop_buildings")
            .select("*")
            .eq("id", listing_row["building_id"])
            .maybe_single()
            .execute()
        )
        building = getattr(b, "data", None)
    return {**listing_row, "rooms": rooms, "building": building}


@router.get("")
async def list_listings(
    status: Optional[str] = None,
    building_id: Optional[str] = None,
    _: dict = Depends(require_role("owner", "investor")),
):
    q = supabase.table("prop_listings").select("*")
    if status:
        q = q.eq("status", status)
    if building_id:
        q = q.eq("building_id", building_id)
    rows = q.order("updated_at", desc=True).execute().data or []

    if rows:
        ids = [r["id"] for r in rows]
        lr = (
            supabase.table("prop_listing_rooms")
            .select("listing_id")
            .in_("listing_id", ids)
            .execute()
            .data
            or []
        )
        counts: dict = defaultdict(int)
        for x in lr:
            counts[x["listing_id"]] += 1
        for r in rows:
            r["room_count"] = counts.get(r["id"], 0)

    return {"listings": rows}


@router.get("/in-use-rooms")
async def in_use_rooms(_: dict = Depends(require_role("owner", "investor"))):
    rows = (
        supabase.table("prop_listing_rooms")
        .select("room_id, listing_id, prop_listings(id, title, status)")
        .execute()
        .data
        or []
    )
    out: dict = defaultdict(list)
    for r in rows:
        listing = r.get("prop_listings") or {}
        if listing.get("status") in ("draft", "published"):
            out[r["room_id"]].append({
                "listing_id": listing.get("id"),
                "listing_title": listing.get("title"),
                "status": listing.get("status"),
            })
    return {"rooms": out}


@router.get("/{listing_id}")
async def get_listing(listing_id: str, _: dict = Depends(require_role("owner", "investor"))):
    resp = (
        supabase.table("prop_listings").select("*").eq("id", listing_id).maybe_single().execute()
    )
    row = getattr(resp, "data", None)
    if not row:
        raise HTTPException(status_code=404, detail="Listing not found")
    return _expand_listing(row)


@router.post("")
async def create_listing(
    body: ListingCreate,
    _: dict = Depends(require_role("owner")),
):
    if not body.title.strip():
        raise HTTPException(status_code=400, detail="Title is required")
    data = {k: v for k, v in body.model_dump().items() if v is not None and k != "room_ids"}
    data["title"] = data["title"].strip()
    data["slug"] = ensure_unique_slug(data.get("slug") or data["title"])

    resp = supabase.table("prop_listings").insert(data).execute()
    if not resp.data:
        raise HTTPException(status_code=500, detail="Failed to create listing")
    listing_id = resp.data[0]["id"]
    if body.room_ids:
        _replace_listing_rooms(listing_id, body.room_ids)
    return _expand_listing(resp.data[0])


@router.patch("/{listing_id}")
async def update_listing(
    listing_id: str,
    body: ListingUpdate,
    _: dict = Depends(require_role("owner")),
):
    body_dict = body.model_dump()
    room_ids = body_dict.pop("room_ids", None)
    updates = {k: v for k, v in body_dict.items() if v is not None}

    if "title" in updates:
        updates["title"] = updates["title"].strip()
    if "slug" in updates and updates["slug"]:
        updates["slug"] = ensure_unique_slug(updates["slug"], exclude_id=listing_id)

    if updates:
        resp = supabase.table("prop_listings").update(updates).eq("id", listing_id).execute()
        if not resp.data:
            raise HTTPException(status_code=404, detail="Listing not found")

    if room_ids is not None:
        _replace_listing_rooms(listing_id, room_ids)

    row = (
        supabase.table("prop_listings").select("*").eq("id", listing_id).maybe_single().execute()
    )
    if not getattr(row, "data", None):
        raise HTTPException(status_code=404, detail="Listing not found")
    return _expand_listing(row.data)


@router.delete("/{listing_id}")
async def delete_listing(listing_id: str, _: dict = Depends(require_role("owner"))):
    supabase.table("prop_listings").delete().eq("id", listing_id).execute()
    return {"id": listing_id, "deleted": True}


def _set_status(listing_id: str, **fields) -> dict:
    resp = supabase.table("prop_listings").update(fields).eq("id", listing_id).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Listing not found")
    return resp.data[0]


@router.post("/{listing_id}/publish")
async def publish(listing_id: str, _: dict = Depends(require_role("owner"))):
    rcount = (
        supabase.table("prop_listing_rooms")
        .select("id", count="exact")
        .eq("listing_id", listing_id)
        .execute()
    )
    if (getattr(rcount, "count", 0) or 0) == 0:
        raise HTTPException(status_code=400, detail="Add at least one room before publishing")
    return _set_status(listing_id, status="published", published_at="now()")


@router.post("/{listing_id}/unpublish")
async def unpublish(listing_id: str, _: dict = Depends(require_role("owner"))):
    return _set_status(listing_id, status="draft")


@router.post("/{listing_id}/archive")
async def archive(listing_id: str, _: dict = Depends(require_role("owner"))):
    return _set_status(listing_id, status="archived", archived_at="now()")


@router.post("/{listing_id}/mark-rented")
async def mark_rented(listing_id: str, _: dict = Depends(require_role("owner"))):
    return _set_status(listing_id, status="rented")


@router.post("/{listing_id}/duplicate")
async def duplicate(listing_id: str, _: dict = Depends(require_role("owner"))):
    src = (
        supabase.table("prop_listings").select("*").eq("id", listing_id).maybe_single().execute()
    )
    src_data = getattr(src, "data", None)
    if not src_data:
        raise HTTPException(status_code=404, detail="Listing not found")

    new_data = {
        k: v
        for k, v in src_data.items()
        if k not in {"id", "created_at", "updated_at", "published_at", "archived_at", "slug"}
    }
    new_data["title"] = (src_data.get("title") or "Untitled") + " (copy)"
    new_data["status"] = "draft"
    new_data["slug"] = ensure_unique_slug(new_data["title"])
    ins = supabase.table("prop_listings").insert(new_data).execute()
    if not ins.data:
        raise HTTPException(status_code=500, detail="Duplicate failed")
    new_id = ins.data[0]["id"]
    src_rooms = (
        supabase.table("prop_listing_rooms")
        .select("room_id, display_order")
        .eq("listing_id", listing_id)
        .execute()
        .data
        or []
    )
    if src_rooms:
        supabase.table("prop_listing_rooms").insert(
            [
                {"listing_id": new_id, "room_id": r["room_id"], "display_order": r["display_order"]}
                for r in src_rooms
            ]
        ).execute()
    return _expand_listing(ins.data[0])

"""
Facilities module — Supabase-backed CRUD for the Facilities page.

DoorLoop is consulted ONLY during the initial import (and optional re-imports)
to seed/refresh building + unit data. After that, these endpoints are the
source of truth; DoorLoop is not queried.
"""
from collections import defaultdict
from typing import Optional, List
import logging
import os

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from dotenv import load_dotenv

from auth import require_role
from database import supabase

load_dotenv()
logger = logging.getLogger("facilities")

router = APIRouter(prefix="/api/facilities", tags=["facilities"])

DOORLOOP_API_KEY = os.getenv("DOORLOOP_API_KEY")
DOORLOOP_BASE_URL = "https://app.doorloop.com/api"


# ── Pydantic models ────────────────────────────────────────────────────────
class BuildingCreate(BaseModel):
    name: str
    address: Optional[str] = None


class BuildingUpdate(BaseModel):
    name: Optional[str] = None
    address: Optional[str] = None


class UnitCreate(BaseModel):
    building_id: str
    name: str
    beds: Optional[int] = None
    baths: Optional[float] = None
    amenities: Optional[List[str]] = None


class UnitUpdate(BaseModel):
    name: Optional[str] = None
    beds: Optional[int] = None
    baths: Optional[float] = None
    amenities: Optional[List[str]] = None


# ── Read ───────────────────────────────────────────────────────────────────
@router.get("")
async def list_facilities(_: dict = Depends(require_role("owner", "operator"))):
    """Return all buildings with their units, shaped for the Facilities page."""
    b_resp = (
        supabase.table("facility_buildings")
        .select("id, name, address")
        .order("name")
        .execute()
    )
    buildings = b_resp.data or []

    u_resp = (
        supabase.table("facility_units")
        .select("id, building_id, name, beds, baths, amenities")
        .execute()
    )
    units_by_building: dict = defaultdict(list)
    for u in u_resp.data or []:
        units_by_building[u["building_id"]].append({
            "unit_id": u["id"],
            "unit_name": u.get("name", ""),
            "beds": u.get("beds"),
            "baths": float(u["baths"]) if u.get("baths") is not None else None,
            "amenities": u.get("amenities") or [],
        })

    properties = [
        {
            "property_id": b["id"],
            "property_name": b["name"],
            "property_amenities": [],
            "units": sorted(units_by_building.get(b["id"], []), key=lambda x: x["unit_name"]),
        }
        for b in buildings
    ]

    all_amenities = sorted({
        a for p in properties for u in p["units"] for a in u["amenities"]
    })
    return {"properties": properties, "all_amenities": all_amenities}


# ── One-time (idempotent) import from DoorLoop ─────────────────────────────
@router.post("/import")
async def import_from_doorloop(_: dict = Depends(require_role("owner"))):
    """
    Idempotent import. Upserts by DoorLoop ID, so:
    - First run:  imports every building + unit with amenities
    - Subsequent: adds newly-created DoorLoop items; leaves existing rows untouched
      (the owner's edits are preserved)
    """
    if not DOORLOOP_API_KEY:
        raise HTTPException(status_code=500, detail="DOORLOOP_API_KEY not configured")

    headers = {
        "Authorization": f"Bearer {DOORLOOP_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

    # Already-imported DoorLoop IDs — we skip these so the owner's edits stick.
    existing_b = (
        supabase.table("facility_buildings")
        .select("id, doorloop_id")
        .not_.is_("doorloop_id", "null")
        .execute()
    )
    building_id_map: dict[str, str] = {
        row["doorloop_id"]: row["id"] for row in (existing_b.data or [])
    }

    existing_u = (
        supabase.table("facility_units")
        .select("doorloop_id")
        .not_.is_("doorloop_id", "null")
        .execute()
    )
    existing_unit_doorloop_ids = {row["doorloop_id"] for row in (existing_u.data or [])}

    created_buildings = 0
    created_units = 0

    async with httpx.AsyncClient(timeout=60) as client:
        try:
            props_resp = await client.get(
                f"{DOORLOOP_BASE_URL}/properties",
                headers=headers,
                params={"limit": 100},
            )
            props_resp.raise_for_status()
        except httpx.HTTPStatusError as e:
            raise HTTPException(
                status_code=502,
                detail=f"DoorLoop /properties failed: {e.response.status_code}",
            ) from e

        for prop in props_resp.json().get("data", []):
            dl_building_id = prop.get("id")
            if not dl_building_id:
                continue

            # Upsert building
            if dl_building_id in building_id_map:
                internal_building_id = building_id_map[dl_building_id]
            else:
                addr = prop.get("address", {}) or {}
                address_str = ", ".join(
                    s for s in [
                        addr.get("street1"),
                        addr.get("city"),
                        addr.get("state"),
                        addr.get("zip"),
                    ] if s
                )
                ins = (
                    supabase.table("facility_buildings")
                    .insert({
                        "doorloop_id": dl_building_id,
                        "name": prop.get("name", "Untitled building"),
                        "address": address_str or None,
                    })
                    .execute()
                )
                if not ins.data:
                    logger.warning(f"Failed to insert building {prop.get('name')}")
                    continue
                internal_building_id = ins.data[0]["id"]
                building_id_map[dl_building_id] = internal_building_id
                created_buildings += 1

            # Fetch units for this property
            try:
                units_resp = await client.get(
                    f"{DOORLOOP_BASE_URL}/units",
                    headers=headers,
                    params={"filter_property": dl_building_id, "limit": 200},
                )
                units_resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                logger.warning(
                    f"Skipping units for {prop.get('name')}: HTTP {e.response.status_code}"
                )
                continue

            unit_rows_to_insert = []
            for u in units_resp.json().get("data", []):
                dl_unit_id = u.get("id")
                if not dl_unit_id or dl_unit_id in existing_unit_doorloop_ids:
                    continue
                if not u.get("active", True):
                    continue
                unit_rows_to_insert.append({
                    "doorloop_id": dl_unit_id,
                    "building_id": internal_building_id,
                    "name": u.get("name", ""),
                    "beds": u.get("beds"),
                    "baths": u.get("baths"),
                    "amenities": u.get("amenities") or [],
                })

            if unit_rows_to_insert:
                supabase.table("facility_units").insert(unit_rows_to_insert).execute()
                created_units += len(unit_rows_to_insert)

    return {
        "imported": True,
        "new_buildings": created_buildings,
        "new_units": created_units,
    }


# ── Buildings CRUD ─────────────────────────────────────────────────────────
@router.post("/buildings")
async def create_building(body: BuildingCreate, _: dict = Depends(require_role("owner"))):
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    resp = (
        supabase.table("facility_buildings")
        .insert({"name": body.name.strip(), "address": body.address})
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=500, detail="Failed to create building")
    return resp.data[0]


@router.patch("/buildings/{building_id}")
async def update_building(
    building_id: str,
    body: BuildingUpdate,
    _: dict = Depends(require_role("owner")),
):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    resp = (
        supabase.table("facility_buildings")
        .update(updates)
        .eq("id", building_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="Building not found")
    return resp.data[0]


@router.delete("/buildings/{building_id}")
async def delete_building(building_id: str, _: dict = Depends(require_role("owner"))):
    # Cascade on units is handled by the FK (ON DELETE CASCADE)
    supabase.table("facility_buildings").delete().eq("id", building_id).execute()
    return {"id": building_id, "deleted": True}


# ── Units CRUD ─────────────────────────────────────────────────────────────
@router.post("/units")
async def create_unit(body: UnitCreate, _: dict = Depends(require_role("owner"))):
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    # Verify the building exists
    b = (
        supabase.table("facility_buildings")
        .select("id")
        .eq("id", body.building_id)
        .maybe_single()
        .execute()
    )
    if not getattr(b, "data", None):
        raise HTTPException(status_code=404, detail="Building not found")

    resp = (
        supabase.table("facility_units")
        .insert({
            "building_id": body.building_id,
            "name": body.name.strip(),
            "beds": body.beds,
            "baths": body.baths,
            "amenities": body.amenities or [],
        })
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=500, detail="Failed to create unit")
    return resp.data[0]


@router.patch("/units/{unit_id}")
async def update_unit(
    unit_id: str,
    body: UnitUpdate,
    _: dict = Depends(require_role("owner")),
):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    resp = (
        supabase.table("facility_units")
        .update(updates)
        .eq("id", unit_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="Unit not found")
    return resp.data[0]


@router.delete("/units/{unit_id}")
async def delete_unit(unit_id: str, _: dict = Depends(require_role("owner"))):
    supabase.table("facility_units").delete().eq("id", unit_id).execute()
    return {"id": unit_id, "deleted": True}

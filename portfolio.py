"""
Unified portfolio CRUD — buildings, units, rooms, financials, monthly perf.

Shape of the data model:
  prop_amenities         — catalog (id, name, category)
  prop_buildings         — structural + photos + description + amenity_ids
  prop_units             — apartment containers
  prop_rooms             — rentable rooms (structural fields only)
  prop_financials        — money fields, 1:1 with prop_rooms
  prop_monthly_performance — per-building time series

Read endpoints are open to all authenticated roles (so the unified page can
render owner / investor / operator views from one source). Write endpoints
are owner-only.
"""
from collections import defaultdict
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from auth import require_role
from database import supabase

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])

Length = Literal["LTR", "STR"]
Strategy = Literal["Coliving", "Entire Apt"]


# ── Pydantic ──────────────────────────────────────────────────────────────
class AmenityCreate(BaseModel):
    name: str
    category: Optional[str] = None


class AmenityUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None


class BuildingBase(BaseModel):
    name: Optional[str] = None
    full_name: Optional[str] = None
    address: Optional[str] = None
    owner_llc: Optional[str] = None
    floors: Optional[int] = None
    has_elevator: Optional[bool] = None
    units_count: Optional[int] = None
    beds_count: Optional[int] = None
    description: Optional[str] = None
    photos: Optional[List[str]] = None
    amenity_ids: Optional[List[str]] = None
    notes: Optional[str] = None


class BuildingCreate(BuildingBase):
    name: str


class BuildingUpdate(BuildingBase):
    pass


class UnitBase(BaseModel):
    name: Optional[str] = None
    unit_type: Optional[str] = None
    notes: Optional[str] = None


class UnitCreate(UnitBase):
    building_id: str
    name: str


class UnitUpdate(UnitBase):
    pass


# Room body — flat: structural + financial in one shape so the frontend
# doesn't have to think about the split.
class RoomBase(BaseModel):
    name: Optional[str] = None
    length: Optional[Length] = None
    strategy: Optional[Strategy] = None
    bed_size: Optional[str] = None
    bathroom: Optional[str] = None
    ceiling_height: Optional[str] = None
    balcony: Optional[str] = None
    room_type_name: Optional[str] = None
    sqft: Optional[int] = None
    is_ada: Optional[bool] = None
    listing_date: Optional[str] = None
    amenity_ids: Optional[List[str]] = None
    notes: Optional[str] = None
    # Financial
    actual_rent: Optional[float] = None
    base_rent: Optional[float] = None
    market_rent: Optional[float] = None
    actual_rent_with_util: Optional[float] = None
    pessimistic_rent: Optional[float] = None
    concession_rent: Optional[float] = None
    concession_rent_with_util: Optional[float] = None
    adjustment: Optional[float] = None
    stake_5_cashback: Optional[float] = None
    stake_8_cashback: Optional[float] = None
    revenue_month: Optional[float] = None
    revenue_year: Optional[float] = None
    revenue_per_apartment: Optional[float] = None
    extras: Optional[str] = None


class RoomCreate(RoomBase):
    unit_id: str
    name: str


class RoomUpdate(RoomBase):
    pass


class MonthlyPerfCreate(BaseModel):
    building_id: str
    period_year: int
    period_month: int
    occupancy_pct: Optional[float] = None
    adr: Optional[float] = None
    revpar: Optional[float] = None
    revenue: Optional[float] = None
    notes: Optional[str] = None


class MonthlyPerfUpdate(BaseModel):
    occupancy_pct: Optional[float] = None
    adr: Optional[float] = None
    revpar: Optional[float] = None
    revenue: Optional[float] = None
    notes: Optional[str] = None


STRUCTURAL_ROOM_FIELDS = {
    "name", "length", "strategy", "bed_size", "bathroom", "ceiling_height",
    "balcony", "room_type_name", "sqft", "is_ada", "listing_date", "amenity_ids", "notes",
}
FINANCIAL_ROOM_FIELDS = {
    "actual_rent", "base_rent", "market_rent", "actual_rent_with_util",
    "pessimistic_rent", "concession_rent", "concession_rent_with_util",
    "adjustment", "stake_5_cashback", "stake_8_cashback",
    "revenue_month", "revenue_year", "revenue_per_apartment", "extras",
}


# ── Read: full tree ───────────────────────────────────────────────────────
@router.get("")
async def list_portfolio(_: dict = Depends(require_role("owner", "investor", "operator"))):
    """
    Returns the full tree:
    {
      buildings: [
        { ...building, units: [{ ...unit, rooms: [{ ...room, financials: {...} }] }] }
      ],
      amenities: [{id, name, category}, ...]
    }
    """
    amenities = (
        supabase.table("prop_amenities")
        .select("*")
        .order("name")
        .execute()
        .data
        or []
    )
    buildings = (
        supabase.table("prop_buildings").select("*").order("name").execute().data or []
    )
    units = supabase.table("prop_units").select("*").execute().data or []
    rooms = supabase.table("prop_rooms").select("*").execute().data or []
    financials = supabase.table("prop_financials").select("*").execute().data or []

    fin_by_room = {f["room_id"]: f for f in financials}

    rooms_by_unit: dict = defaultdict(list)
    for r in rooms:
        rooms_by_unit[r["unit_id"]].append({**r, "financials": fin_by_room.get(r["id"])})
    for v in rooms_by_unit.values():
        v.sort(key=lambda x: x.get("name") or "")

    units_by_building: dict = defaultdict(list)
    for u in units:
        units_by_building[u["building_id"]].append({
            **u,
            "rooms": rooms_by_unit.get(u["id"], []),
        })
    for v in units_by_building.values():
        v.sort(key=lambda x: x.get("name") or "")

    tree = [
        {**b, "units": units_by_building.get(b["id"], [])}
        for b in buildings
    ]

    return {"buildings": tree, "amenities": amenities}


# ── Amenities catalog ─────────────────────────────────────────────────────
@router.get("/amenities")
async def list_amenities(_: dict = Depends(require_role("owner", "investor", "operator"))):
    return {
        "amenities": (
            supabase.table("prop_amenities")
            .select("*")
            .order("name")
            .execute()
            .data
            or []
        )
    }


@router.post("/amenities")
async def create_amenity(body: AmenityCreate, _: dict = Depends(require_role("owner"))):
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Name required")
    payload = {"name": body.name.strip(), "category": body.category}
    try:
        resp = supabase.table("prop_amenities").insert(payload).execute()
    except Exception as e:
        # likely unique violation; fetch existing
        existing = (
            supabase.table("prop_amenities")
            .select("*")
            .eq("name", body.name.strip())
            .maybe_single()
            .execute()
        )
        if getattr(existing, "data", None):
            return existing.data
        raise HTTPException(status_code=400, detail=str(e))
    if not resp.data:
        raise HTTPException(status_code=500, detail="Insert failed")
    return resp.data[0]


@router.patch("/amenities/{amenity_id}")
async def update_amenity(
    amenity_id: str,
    body: AmenityUpdate,
    _: dict = Depends(require_role("owner")),
):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    if "name" in updates:
        updates["name"] = updates["name"].strip()
    resp = supabase.table("prop_amenities").update(updates).eq("id", amenity_id).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Amenity not found")
    return resp.data[0]


@router.delete("/amenities/{amenity_id}")
async def delete_amenity(amenity_id: str, _: dict = Depends(require_role("owner"))):
    supabase.table("prop_amenities").delete().eq("id", amenity_id).execute()
    return {"id": amenity_id, "deleted": True}


# ── Buildings ─────────────────────────────────────────────────────────────
@router.post("/buildings")
async def create_building(body: BuildingCreate, _: dict = Depends(require_role("owner"))):
    if not body.name or not body.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    payload = {k: v for k, v in body.model_dump().items() if v is not None}
    payload["name"] = payload["name"].strip()
    resp = supabase.table("prop_buildings").insert(payload).execute()
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
    if "name" in updates:
        updates["name"] = updates["name"].strip()
    resp = supabase.table("prop_buildings").update(updates).eq("id", building_id).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Building not found")
    return resp.data[0]


@router.delete("/buildings/{building_id}")
async def delete_building(building_id: str, _: dict = Depends(require_role("owner"))):
    supabase.table("prop_buildings").delete().eq("id", building_id).execute()
    return {"id": building_id, "deleted": True}


# ── Units ─────────────────────────────────────────────────────────────────
@router.post("/units")
async def create_unit(body: UnitCreate, _: dict = Depends(require_role("owner"))):
    b = (
        supabase.table("prop_buildings")
        .select("id")
        .eq("id", body.building_id)
        .maybe_single()
        .execute()
    )
    if not getattr(b, "data", None):
        raise HTTPException(status_code=404, detail="Building not found")
    payload = {
        "building_id": body.building_id,
        "name": body.name.strip(),
        "unit_type": body.unit_type,
        "notes": body.notes,
    }
    resp = supabase.table("prop_units").insert(payload).execute()
    if not resp.data:
        raise HTTPException(status_code=500, detail="Failed to create unit")
    return resp.data[0]


@router.patch("/units/{unit_id}")
async def update_unit(unit_id: str, body: UnitUpdate, _: dict = Depends(require_role("owner"))):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    if "name" in updates:
        updates["name"] = updates["name"].strip()
    resp = supabase.table("prop_units").update(updates).eq("id", unit_id).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Unit not found")
    return resp.data[0]


@router.delete("/units/{unit_id}")
async def delete_unit(unit_id: str, _: dict = Depends(require_role("owner"))):
    supabase.table("prop_units").delete().eq("id", unit_id).execute()
    return {"id": unit_id, "deleted": True}


# ── Rooms (with financials side-by-side) ──────────────────────────────────
def _split_room_body(body_dict: dict) -> tuple[dict, dict]:
    structural = {k: v for k, v in body_dict.items() if k in STRUCTURAL_ROOM_FIELDS and v is not None}
    financial = {k: v for k, v in body_dict.items() if k in FINANCIAL_ROOM_FIELDS and v is not None}
    return structural, financial


@router.post("/rooms")
async def create_room(body: RoomCreate, _: dict = Depends(require_role("owner"))):
    u = (
        supabase.table("prop_units")
        .select("id")
        .eq("id", body.unit_id)
        .maybe_single()
        .execute()
    )
    if not getattr(u, "data", None):
        raise HTTPException(status_code=404, detail="Unit not found")

    body_dict = body.model_dump()
    structural, financial = _split_room_body(body_dict)
    structural["unit_id"] = body.unit_id
    structural["name"] = body.name.strip()
    if "amenity_ids" not in structural:
        structural["amenity_ids"] = []

    ins = supabase.table("prop_rooms").insert(structural).execute()
    if not ins.data:
        raise HTTPException(status_code=500, detail="Failed to create room")
    room = ins.data[0]
    room_id = room["id"]

    if financial:
        financial["room_id"] = room_id
        supabase.table("prop_financials").insert(financial).execute()
    return {**room, "financials": financial if financial else None}


@router.patch("/rooms/{room_id}")
async def update_room(room_id: str, body: RoomUpdate, _: dict = Depends(require_role("owner"))):
    body_dict = body.model_dump()
    structural, financial = _split_room_body(body_dict)
    if not structural and not financial:
        raise HTTPException(status_code=400, detail="No fields to update")

    if "name" in structural:
        structural["name"] = structural["name"].strip()

    if structural:
        resp = supabase.table("prop_rooms").update(structural).eq("id", room_id).execute()
        if not resp.data:
            raise HTTPException(status_code=404, detail="Room not found")

    if financial:
        # Upsert into financials (insert if missing, update if present)
        existing = (
            supabase.table("prop_financials")
            .select("id")
            .eq("room_id", room_id)
            .maybe_single()
            .execute()
        )
        if getattr(existing, "data", None):
            supabase.table("prop_financials").update(financial).eq("room_id", room_id).execute()
        else:
            financial["room_id"] = room_id
            supabase.table("prop_financials").insert(financial).execute()

    # Return latest combined view
    room = (
        supabase.table("prop_rooms").select("*").eq("id", room_id).maybe_single().execute()
    )
    fin = (
        supabase.table("prop_financials")
        .select("*")
        .eq("room_id", room_id)
        .maybe_single()
        .execute()
    )
    return {**(getattr(room, "data", {}) or {}), "financials": getattr(fin, "data", None)}


@router.delete("/rooms/{room_id}")
async def delete_room(room_id: str, _: dict = Depends(require_role("owner"))):
    supabase.table("prop_rooms").delete().eq("id", room_id).execute()
    return {"id": room_id, "deleted": True}


# ── Monthly performance ───────────────────────────────────────────────────
@router.get("/monthly-performance")
async def list_monthly_perf(
    building_id: Optional[str] = None,
    year: Optional[int] = None,
    _: dict = Depends(require_role("owner", "investor", "operator")),
):
    q = supabase.table("prop_monthly_performance").select("*")
    if building_id:
        q = q.eq("building_id", building_id)
    if year:
        q = q.eq("period_year", year)
    rows = (
        q.order("period_year", desc=True).order("period_month", desc=True).execute().data
        or []
    )
    return {"rows": rows}


@router.post("/monthly-performance")
async def create_monthly_perf(
    body: MonthlyPerfCreate,
    _: dict = Depends(require_role("owner")),
):
    payload = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        resp = supabase.table("prop_monthly_performance").insert(payload).execute()
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Insert failed (likely duplicate period): {e}")
    if not resp.data:
        raise HTTPException(status_code=500, detail="Insert failed")
    return resp.data[0]


@router.patch("/monthly-performance/{row_id}")
async def update_monthly_perf(
    row_id: str,
    body: MonthlyPerfUpdate,
    _: dict = Depends(require_role("owner")),
):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    resp = (
        supabase.table("prop_monthly_performance")
        .update(updates)
        .eq("id", row_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="Row not found")
    return resp.data[0]


@router.delete("/monthly-performance/{row_id}")
async def delete_monthly_perf(row_id: str, _: dict = Depends(require_role("owner"))):
    supabase.table("prop_monthly_performance").delete().eq("id", row_id).execute()
    return {"id": row_id, "deleted": True}

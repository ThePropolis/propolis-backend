"""
Canonical inventory CRUD — buildings → units → rooms.

Source of truth for the property portfolio. Seeded once from the XLSX via
scripts/import_inventory.py; after that, the website is authoritative.
All endpoints owner-only.
"""
from collections import defaultdict
from typing import List, Literal, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import require_role
from database import supabase

router = APIRouter(prefix="/api/inventory", tags=["inventory"])

Length = Literal["LTR", "STR"]
Strategy = Literal["Coliving", "Entire Apt"]


# ── Pydantic models ────────────────────────────────────────────────────────
class BuildingCreate(BaseModel):
    name: str
    full_name: Optional[str] = None
    address: Optional[str] = None
    owner_llc: Optional[str] = None
    units_count: Optional[int] = None
    beds_count: Optional[int] = None
    floors: Optional[int] = None
    has_elevator: Optional[bool] = None
    notes: Optional[str] = None


class BuildingUpdate(BaseModel):
    name: Optional[str] = None
    full_name: Optional[str] = None
    address: Optional[str] = None
    owner_llc: Optional[str] = None
    units_count: Optional[int] = None
    beds_count: Optional[int] = None
    floors: Optional[int] = None
    has_elevator: Optional[bool] = None
    notes: Optional[str] = None


class UnitCreate(BaseModel):
    building_id: str
    name: str
    notes: Optional[str] = None


class UnitUpdate(BaseModel):
    name: Optional[str] = None
    notes: Optional[str] = None


class _RoomBase(BaseModel):
    name: Optional[str] = None
    length: Optional[Length] = None
    strategy: Optional[Strategy] = None
    bed_size: Optional[str] = None
    bathroom: Optional[str] = None
    ceiling_height: Optional[str] = None
    balcony: Optional[str] = None
    room_type_name: Optional[str] = None
    amenities: Optional[List[str]] = None
    notes: Optional[str] = None
    # Money / financials
    base_rent: Optional[float] = None
    market_rent: Optional[float] = None
    actual_rent: Optional[float] = None
    revenue_year: Optional[float] = None
    revenue_month: Optional[float] = None
    is_ada: Optional[bool] = None
    extras: Optional[str] = None
    adjustment: Optional[float] = None
    actual_rent_with_util: Optional[float] = None
    pessimistic_rent: Optional[float] = None
    concession_rent: Optional[float] = None
    concession_rent_with_util: Optional[float] = None
    stake_5_cashback: Optional[float] = None
    stake_8_cashback: Optional[float] = None
    revenue_per_apartment: Optional[float] = None
    unit_type: Optional[str] = None
    listing_date: Optional[str] = None  # ISO yyyy-mm-dd


class RoomCreate(_RoomBase):
    unit_id: str
    name: str  # required on create


class RoomUpdate(_RoomBase):
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


# ── Read ───────────────────────────────────────────────────────────────────
@router.get("")
async def list_inventory(_: dict = Depends(require_role("owner"))):
    """Return the full tree: buildings → units → rooms."""
    buildings = (
        supabase.table("inv_buildings")
        .select("*")
        .order("name")
        .execute()
        .data
        or []
    )
    units = (
        supabase.table("inv_units")
        .select("*")
        .execute()
        .data
        or []
    )
    rooms = (
        supabase.table("inv_rooms")
        .select("*")
        .execute()
        .data
        or []
    )

    rooms_by_unit: dict = defaultdict(list)
    for r in rooms:
        rooms_by_unit[r["unit_id"]].append(r)
    for v in rooms_by_unit.values():
        v.sort(key=lambda x: (x.get("name") or ""))

    units_by_building: dict = defaultdict(list)
    for u in units:
        u_with_rooms = {**u, "rooms": rooms_by_unit.get(u["id"], [])}
        units_by_building[u["building_id"]].append(u_with_rooms)
    for v in units_by_building.values():
        v.sort(key=lambda x: (x.get("name") or ""))

    tree = [
        {**b, "units": units_by_building.get(b["id"], [])}
        for b in buildings
    ]

    # Useful for filter widgets in the UI
    all_amenities = sorted({
        a for r in rooms for a in (r.get("amenities") or [])
    })

    return {"buildings": tree, "all_amenities": all_amenities}


# ── Buildings CRUD ─────────────────────────────────────────────────────────
@router.post("/buildings")
async def create_building(body: BuildingCreate, _: dict = Depends(require_role("owner"))):
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    payload = {k: v for k, v in body.model_dump().items() if v is not None}
    payload["name"] = payload["name"].strip()
    resp = supabase.table("inv_buildings").insert(payload).execute()
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
    resp = (
        supabase.table("inv_buildings")
        .update(updates)
        .eq("id", building_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="Building not found")
    return resp.data[0]


@router.delete("/buildings/{building_id}")
async def delete_building(building_id: str, _: dict = Depends(require_role("owner"))):
    supabase.table("inv_buildings").delete().eq("id", building_id).execute()
    return {"id": building_id, "deleted": True}


# ── Units CRUD ─────────────────────────────────────────────────────────────
@router.post("/units")
async def create_unit(body: UnitCreate, _: dict = Depends(require_role("owner"))):
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    b = (
        supabase.table("inv_buildings")
        .select("id")
        .eq("id", body.building_id)
        .maybe_single()
        .execute()
    )
    if not getattr(b, "data", None):
        raise HTTPException(status_code=404, detail="Building not found")
    resp = (
        supabase.table("inv_units")
        .insert({
            "building_id": body.building_id,
            "name": body.name.strip(),
            "notes": body.notes,
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
    if "name" in updates:
        updates["name"] = updates["name"].strip()
    resp = supabase.table("inv_units").update(updates).eq("id", unit_id).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Unit not found")
    return resp.data[0]


@router.delete("/units/{unit_id}")
async def delete_unit(unit_id: str, _: dict = Depends(require_role("owner"))):
    supabase.table("inv_units").delete().eq("id", unit_id).execute()
    return {"id": unit_id, "deleted": True}


# ── Rooms CRUD ─────────────────────────────────────────────────────────────
@router.post("/rooms")
async def create_room(body: RoomCreate, _: dict = Depends(require_role("owner"))):
    if not body.name.strip():
        raise HTTPException(status_code=400, detail="Name is required")
    u = (
        supabase.table("inv_units")
        .select("id")
        .eq("id", body.unit_id)
        .maybe_single()
        .execute()
    )
    if not getattr(u, "data", None):
        raise HTTPException(status_code=404, detail="Unit not found")
    payload = {k: v for k, v in body.model_dump().items() if v is not None}
    payload["name"] = payload["name"].strip()
    if "amenities" not in payload:
        payload["amenities"] = []
    resp = supabase.table("inv_rooms").insert(payload).execute()
    if not resp.data:
        raise HTTPException(status_code=500, detail="Failed to create room")
    return resp.data[0]


@router.patch("/rooms/{room_id}")
async def update_room(
    room_id: str,
    body: RoomUpdate,
    _: dict = Depends(require_role("owner")),
):
    updates = {k: v for k, v in body.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")
    if "name" in updates:
        updates["name"] = updates["name"].strip()
    resp = supabase.table("inv_rooms").update(updates).eq("id", room_id).execute()
    if not resp.data:
        raise HTTPException(status_code=404, detail="Room not found")
    return resp.data[0]


@router.delete("/rooms/{room_id}")
async def delete_room(room_id: str, _: dict = Depends(require_role("owner"))):
    supabase.table("inv_rooms").delete().eq("id", room_id).execute()
    return {"id": room_id, "deleted": True}


# ── Monthly performance ────────────────────────────────────────────────────
@router.get("/monthly-performance")
async def list_monthly_perf(
    building_id: Optional[str] = None,
    year: Optional[int] = None,
    _: dict = Depends(require_role("owner")),
):
    q = supabase.table("inv_monthly_performance").select("*")
    if building_id:
        q = q.eq("building_id", building_id)
    if year:
        q = q.eq("period_year", year)
    rows = q.order("period_year", desc=True).order("period_month", desc=True).execute().data or []
    return {"rows": rows}


@router.post("/monthly-performance")
async def create_monthly_perf(
    body: MonthlyPerfCreate,
    _: dict = Depends(require_role("owner")),
):
    payload = {k: v for k, v in body.model_dump().items() if v is not None}
    try:
        resp = supabase.table("inv_monthly_performance").insert(payload).execute()
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=f"Failed to insert (likely duplicate building+period): {e}",
        )
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
        supabase.table("inv_monthly_performance")
        .update(updates)
        .eq("id", row_id)
        .execute()
    )
    if not resp.data:
        raise HTTPException(status_code=404, detail="Row not found")
    return resp.data[0]


@router.delete("/monthly-performance/{row_id}")
async def delete_monthly_perf(
    row_id: str,
    _: dict = Depends(require_role("owner")),
):
    supabase.table("inv_monthly_performance").delete().eq("id", row_id).execute()
    return {"id": row_id, "deleted": True}


# ── Financial summary ──────────────────────────────────────────────────────
@router.get("/financial-summary")
async def financial_summary(_: dict = Depends(require_role("owner"))):
    """Roll-up across all buildings: monthly + annual rent potential, by length."""
    rooms = (
        supabase.table("inv_rooms")
        .select("unit_id,length,actual_rent,base_rent,revenue_year,revenue_month")
        .execute()
        .data
        or []
    )
    units = (
        supabase.table("inv_units")
        .select("id,building_id,name")
        .execute()
        .data
        or []
    )
    unit_to_building = {u["id"]: u["building_id"] for u in units}

    def num(x):
        try:
            return float(x or 0)
        except (TypeError, ValueError):
            return 0.0

    by_building: dict = {}
    totals = {"actual_rent_monthly": 0.0, "actual_rent_annual": 0.0,
              "revenue_year": 0.0, "ltr_rooms": 0, "str_rooms": 0, "rooms": 0}

    for r in rooms:
        bid = unit_to_building.get(r["unit_id"])
        if not bid:
            continue
        b = by_building.setdefault(bid, {
            "actual_rent_monthly": 0.0, "actual_rent_annual": 0.0,
            "revenue_year": 0.0, "ltr_rooms": 0, "str_rooms": 0, "rooms": 0,
        })
        rent = num(r.get("actual_rent")) or num(r.get("base_rent"))
        rev_yr = num(r.get("revenue_year"))
        b["actual_rent_monthly"] += rent
        b["actual_rent_annual"] += rent * 12
        b["revenue_year"] += rev_yr
        b["rooms"] += 1
        if r.get("length") == "LTR":
            b["ltr_rooms"] += 1
        elif r.get("length") == "STR":
            b["str_rooms"] += 1

        totals["actual_rent_monthly"] += rent
        totals["actual_rent_annual"] += rent * 12
        totals["revenue_year"] += rev_yr
        totals["rooms"] += 1
        if r.get("length") == "LTR":
            totals["ltr_rooms"] += 1
        elif r.get("length") == "STR":
            totals["str_rooms"] += 1

    return {"by_building": by_building, "totals": totals}

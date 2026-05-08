"""
One-shot seed: copy the existing canonical inventory (`inv_*`) into the new
normalized portfolio schema (`prop_*`).

- Builds a stable amenity catalog from the union of strings on inv_rooms.
- Creates buildings/units/rooms with the same names so analytics tables that
  key on building name keep matching.
- Splits financial fields into prop_financials.
- Copies monthly performance rows.

Idempotent: re-runs only insert what's missing. Safe to run multiple times.
After cutover, edits should go directly to prop_* via /api/portfolio.
"""
from __future__ import annotations

import sys
from pathlib import Path

# Run from anywhere — find the Backend directory
HERE = Path(__file__).resolve().parent
BACKEND_DIR = HERE.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from database import supabase  # noqa: E402


# ── Catalog ──────────────────────────────────────────────────────────────
def seed_amenity_catalog() -> dict[str, str]:
    """Returns {name → uuid} for every amenity in use."""
    rooms = supabase.table("inv_rooms").select("amenities").execute().data or []
    names: set[str] = set()
    for r in rooms:
        for a in (r.get("amenities") or []):
            if isinstance(a, str) and a.strip():
                names.add(a.strip())

    existing = supabase.table("prop_amenities").select("id, name").execute().data or []
    name_to_id = {row["name"]: row["id"] for row in existing}

    new_count = 0
    for n in sorted(names):
        if n in name_to_id:
            continue
        ins = supabase.table("prop_amenities").insert({"name": n}).execute()
        if ins.data:
            name_to_id[n] = ins.data[0]["id"]
            new_count += 1
    return name_to_id, new_count


# ── Buildings ────────────────────────────────────────────────────────────
def seed_buildings() -> tuple[dict[str, str], int]:
    """Returns ({inv_building_id → prop_building_id}, created_count)."""
    src = supabase.table("inv_buildings").select("*").execute().data or []
    existing = supabase.table("prop_buildings").select("id, name").execute().data or []
    by_name = {row["name"]: row["id"] for row in existing}

    inv_to_prop: dict[str, str] = {}
    created = 0
    for b in src:
        name = b["name"]
        if name in by_name:
            inv_to_prop[b["id"]] = by_name[name]
            continue
        payload = {
            "name": name,
            "full_name": b.get("full_name"),
            "address": b.get("address"),
            "owner_llc": b.get("owner_llc"),
            "floors": b.get("floors"),
            "has_elevator": b.get("has_elevator"),
            "units_count": b.get("units_count"),
            "beds_count": b.get("beds_count"),
            "notes": b.get("notes"),
        }
        ins = supabase.table("prop_buildings").insert(payload).execute()
        if ins.data:
            inv_to_prop[b["id"]] = ins.data[0]["id"]
            by_name[name] = ins.data[0]["id"]
            created += 1
    return inv_to_prop, created


# ── Units ────────────────────────────────────────────────────────────────
def seed_units(building_map: dict[str, str]) -> tuple[dict[str, str], int]:
    src = supabase.table("inv_units").select("*").execute().data or []
    existing = supabase.table("prop_units").select("id, building_id, name").execute().data or []
    by_key = {(row["building_id"], row["name"]): row["id"] for row in existing}

    inv_to_prop: dict[str, str] = {}
    created = 0
    rows_to_insert = []
    pending_keys = []
    for u in src:
        prop_b = building_map.get(u["building_id"])
        if not prop_b:
            continue
        key = (prop_b, u["name"])
        if key in by_key:
            inv_to_prop[u["id"]] = by_key[key]
            continue
        rows_to_insert.append({
            "building_id": prop_b,
            "name": u["name"],
            "notes": u.get("notes"),
        })
        pending_keys.append((u["id"], key))

    if rows_to_insert:
        # Insert in chunks of 100 to be polite
        for i in range(0, len(rows_to_insert), 100):
            chunk = rows_to_insert[i:i + 100]
            ins = supabase.table("prop_units").insert(chunk).execute()
            for src_row, ret_row in zip(pending_keys[i:i + len(chunk)], ins.data or []):
                inv_to_prop[src_row[0]] = ret_row["id"]
                created += 1
    return inv_to_prop, created


# ── Rooms + Financials ───────────────────────────────────────────────────
FINANCIAL_FIELDS = (
    "actual_rent", "base_rent", "market_rent", "actual_rent_with_util",
    "pessimistic_rent", "concession_rent", "concession_rent_with_util",
    "adjustment", "stake_5_cashback", "stake_8_cashback",
    "revenue_month", "revenue_year", "revenue_per_apartment", "extras",
)


def seed_rooms_and_financials(unit_map: dict[str, str], amenity_map: dict[str, str]) -> tuple[int, int]:
    src = supabase.table("inv_rooms").select("*").execute().data or []
    existing = supabase.table("prop_rooms").select("id, unit_id, name").execute().data or []
    by_key = {(row["unit_id"], row["name"]): row["id"] for row in existing}

    # Pull existing financial rows so we can avoid re-inserting
    existing_fin = (
        supabase.table("prop_financials").select("room_id").execute().data or []
    )
    finalized_rooms = {row["room_id"] for row in existing_fin}

    rooms_created = 0
    fin_created = 0

    for r in src:
        prop_u = unit_map.get(r["unit_id"])
        if not prop_u:
            continue

        key = (prop_u, r["name"])
        if key in by_key:
            room_id = by_key[key]
        else:
            amenity_uuids = []
            for a in (r.get("amenities") or []):
                aid = amenity_map.get(a)
                if aid:
                    amenity_uuids.append(aid)

            payload = {
                "unit_id": prop_u,
                "name": r["name"],
                "length": r.get("length"),
                "strategy": r.get("strategy"),
                "bed_size": r.get("bed_size"),
                "bathroom": r.get("bathroom"),
                "ceiling_height": r.get("ceiling_height"),
                "balcony": r.get("balcony"),
                "room_type_name": r.get("room_type_name"),
                "is_ada": r.get("is_ada"),
                "listing_date": r.get("listing_date"),
                "amenity_ids": amenity_uuids,
                "notes": r.get("notes"),
            }
            ins = supabase.table("prop_rooms").insert(payload).execute()
            if not ins.data:
                continue
            room_id = ins.data[0]["id"]
            by_key[key] = room_id
            rooms_created += 1

        # Financials
        if room_id not in finalized_rooms:
            fin_payload = {"room_id": room_id}
            for f in FINANCIAL_FIELDS:
                if r.get(f) is not None:
                    fin_payload[f] = r.get(f)
            # Only insert when there's at least one money value to record
            if len(fin_payload) > 1:
                supabase.table("prop_financials").insert(fin_payload).execute()
                finalized_rooms.add(room_id)
                fin_created += 1
    return rooms_created, fin_created


# ── Monthly performance ─────────────────────────────────────────────────
def seed_monthly_perf(building_map: dict[str, str]) -> int:
    src = supabase.table("inv_monthly_performance").select("*").execute().data or []
    existing = (
        supabase.table("prop_monthly_performance")
        .select("building_id, period_year, period_month")
        .execute()
        .data
        or []
    )
    seen = {(row["building_id"], row["period_year"], row["period_month"]) for row in existing}

    created = 0
    for p in src:
        prop_b = building_map.get(p["building_id"])
        if not prop_b:
            continue
        key = (prop_b, p["period_year"], p["period_month"])
        if key in seen:
            continue
        ins = supabase.table("prop_monthly_performance").insert({
            "building_id": prop_b,
            "period_year": p["period_year"],
            "period_month": p["period_month"],
            "occupancy_pct": p.get("occupancy_pct"),
            "adr": p.get("adr"),
            "revpar": p.get("revpar"),
            "revenue": p.get("revenue"),
            "notes": p.get("notes"),
        }).execute()
        if ins.data:
            created += 1
    return created


def main() -> None:
    print("Seeding portfolio from inventory…")
    amenity_map, am_created = seed_amenity_catalog()
    print(f"  amenities: +{am_created} new (total catalog: {len(amenity_map)})")

    building_map, b_created = seed_buildings()
    print(f"  buildings: +{b_created}")

    unit_map, u_created = seed_units(building_map)
    print(f"  units:     +{u_created}")

    rooms_created, fin_created = seed_rooms_and_financials(unit_map, amenity_map)
    print(f"  rooms:     +{rooms_created}")
    print(f"  financials: +{fin_created}")

    perf_created = seed_monthly_perf(building_map)
    print(f"  monthly perf rows: +{perf_created}")

    print("Done. Re-run anytime — it's idempotent.")


if __name__ == "__main__":
    main()

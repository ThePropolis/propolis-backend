"""
Merge the rich DoorLoop amenities (in `facility_units.amenities`) into the
new portfolio model (`prop_rooms.amenity_ids` + `prop_amenities` catalog).

The original seed only pulled amenity strings from `inv_rooms.amenities` —
those came from the XLSX, which only had 3 distinct strings. DoorLoop has
~30 — Dishwasher, Washer, AirConditioner, Microwave, etc.

This script is idempotent: re-runs only add what's missing on each room.
Match logic: building name match, then room name match
(`facility_units.name` already uses the same "11A"-style ids).
"""
from __future__ import annotations

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
BACKEND_DIR = HERE.parent
sys.path.insert(0, str(BACKEND_DIR))

from dotenv import load_dotenv
load_dotenv(BACKEND_DIR / ".env")

from database import supabase  # noqa: E402


def main() -> None:
    print("Merging DoorLoop amenities into Listings…")

    # ── Catalog: ensure every amenity string has a row ──────────────
    facility_units = (
        supabase.table("facility_units").select("building_id, name, amenities").execute().data or []
    )
    facility_buildings = (
        supabase.table("facility_buildings").select("id, name").execute().data or []
    )
    prop_buildings = (
        supabase.table("prop_buildings").select("id, name").execute().data or []
    )
    prop_rooms = (
        supabase.table("prop_rooms").select("id, unit_id, name, amenity_ids").execute().data or []
    )
    prop_units = supabase.table("prop_units").select("id, building_id, name").execute().data or []
    existing_amenities = (
        supabase.table("prop_amenities").select("id, name").execute().data or []
    )

    # Build amenity catalog map
    name_to_aid: dict[str, str] = {row["name"]: row["id"] for row in existing_amenities}
    needed: set[str] = set()
    for u in facility_units:
        for a in (u.get("amenities") or []):
            if isinstance(a, str) and a.strip():
                needed.add(a.strip())
    new_amenities = sorted(needed - set(name_to_aid.keys()))
    for n in new_amenities:
        ins = supabase.table("prop_amenities").insert({"name": n}).execute()
        if ins.data:
            name_to_aid[n] = ins.data[0]["id"]
    print(f"  amenities catalog: +{len(new_amenities)} new (total: {len(name_to_aid)})")

    # ── Index lookup helpers ───────────────────────────────────────
    fb_id_to_name = {b["id"]: b["name"] for b in facility_buildings}
    pb_name_to_id = {b["name"]: b["id"] for b in prop_buildings}

    # rooms keyed by (prop_building_id, room_name) for fast match
    pu_id_to_building = {u["id"]: u["building_id"] for u in prop_units}
    rooms_by_key: dict[tuple[str, str], dict] = {}
    for r in prop_rooms:
        bid = pu_id_to_building.get(r["unit_id"])
        if bid:
            rooms_by_key[(bid, r["name"])] = r

    # ── Merge ──────────────────────────────────────────────────────
    rooms_updated = 0
    no_match_rooms: list[str] = []
    for fu in facility_units:
        fb_name = fb_id_to_name.get(fu["building_id"])
        if not fb_name:
            continue
        # facility_buildings names are like "Aerie Apartments"; prop_buildings.name
        # may be "Aerie". Try both.
        candidate_names = [fb_name]
        if fb_name.endswith(" Apartments"):
            candidate_names.append(fb_name[: -len(" Apartments")])
        prop_b_id = next((pb_name_to_id[n] for n in candidate_names if n in pb_name_to_id), None)
        if not prop_b_id:
            continue

        # facility_units.name is e.g. "Unit 12B"; prop_rooms.name is "12B".
        # Try the raw name and a few sensible variants.
        raw = fu["name"] or ""
        candidates = [raw, raw.removeprefix("Unit ").strip(), raw.removeprefix("Unit").strip()]
        room = next(
            (rooms_by_key.get((prop_b_id, n)) for n in candidates if (prop_b_id, n) in rooms_by_key),
            None,
        )
        if not room:
            no_match_rooms.append(f"{fb_name} · {fu['name']}")
            continue

        new_ids = list(room.get("amenity_ids") or [])
        existing_ids_set = set(new_ids)
        added = False
        for a_str in (fu.get("amenities") or []):
            aid = name_to_aid.get(a_str)
            if aid and aid not in existing_ids_set:
                new_ids.append(aid)
                existing_ids_set.add(aid)
                added = True
        if added:
            supabase.table("prop_rooms").update({"amenity_ids": new_ids}).eq("id", room["id"]).execute()
            rooms_updated += 1

    print(f"  rooms updated:     {rooms_updated}")
    if no_match_rooms:
        print(f"  unmatched rooms:   {len(no_match_rooms)} (e.g. {no_match_rooms[:3]})")
    print("Done.")


if __name__ == "__main__":
    main()

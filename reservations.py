# src/main.py

from datetime import datetime
import os
from fastapi import APIRouter, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from database import supabase

router = APIRouter()
class ReservationGraphData(BaseModel):
    id: int
    guesty_created_at: Optional[str]
    property_full_name: Optional[str]
    total_paid: Optional[float]

class Reservation(ReservationGraphData):
    guesty_guest_id: Optional[str]
    guesty_listing_id: Optional[str]
    guesty_owner_id: Optional[str]
    property_name: Optional[str]
    bedroom_name: Optional[str]
    apartment_id: Optional[str]
    property_full_name: Optional[str]
    unit_full_name: Optional[str]
    reservation_start_date: Optional[datetime]
    reservation_end_date: Optional[datetime]
    guest_name: Optional[str]
    guest_email: Optional[str]
    guest_phone: Optional[str]
    guest_emails: Optional[Dict[str, Any]]
    reservation_status: Optional[str]
    is_fully_paid: Optional[bool]
    source: Optional[str]
    price: Optional[float]
    total_paid: Optional[float]
    total_due: Optional[float]
    reservation_details_obj: Optional[Dict[str, Any]]
    guesty_reservation_id: Optional[str]
    salto_user_id: Optional[str]
    salto_user_api_id: Optional[str]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    deleted_at: Optional[datetime]
    apartment_name: Optional[str]
    site_id: Optional[str]
    access_group_name: Optional[str]
    night_count: Optional[int]
    guest_count: Optional[int]
    confirmedAt: Optional[datetime]
    guesty_updated_at: Optional[datetime]



@router.get(
    "/api/reservations/",
    response_model=List[ReservationGraphData],
    summary="Get reservations with specific filters"
)
def get_reservations(
    date_start: Optional[str] = Query(None, description="start date of filter"),
    date_end: Optional[str] = Query(None, description="end date of filter"),
    number_of_beds: Optional[int] = Query(None, description="number of beds to filter on"),
    property_type: Optional[str] = Query(None, description="filter on co-living or entire unit"),
    building_names: Optional[List[str]] = Query(None, description="Property names to filter on"),
    property_full_names: Optional[List[str]] = Query(None, description="Full property names to filter on")
) -> List[ReservationGraphData]:
    """
    Get reservation data with filtering options.
    """
    # Step 1: Get filtered listings
    listing_query = supabase.from_("jd_listing").select("id, bedrooms, property_type") 
    
    if property_type:
        listing_query = listing_query.eq("property_type", property_type)
    if number_of_beds:
        listing_query = listing_query.eq("bedrooms", number_of_beds)
    
    listings_response = listing_query.execute()
    listings = listings_response.data or []
    
    listing_map = {l["id"]: l for l in listings}
    listing_ids = list(listing_map.keys())
   
    if not listing_ids:
        return []
    
    # Step 2: Get reservations with filters
    reservation_query = (
    supabase
    .from_("reservations")
    .select("total_paid, guesty_created_at, guesty_listing_id, property_full_name, property_name, id")
    .filter("total_paid", "neq", 0)
    .order("guesty_created_at", desc=False)
)

# Combine filters with OR logic
    or_conditions = []

    if building_names:
        building_names_str = ",".join([f'"{name}"' for name in building_names])
        or_conditions.append(f"property_name.in.({building_names_str})")

    if property_full_names:
        property_full_names_str = ",".join([f'"{name}"' for name in property_full_names])
        or_conditions.append(f"property_full_name.in.({property_full_names_str})")

    if or_conditions:
        # Join conditions with a comma — this creates an OR query in Supabase
        reservation_query = reservation_query.or_(",".join(or_conditions))

        
        
    # Date filters
    if date_start:
        reservation_query = reservation_query.gte("guesty_created_at", date_start)
    if date_end:
        reservation_query = reservation_query.lte("guesty_created_at", date_end)
    
    reservations_response = reservation_query.execute()
    reservations = reservations_response.data or []
    
    # Step 3: Join and return results
    result = []
    for r in reservations:
        print(r)
        if r["guesty_listing_id"] in listing_ids and r['guesty_created_at'] != None: 
            result.append(ReservationGraphData(
                id=r["id"],
                total_paid=r["total_paid"],
                guesty_created_at=r["guesty_created_at"],
                property_full_name=r.get("property_full_name")
            ))

   
   
    
    return result


@router.get(
    "/api/reservations/names",
    response_model=Dict[str, List[str]],
    summary="Get unique property and building names"
)
def get_property_and_building_names():
    """
    Get a list of all unique property and building names from the database.
    The response will have two keys:
    - property_names: List of property full names
    - building_names: List of building names
    """
    res = (
        supabase
        .from_("reservations")
        .select("property_name, property_full_name")
        .execute()
    )

    property_names = set()
    building_names = set()

    for item in res.data:
        if item.get("property_full_name"):
            property_names.add(item["property_full_name"])
        if item.get("property_name"):
            building_names.add(item["property_name"])

    return {
        "property_names": sorted(list(property_names)),  # Sort alphabetically
        "building_names": sorted(list(building_names))   # Sort alphabetically
    }
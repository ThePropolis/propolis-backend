# src/main.py

from datetime import datetime
import os
from fastapi import APIRouter, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from database import supabase

router = APIRouter()
class ReservationGraphData(BaseModel):
    guesty_created_at: Optional[str]
    total_paid: Optional[float]

class Reservation(ReservationGraphData):
    id: int
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
    number_of_beds: Optional[List[int]] = Query(None, description="number of beds to filter on"),
    property_type: Optional[str] = Query(None, description="filter on co-living or entire unit"),
    property_full_name: Optional[str] = Query(None, description="Full name of the property")
) -> List[ReservationGraphData]:
    # Step 1: Get filtered listings
    listing_query = supabase.from_("jd_listing").select("id, bedrooms, property_type") 
    if property_type:
        listing_query = listing_query.eq("property_type", property_type)
    if number_of_beds:
        listing_query = listing_query.in_("bedrooms", number_of_beds)
    listings_response = listing_query.execute()
    listings = listings_response.data or []
    
    # Create a mapping of listing_id to listing details
    listing_map = {l["id"]: l for l in listings}
    listing_ids = list(listing_map.keys())
    
    # If no listings match the criteria, return empty result
    if not listing_ids:
        return []
    
    # Step 2: Get reservations only for the filtered listings
    reservation_query = (
        supabase
        .from_("reservations")
        .select("total_paid, guesty_created_at, guesty_listing_id")
        .filter("total_paid", "neq", 0)
    )
    # print(listing_ids)
    print(property_full_name, "")
    if property_full_name:
        listing_query = reservation_query.filter("property_full_name", "eq", property_full_name)
    if date_start:
        reservation_query = reservation_query.gte("guesty_created_at", date_start)
    if date_end:
        reservation_query = reservation_query.lte("guesty_created_at", date_end)
        
    reservations_response = reservation_query.execute()
    reservations = reservations_response.data or []
    
    # Step 3: Join the data and return proper model instances
    result = []
    for r in reservations:
        listing = listing_map.get(r["guesty_listing_id"])
        if listing:  # This check is probably redundant now due to the in_() filter
            result.append(ReservationGraphData(
                total_paid=r["total_paid"],
                guesty_created_at=r["guesty_created_at"],
                bedrooms=listing.get("bedrooms"),
                property_type=listing.get("property_type"),
                listing_id=r["guesty_listing_id"]
            ))
    return result





@router.get(
    "/api/reservations/names",
    response_model=List[str],
    summary="Get reservations names"
)
@router.get(
    "/api/reservations/names",
    response_model=List[str],
    summary="Get reservations names"
)
def get_property_names():
    # Use from_() instead of table() to be consistent
    res = (
        supabase
        .from_("reservations")
        .select("property_full_name")
        .execute()
    )
    
    # Filter out None values and create a set of unique names
    property_names = [item["property_full_name"] for item in res.data if item.get("property_full_name")]
    return list(set(property_names))

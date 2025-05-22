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
    building_name: Optional[str] = Query(None, description="The property name"),
    building_names: Optional[List[str]] = Query(None, description="Multiple property names"),
    property_full_name: Optional[str] = Query(None, description="Full name of the property"),
    property_full_names: Optional[List[str]] = Query(None, description="Multiple full property names")
) -> List[ReservationGraphData]:
    """
    Get reservation data with multiple filtering options, including support for
    multiple buildings or properties at once.
    """
    # Log the request parameters for debugging
    print("Received request with parameters:")
    print(f"date_start: {date_start}")
    print(f"date_end: {date_end}")
    print(f"number_of_beds: {number_of_beds}")
    print(f"property_type: {property_type}")
    print(f"building_name: {building_name}")
    print(f"building_names: {building_names}")
    print(f"property_full_name: {property_full_name}")
    print(f"property_full_names: {property_full_names}")
    
    # Step 1: Get filtered listings
    listing_query = supabase.from_("jd_listing").select("id, bedrooms, property_type") 
    
    if property_type:
        listing_query = listing_query.eq("property_type", property_type)
    if number_of_beds:
        listing_query = listing_query.eq("bedrooms", number_of_beds)
    listings_response = listing_query.execute()
    listings = listings_response.data or []
    
    print(listings)
    # Create a mapping of listing_id to listing details
    listing_map = {l["id"]: l for l in listings}
    listing_ids = list(listing_map.keys())
    
    # Step 2: Get reservations with all applied filters
    reservation_query = (
        supabase
        .from_("reservations")
        .select("total_paid, guesty_created_at, guesty_listing_id, property_full_name, property_name, id")
        .filter("total_paid", "neq", 0)
    )

    # Handle multiple building names
    if building_names and len(building_names) > 0:
        reservation_query = reservation_query.in_("property_name", building_names)
    elif building_name:
        reservation_query = reservation_query.eq("property_name", building_name)
        
    # Handle multiple property names
    if property_full_names and len(property_full_names) > 0:
        reservation_query = reservation_query.in_("property_full_name", property_full_names)
    elif property_full_name:
        reservation_query = reservation_query.eq("property_full_name", property_full_name)
        
    # Date filters
    if date_start:
        reservation_query = reservation_query.gte("guesty_created_at", date_start)
    if date_end:
        reservation_query = reservation_query.lte("guesty_created_at", date_end)
    
    # Execute the query
    reservations_response = reservation_query.execute()
    reservations = reservations_response.data or []
    
    # Step 3: Join the data and return with property information included
    result = []
    for r in reservations:
        # If we're not filtering by listing details, or if this listing matches our filters
        if not listing_ids or r["guesty_listing_id"] in listing_ids:  
            result.append(ReservationGraphData(
                id=r["id"],
                total_paid=r["total_paid"],
                guesty_created_at=r["guesty_created_at"],
                property_full_name=r.get("property_full_name")  # Include property name for grouping on frontend
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
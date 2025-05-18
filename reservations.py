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
    summary="Get reservations for a property with non-zero total_paid"
)
def get_reservations(
    property_full_name: str = Query(..., description="Full name of the property")
) -> List[Dict]:
    res = (
        supabase
        .table("reservations")
        .select("total_paid, guesty_created_at")
        .filter("property_full_name", "eq", property_full_name)
        .filter("total_paid", "neq", 0)
        .order("guesty_created_at")  # optional: sort by date
        .execute()
    )

   

    return res.data or []


@router.get(
    "/api/reservations/names",
    response_model=List[str],
    summary="Get reservations names"
)
def get_property_names():
    # Run the Supabase query
    res = (
        supabase
        .table("reservations")
        .select("property_full_name")
        .execute() 
    )


    return list(set([item["property_full_name"] for item in res.data]))


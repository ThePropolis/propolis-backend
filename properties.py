
from datetime import datetime
import os
from fastapi import APIRouter, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from database import supabase

router = APIRouter()

class GuestyListing(BaseModel):
    id: str = Field(..., description="Primary key, text")
    account_id: str
    created_at: datetime
    last_updated_at: Optional[datetime] = None
    imported_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None

    title: Optional[str] = None
    nickname: Optional[str] = None
    property_type: Optional[str] = None
    room_type: Optional[str] = None

    accommodates: Optional[int] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    area_square_feet: Optional[float] = None
    minimum_age: Optional[int] = None

    complex_id: Optional[str] = None
    cleaning_status: Optional[str] = None
    active: Optional[str] = None

    address_building_name: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = None
    address_neighborhood: Optional[str] = None
    address_latitude: Optional[str] = None
    address_longitude: Optional[str] = None
    address_full: Optional[str] = None

    thumbnail_url: Optional[str] = None

    base_price: Optional[float] = None
    currency: Optional[str] = None
    weekly_price_factor: Optional[float] = None
    monthly_price_factor: Optional[float] = None
    extra_person_fee: Optional[float] = None
    security_deposit_fee: Optional[float] = None

    guests_included: Optional[int] = None
    min_nights: Optional[int] = None
    max_nights: Optional[int] = None

    description_summary: Optional[str] = None

    payment_provider_id: Optional[str] = None
    account_taxes: Optional[Dict[str, Any]] = None
    tags: List[str] = []
    amenities: List[str] = []

@router.get("/api/properties/listings",
    response_model=List[GuestyListing],
    summary="Get reservations for a property with non-zero total_paid"
)
def get_reservations() -> List[Dict]:
    res = (
        supabase
        .table("jd_listing")
        .select("*")
        .execute()
    )
    print("TEST")

   

    return res.data or []

from datetime import datetime
import os
from fastapi import APIRouter, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from database import supabase

router = APIRouter()

class GuestyListing(BaseModel):
    id: str = Field(..., description="Unique listing identifier")
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
    payment_provider_id: Optional[Dict[str, Any]] = None
    tags: List[str] = []
    amenities: Optional[Dict[str, Any]] = []
    amenities_not_included: Optional[Dict[str, Any]]= []
    saas: Optional[Dict[str, Any]] = None
    financials: Optional[Dict[str, Any]] = None
    cleaning_status: Optional[Dict[str, Any]] = None
    terms: Optional[Dict[str, Any]] = None
    prices: Optional[Dict[str, Any]] = None
    public_description: Optional[str] = None
    pms: Optional[Dict[str, Any]] = None
    calendar_rules: Optional[List[Dict[str, Any]]] = None
    receptionists_service: Optional[Dict[str, Any]] = None
    check_in_instructions: Optional[Dict[str, Any]] = None
    business_model: Optional[Dict[str, Any]] = None
    account_taxes: Optional[Dict[str, Any]] = None
    payment_provider_id: str
    cleaning_status: str

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
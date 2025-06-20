from datetime import datetime
import os
from fastapi import APIRouter, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from database import supabase

router = APIRouter()

class ListingPicture(BaseModel):
    full_url: str
    thumbnail_url: Optional[str] = None
    caption: Optional[str] = None
    display_order: int

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

class DetailedListing(BaseModel):
    """Extended listing model with detailed picture information"""
    # Inherit all basic fields
    id: str
    account_id: Optional[str] = None
    created_at: Optional[datetime] = None
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
    
    # Enhanced picture information
    pictures: List[str] = []  # Array of full_url strings for backward compatibility
    detailed_pictures: List[ListingPicture] = []  # Detailed picture objects with metadata

@router.get("/api/properties/listings/{listing_id}",
    response_model=DetailedListing,
    summary="Get a specific property with detailed picture information"
)
def get_property_by_id(listing_id: str) -> Dict[str, Any]:
    """
    Get a specific property by ID with detailed picture information from jd_listing_pictures table.
    
    This endpoint joins jd_listing with jd_listing_pictures using listing_id as the key
    and returns full_url, caption, and display_order for each picture.
    """
    # Fetch the specific listing
    listing_res = (
        supabase
        .table("jd_listing")
        .select("*")
        .eq("id", listing_id)
        .execute()
    )
    
    if not listing_res.data:
        raise HTTPException(status_code=404, detail=f"Property with ID '{listing_id}' not found")
    
    listing = listing_res.data[0]
    
    # Fetch pictures for this specific listing from jd_listing_pictures table
    pictures_res = (
        supabase
        .table("jd_listing_pictures")
        .select("full_url, thumbnail_url, caption, display_order")
        .eq("listing_id", listing_id)
        .order("display_order")
        .execute()
    )
    
    # Process pictures data
    detailed_pictures = []
    picture_urls = []
    
    if pictures_res.data:
        for pic in pictures_res.data:
            if pic["full_url"]:  # Only include pictures with valid full_url
                detailed_pictures.append({
                    "full_url": pic["full_url"],
                    "thumbnail_url": pic.get("thumbnail_url"),
                    "caption": pic.get("caption"),
                    "display_order": pic.get("display_order", 0)
                })
                picture_urls.append(pic["full_url"])
    
    # If no pictures found in jd_listing_pictures, fallback to thumbnail_url
    if not picture_urls and listing.get("thumbnail_url"):
        picture_urls = [listing["thumbnail_url"]]
        detailed_pictures = [{
            "full_url": listing["thumbnail_url"],
            "thumbnail_url": listing["thumbnail_url"],
            "caption": "Property thumbnail",
            "display_order": 0
        }]
    
    # Add picture data to listing
    listing["pictures"] = picture_urls
    listing["detailed_pictures"] = detailed_pictures
    
    return listing

@router.get("/api/properties/listings",
    response_model=List[GuestyListing],
    summary="Get all properties with pictures"
)
def get_reservations() -> List[Dict]:
    # Fetch listings with their associated pictures
    listings_res = (
        supabase
        .table("jd_listing")
        .select("*")
        .execute()
    )
    
    if not listings_res.data:
        return []
    
    # For each listing, fetch its pictures and replace thumbnail with full-size images
    for listing in listings_res.data:
        # Fetch pictures for this listing
        pictures_res = (
            supabase
            .table("jd_listing_pictures")
            .select("full_url, thumbnail_url, caption, display_order")
            .eq("listing_id", listing["id"])
            .order("display_order")
            .execute()
        )
        
        # Add full-size pictures array to the listing
        if pictures_res.data:
            # Use full_url (original quality) instead of thumbnail
            listing["pictures"] = [pic["full_url"] for pic in pictures_res.data if pic["full_url"]]
        else:
            # Fallback to thumbnail_url if no pictures found
            listing["pictures"] = [listing["thumbnail_url"]] if listing.get("thumbnail_url") else []

    return listings_res.data or []
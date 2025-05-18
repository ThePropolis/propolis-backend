from datetime import datetime, timezone
import logging
import os
from fastapi import APIRouter, HTTPException, Depends
import httpx
from supabase import create_client, Client
from typing import List, Dict, Any
import guesty_token

router = APIRouter()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
token_gen = guesty_token.GuestyToken()

@router.post("/api/guesty/listings/sync")
async def sync_guesty_listings(token: str = Depends(token_gen.get_guesty_token)):
    """
    Fetches all listings (with embedded pictures, address & integrations)
    and upserts into Supabase tables: jd_listing, jd_listing_pictures, 
    jd_listing_amenities, jd_listing_integrations.
    """
    listings_url = "https://open-api.guesty.com/v1/listings"
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    all_listings: List[Dict[str, Any]] = []
    limit, skip = 100, 0

    async with httpx.AsyncClient() as client:
        while True:
            resp = await client.get(listings_url, headers=headers, params={"limit": limit, "skip": skip})
            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise HTTPException(status_code=502, detail=f"Guesty fetch failed: {e}")
            payload = resp.json()
            batch, count = payload.get("results", []), payload.get("count", 0)
            if not batch:
                break
            all_listings.extend(batch)
            skip += len(batch)
            if skip >= count:
                break

    # Normalize and upsert main listings
    normalized = [normalize_guesty_record(raw) for raw in all_listings]
    sb_main = supabase.from_("jd_listing").upsert(normalized).execute()

    # Extract & upsert related tables from the already-embedded payload
    process_related_data(all_listings)

    return {
        "message": "Guesty listings synced",
        "total_fetched": len(all_listings),
        "supabase_inserted": getattr(sb_main, "data", []).__len__(),
    }

def process_related_data(listings: List[Dict[str, Any]]) -> None:
    # Pictures
    pics = []
    for lst in listings:
        lid = lst["_id"]
        for idx, pic in enumerate(lst.get("pictures", [])):
            pics.append({
                "listing_id": lid,
                "thumbnail_url": pic.get("thumbnail", ""),
                "full_url": pic.get("original", ""),
                "caption": pic.get("description", ""),
                "display_order": idx,
            })
    if pics:
        supabase.from_("jd_listing_pictures").upsert(pics).execute()

    # Integrations
    ints = []
    for lst in listings:
        lid = lst["_id"]
        for integ in lst.get("integrations", []):
            ints.append({
                "listing_id": lid,
                "platform": integ.get("platform", ""),
                "external_id": integ.get("oid") or integ.get("id", ""),
                "external_url": integ.get("externalUrl", ""),
            })
    if ints:
        supabase.from_("jd_listing_integrations").upsert(ints).execute()



def normalize_guesty_record(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transform a raw Guesty listing record into the format expected by our database.
    Includes all fields needed for the complete listing schema.
    """
    # Extract address information
    address = raw.get("address", {})
    
    # Extract cleaning status
    cleaning_status = raw.get("cleaningStatus", {})
    cleaning_status_value = "clean" if cleaning_status.get("value") == "clean" else "needs-cleaning"
    
    # Extract prices
    prices = raw.get("prices", {})
    
    # Extract terms
    terms = raw.get("terms", {})

    amenities = []
    for amenity in raw.get("amenities", []):
        amenities.append(amenity)
    
    return {
        # Primary ID
        "id": raw["_id"],
        
        # Basic Information
        "account_id": raw.get("accountId"),
        "created_at": raw.get("createdAt"),
        "last_updated_at": raw.get("lastUpdatedAt"),
        "imported_at": raw.get("importedAt"),
        "last_activity_at": raw.get("lastActivityAt"),
        "title": raw.get("title", ""),
        "nickname": raw.get("nickname", ""),
        "active": raw.get("active", True),  # Add active status
        
        # Property Details
        "property_type": raw.get("propertyType", ""),
        "room_type": raw.get("roomType", ""),
        "accommodates": raw.get("accommodates", 0),
        "bedrooms": raw.get("bedrooms", 0),
        "bathrooms": raw.get("bathrooms", 0),
        "area_square_feet": raw.get("areaSquareFeet", 0),
        "minimum_age": raw.get("minimumAge"),
        "amenities": amenities,
        
        # Cleaning Status
        "cleaning_status": cleaning_status_value,
        
        # Address
        "address_full": address.get("full", ""),
        "address_building_name": address.get("buildingName", ""),
        "address_city": address.get("city", ""),
        "address_state": address.get("state", ""),
        "address_neighborhood": address.get("neighborhood", ""),
        "address_latitude": address.get("lat"),
        "address_longitude": address.get("lng"),
        
        # Main Thumbnail
        "thumbnail_url": raw.get("picture", {}).get("thumbnail", ""),
        
        # Pricing
        "base_price": prices.get("basePrice", 0),
        "currency": prices.get("currency", "USD"),
        "weekly_price_factor": prices.get("weeklyPriceFactor", 1.0),
        "monthly_price_factor": prices.get("monthlyPriceFactor", 1.0),
        "extra_person_fee": prices.get("extraPersonFee", 0),
        "guests_included": prices.get("guestsIncludedInRegularFee", 1),
        "security_deposit_fee": prices.get("securityDepositFee", 0),
        
        # Stay Terms
        "min_nights": terms.get("minNights", 1),
        "max_nights": terms.get("maxNights", 365),
        
        # Description
        "description_summary": raw.get("publicDescription", {}).get("summary", ""),
        
        # Other Details
        "complex_id": raw.get("complexId"),
        "payment_provider_id": raw.get("paymentProviderId"),
        "tags": raw.get("tags", []),
        # "saas": raw.get("SaaS"),
        # "financials": raw.get("financials"),
        # "pms": raw.get("pms"),
        # "calendar_rules": raw.get("calendarRules"),
        # "receptionists_service": raw.get("receptionistsService"),
        # "check_in_instructions": raw.get("checkInInstructions"),
        # "business_model": raw.get("businessModel"),
        # "account_taxes": raw.get("accountTaxes"),
    }
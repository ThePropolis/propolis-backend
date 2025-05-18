from datetime import datetime, timedelta, timezone
import logging
import os
from fastapi import APIRouter, FastAPI, Depends, HTTPException
import httpx
from supabase import create_client, Client
from typing import List, Dict, Any
import guesty_token

router = APIRouter()
# --- Supabase client setup ---
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set")

CLIENT_ID = os.getenv("GUESTY_CLIENT_ID")
GUESTY_SECRET = os.getenv("GUESTY_SECRET")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
token_gen = guesty_token.GuestyToken()
# --- Your existing dependency to get Guesty token ---


@router.post("/api/guesty/listings/sync")
async def sync_guesty_listings(token: str = Depends(token_gen.get_guesty_token)):
    """
    Fetches all listings from Guesty (in pages of up to 100)
    and upserts them into the Supabase `listings` table.
    """
    listings_url = "https://open-api.guesty.com/v1/listings"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/json",
    }

    all_listings: List[Dict[str, Any]] = []
    limit = 100
    skip = 0

    async with httpx.AsyncClient() as client:
        while True:
            params = {"limit": limit, "skip": skip}
            resp = await client.get(listings_url, headers=headers, params=params)

            try:
                resp.raise_for_status()
            except httpx.HTTPStatusError as e:
                raise HTTPException(status_code=502, detail=f"Guesty fetch failed: {e}")

            payload = resp.json()
            batch = payload.get("results", [])
            count = payload.get("count", 0)

            if not batch:
                break

            all_listings.extend(batch)
            skip += len(batch)

            # stop if we've fetched them all
            if skip >= count:
                break

    # Upsert into Supabase
    normalized_listings = list(map(normalize_guesty_record, all_listings))
    sb_resp = supabase.from_("listings").upsert(normalized_listings).execute()
    if sb_resp.error:
        raise HTTPException(status_code=500, detail=f"Supabase error: {sb_resp.error.message}")

    return {
        "message": "Guesty listings synced",
        "total_fetched": len(all_listings),
        "supabase_inserted": sb_resp.data,  # or len(sb_resp.data) depending on your needs
    }



def normalize_guesty_record(raw: Dict[str, Any]) -> Dict[str, Any]:
    return {
      "id": raw["_id"],
      "account_id": raw["accountId"],
      "created_at": raw["createdAt"],
      "last_updated_at": raw.get("lastUpdatedAt"),
      "imported_at": raw.get("importedAt"),
      "last_activity_at": raw.get("lastActivityAt"),
      "title": raw.get("title"),
      "nickname": raw.get("nickname"),
      "property_type": raw.get("propertyType"),
      "room_type": raw.get("roomType"),
      "accommodates": raw.get("accommodates"),
      "bedrooms": raw.get("bedrooms"),
      "bathrooms": raw.get("bathrooms"),
      "area_square_feet": raw.get("areaSquareFeet"),
      "minimum_age": raw.get("minimumAge"),
      "complex_id": raw.get("complexId"),
      "payment_provider_id": raw.get("paymentProviderId"),
      "tags": raw.get("tags", []),
      "amenities": raw.get("amenities", []),
      "amenities_not_included": raw.get("amenitiesNotIncluded", []),
      "saas": raw.get("SaaS"),
      "financials": raw.get("financials"),
      "cleaning_status": raw.get("cleaningStatus"),
      "terms": raw.get("terms"),
      "prices": raw.get("prices"),
      "public_description": raw.get("publicDescription"),
      "pms": raw.get("pms"),
      "calendar_rules": raw.get("calendarRules"),
      "receptionists_service": raw.get("receptionistsService"),
      "check_in_instructions": raw.get("checkInInstructions"),
      "business_model": raw.get("businessModel"),
      "account_taxes": raw.get("accountTaxes"),
    }

import logging
from typing import Optional
logging.basicConfig(level=logging.INFO)
logging.info("FastAPI app is starting up...")

from fastapi import FastAPI, Depends, HTTPException, Request
import httpx
import os
from dotenv import load_dotenv

from auth import router as auth_router
from reservations import router as reservation_router
from scraper.listings import router as listing_router
from properties import router as property_router
from doorloop import router as doorloop_router
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta, timezone
import logging
import guesty_token

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s ▶ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("app")
token = guesty_token.GuestyToken()
load_dotenv()
CLIENT_ID = os.getenv("GUESTY_CLIENT_ID")
GUESTY_SECRET = os.getenv("GUESTY_SECRET")
if not CLIENT_ID or not GUESTY_SECRET:
    raise ValueError("GUESTY_CLIENT_ID and GUESTY_SECRET environment variables must be set")

app = FastAPI(
    title="Guesty Integration",
    description="Proxy endpoint for Guesty listings",
    version="0.1.0",
)


@app.middleware("http")
async def log_request_scheme(request: Request, call_next):
    print(f"🔍 SCHEME: {request.url.scheme} — FULL URL: {request.url}")
    response = await call_next(request)
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174","https://propolis-frontend.vercel.app"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(reservation_router)
app.include_router(listing_router)
app.include_router(property_router)
app.include_router(doorloop_router)



 
@app.get("/")
async def welcome():
    await token.get_guesty_token()
    return "Hello, welcome to the Propolis Backend"

@app.get("/api/guesty/listings")
async def list_guesty_listings(token: str = Depends(token.get_guesty_token)):

    listings_url = "https://open-api.guesty.com/v1/listings"
    headers = {
        "Authorization": f"Bearer {token}",
        "accept":        "application/json",
    }
    params = {"limit": 1}
    async with httpx.AsyncClient() as client:
        resp = await client.get(listings_url, headers=headers, params=params)
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail="Failed to fetch listings") from e
    print(resp.json())
    return resp.json()

@app.get("/api/guesty/reservations")
async def list_guesty_listings(token: str = Depends(token.get_guesty_token)):
    listings_url = "https://open-api.guesty.com/v1/reservations"
    headers = {
        "Authorization": f"Bearer {token}",
        "accept":        "application/json",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(listings_url, headers=headers)
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail="Failed to fetch listings") from e
    return resp.json()

@app.get("/api/guesty/users")
async def list_guesty_users(token: str = Depends(token.get_guesty_token)):
    users_url = "https://open-api.guesty.com/v1/users"
    headers = {
        "Authorization": f"Bearer {token}",
        "accept":        "application/json",
    }
    async with httpx.AsyncClient() as client:
        resp = await client.get(users_url, headers=headers)
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail="Failed to fetch users") from e
    return resp.json()

@app.get("/api/guesty/revenue")
async def get_guesty_revenue(
    start_date: str = None, 
    end_date: str = None,
    token: str = Depends(token.get_guesty_token)
):
    """Get revenue data from Guesty reservations with financial details."""
    revenue_url = "https://open-api.guesty.com/v1/reservations"
    
    # Financial fields to include in the response (matching PHP implementation)
    financial_fields = [
        "money.hostPayout",
        "money.hostPayoutUsd", 
        "money.totalPaid",
        "money.balanceDue",
        "money.invoiceItems",
        "money.totalTaxes",
        "money.hostServiceFee",
        "money.hostServiceFeeTax",
        "money.hostServiceFeeIncTax",
        "money.payments.status",
        "money.payments.amount",
        "money.payments.currency",
        "money.payments.paidAt",
        "money.currency",
        "confirmationCode",
        "checkIn",
        "checkOut",
        "nightsCount",
        "guestsCount",
        "listing._id",
        "listing.title",
        "listing.nickname",
        "guest.fullName",
        "createdAt",
        "confirmedAt",
        "status"
    ]
    
    headers = {
        "Authorization": f"Bearer {token}",
        "accept": "application/json",
    }
    
    # Try different filtering strategies (matching PHP format)
    filtering_strategies = []
    
    if start_date and end_date:
        # Strategy 1: Filter by check-in date with confirmed status
        strategy1 = [
            {
                "field": "checkIn",
                "operator": "$gte", 
                "value": start_date
            },
            {
                "field": "checkIn",
                "operator": "$lte", 
                "value": end_date
            },
            {
                "field": "status",
                "operator": "$eq", 
                "value": "confirmed"
            }
        ]
        filtering_strategies.append(("checkIn_confirmed", strategy1))
        
        # Strategy 2: Filter reservations that overlap with the date range (confirmed only)
        strategy2 = [
            {
                "field": "checkIn",
                "operator": "$lte", 
                "value": end_date
            },
            {
                "field": "checkOut",
                "operator": "$gte", 
                "value": start_date
            },
            {
                "field": "status",
                "operator": "$eq", 
                "value": "confirmed"
            }
        ]
        filtering_strategies.append(("overlap_confirmed", strategy2))
        
        # Strategy 3: Filter by check-out date with confirmed status
        strategy3 = [
            {
                "field": "checkOut",
                "operator": "$gte", 
                "value": start_date
            },
            {
                "field": "checkOut",
                "operator": "$lte", 
                "value": end_date
            },
            {
                "field": "status",
                "operator": "$eq", 
                "value": "confirmed"
            }
        ]
        filtering_strategies.append(("checkOut_confirmed", strategy3))
    
    all_reservations = []
    successful_strategy = None
    
    async with httpx.AsyncClient() as client:
        # Try each filtering strategy
        for strategy_name, date_filter in filtering_strategies:
            try:
                # Convert to proper JSON string (matching PHP format)
                import json
                
                print(f"DEBUG: Trying strategy: {strategy_name}")
                print(f"DEBUG: Using date filter: {json.dumps(date_filter)}")
                print(f"DEBUG: Start date: {start_date}, End date: {end_date}")
                
                # Fetch all pages for this strategy
                skip = 0
                limit = 100
                strategy_reservations = []
                
                while True:
                    params = {
                        "fields": " ".join(financial_fields),
                        "limit": limit,
                        "skip": skip,
                        "sort": "-createdAt",
                        "filters": json.dumps(date_filter)
                    }
                    
                    resp = await client.get(revenue_url, headers=headers, params=params)
                    resp.raise_for_status()
                    data = resp.json()
                    
                    batch_reservations = data.get('results', [])
                    if not batch_reservations:
                        break
                    
                    strategy_reservations.extend(batch_reservations)
                    print(f"DEBUG: Strategy {strategy_name} - Fetched {len(batch_reservations)} reservations (total: {len(strategy_reservations)})")
                    
                    # If we got fewer than the limit, we've reached the end
                    if len(batch_reservations) < limit:
                        break
                    
                    skip += limit
                
                print(f"DEBUG: Strategy {strategy_name} returned {len(strategy_reservations)} total reservations")
                
                # If we got results, use this strategy
                if len(strategy_reservations) > 0:
                    all_reservations = strategy_reservations
                    successful_strategy = strategy_name
                    print(f"DEBUG: Using strategy {strategy_name} with {len(all_reservations)} reservations")
                    break
                else:
                    print(f"DEBUG: Strategy {strategy_name} returned no results, trying next...")
                    
            except Exception as e:
                print(f"DEBUG: Strategy {strategy_name} failed: {str(e)}")
                continue
        else:
            # If no strategies worked, try without date filter but with pagination
            print("DEBUG: All date filtering strategies failed, trying without date filter...")
            
            skip = 0
            limit = 100
            
            while True:
                params = {
                    "fields": " ".join(financial_fields),
                    "limit": limit,
                    "skip": skip,
                    "sort": "-createdAt"
                }
                
                resp = await client.get(revenue_url, headers=headers, params=params)
                resp.raise_for_status()
                data = resp.json()
                
                batch_reservations = data.get('results', [])
                if not batch_reservations:
                    break
                
                all_reservations.extend(batch_reservations)
                
                if len(batch_reservations) < limit:
                    break
                
                skip += limit
                
                # Limit to reasonable number for fallback
                if len(all_reservations) >= 1000:
                    break
            
            successful_strategy = "no_filter_fallback"
    
    try:
        print(f"DEBUG: Final strategy used: {successful_strategy}")
        print(f"DEBUG: Total reservations fetched: {len(all_reservations)}")
        
        # Calculate summary statistics with improved revenue calculation
        total_revenue = 0
        total_host_payout = 0
        total_paid = 0
        total_due = 0
        reservation_count = 0
        revenue_by_currency = {}
        
        for reservation in all_reservations:
            print(f"DEBUG: Processing reservation: {reservation.get('confirmationCode', 'no_code')}")
            print(f"DEBUG: Reservation status: {reservation.get('status', 'no_status')}")
            print(f"DEBUG: Check-in date: {reservation.get('checkIn', 'no_date')}")
            print(f"DEBUG: Check-out date: {reservation.get('checkOut', 'no_date')}")
            
            # Skip non-confirmed reservations if we're using fallback strategy
            if successful_strategy == "no_filter_fallback" and reservation.get('status') != 'confirmed':
                continue
            
            if "money" in reservation:
                money = reservation["money"]
                
                # Use multiple revenue sources for better accuracy
                host_payout_usd = money.get("hostPayoutUsd", 0) or 0
                host_payout = money.get("hostPayout", 0) or 0
                total_paid_amount = money.get("totalPaid", 0) or 0
                balance_due = money.get("balanceDue", 0) or 0
                currency = money.get("currency", "USD")
                
                print(f"DEBUG: Host payout USD: {host_payout_usd}, Host payout: {host_payout}, Total paid: {total_paid_amount}, Balance due: {balance_due}, Currency: {currency}")
                
                # Prefer USD amounts, fall back to base amounts
                revenue_amount = host_payout_usd if host_payout_usd > 0 else host_payout
                
                # If we still don't have host payout, use total paid as gross revenue
                if revenue_amount <= 0:
                    revenue_amount = total_paid_amount
                
                total_revenue += revenue_amount
                total_host_payout += host_payout_usd
                total_paid += total_paid_amount
                total_due += balance_due
                reservation_count += 1
                
                # Track revenue by currency
                if currency not in revenue_by_currency:
                    revenue_by_currency[currency] = 0
                revenue_by_currency[currency] += revenue_amount
        
        # Create comprehensive response
        response_data = {
            "results": all_reservations,
            "count": len(all_reservations),
            "summary": {
                "total_revenue_usd": round(total_revenue, 2),
                "total_host_payout_usd": round(total_host_payout, 2),
                "total_paid_usd": round(total_paid, 2),
                "total_balance_due_usd": round(total_due, 2),
                "reservation_count": reservation_count,
                "revenue_by_currency": revenue_by_currency,
                "date_range": {
                    "start_date": start_date,
                    "end_date": end_date
                } if start_date and end_date else None,
                "debug_info": {
                    "strategy_used": successful_strategy,
                    "total_reservations_fetched": len(all_reservations),
                    "filters_applied": bool(start_date and end_date)
                }
            }
        }
        
        return response_data
        
    except Exception as e:
        print(f"DEBUG: Error in revenue calculation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error calculating revenue: {str(e)}")
    


@app.get("/occupancy-rate")
async def get_occupancy_rate(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    token: str = Depends(token.get_guesty_token)
):
    """
    Calculate occupancy rate: (occupied units / total units) * 100
    
    Parameters:
    - date_from: Start date (YYYY-MM-DD) - defaults to current month start
    - date_to: End date (YYYY-MM-DD) - defaults to current month end
    """
    
    if not token:
        raise HTTPException(status_code=500, detail="Guesty API token not configured")
    
    # Set default date range to current month if not provided
    if not date_from or not date_to:
        today = datetime.now()
        date_from = today.replace(day=1).strftime("%Y-%m-%d")
        # Last day of current month
        next_month = today.replace(day=28) + timedelta(days=4)
        date_to = (next_month - timedelta(days=next_month.day)).strftime("%Y-%m-%d")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    try:
        # Get occupied units (properties with confirmed reservations in date range)
        occupied_units = await get_occupied_units(headers, date_from, date_to)
        
        # Get total units (all active properties)
        total_units = await get_total_units(headers)
        
        if total_units == 0:
            occupancy_rate = 0.0
        else:
            occupancy_rate = (occupied_units / total_units) * 100
        
        return {
            "occupancy_rate": round(occupancy_rate, 2),
            "occupied_units": occupied_units,
            "total_units": total_units,
            "date_from": date_from,
            "date_to": date_to,
            "message": f"Occupancy rate: {occupancy_rate:.2f}%"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to calculate occupancy: {str(e)}")

async def get_occupied_units(
        headers: dict, 
        date_from: str, 
        date_to: str,
        token: str = Depends(token.get_guesty_token)
    ):
    """
    Get count of unique properties that have confirmed reservations in the date range
    """
    params = {
        "fields": "listingId",
        "limit": 100,
        "sort": "_id"
    }
    
    # Filter for confirmed reservations in date range (matching PHP format)
    filters = [
        {"field": "status", "operator": "$eq", "value": "confirmed"},
        {"field": "checkIn", "operator": "$gte", "value": date_from},
        {"field": "checkIn", "operator": "$lte", "value": date_to}
    ]
    
    import json
    params["filters"] = json.dumps(filters)
    
    occupied_property_ids = set()
    skip = 0
    
    async with httpx.AsyncClient() as client:
        while True:
            params["skip"] = skip
            
            response = await client.get(
                f"https://open-api.guesty.com/v1/reservations",
                params=params,
                headers=headers,
                timeout=30.0
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Guesty API error: {response.text}"
                )
            
            data = response.json()
            reservations = data.get("results", [])
            
            if not reservations:
                break
            
            # Collect unique property IDs
            for reservation in reservations:
                listing_id = reservation.get("listingId")
                if listing_id:
                    occupied_property_ids.add(listing_id)
            
            if len(reservations) < 100:
                break
                
            skip += 100
    
    return len(occupied_property_ids)

async def get_total_units(
        headers: dict
    ):
    """
    Get total count of active properties/units
    """
    params = {
        "fields": "_id",
        "filters": '[{"operator": "$eq", "field": "active", "value": true}]',
        "limit": 100,
        "sort": "_id"
    }
    
    total_units = 0
    skip = 0
    
    async with httpx.AsyncClient() as client:
        while True:
            params["skip"] = skip
            
            response = await client.get(
                f"https://open-api.guesty.com/v1/listings",
                params=params,
                headers=headers,
                timeout=30.0
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Guesty API error: {response.text}"
                )
            
            data = response.json()
            listings = data.get("results", [])
            
            if not listings:
                break
            
            total_units += len(listings)
            
            if len(listings) < 100:
                break
                
            skip += 100
    
    return total_units

@app.get("/occupancy-rate/current-month")
async def get_current_month_occupancy():
    """Get occupancy rate for current month"""
    return await get_occupancy_rate()

@app.get("/occupancy-rate/custom")
async def get_custom_occupancy(date_from: str, date_to: str):
    """Get occupancy rate for custom date range"""
    return await get_occupancy_rate(date_from, date_to)

@app.post("/debug/clear-tables")
async def clear_database_tables(tables: str = "pictures"):
    """
    Clear specified database tables for debugging.
    tables parameter can be: 'pictures', 'listings', 'all'
    """
    try:
        cleared_tables = []
        
        if tables in ["pictures", "all"]:
            # Clear pictures table
            result = supabase.from_("jd_listing_pictures").delete().neq("listing_id", "").execute()
            cleared_tables.append(f"jd_listing_pictures ({len(result.data)} rows deleted)")
        
        if tables in ["listings", "all"]:
            # Clear listings table
            result = supabase.from_("jd_listing").delete().neq("id", "").execute()
            cleared_tables.append(f"jd_listing ({len(result.data)} rows deleted)")
        
        if tables == "all":
            # Also clear related tables
            supabase.from_("jd_listing_integrations").delete().neq("listing_id", "").execute()
            cleared_tables.append("jd_listing_integrations")
        
        return {
            "message": "Tables cleared successfully",
            "cleared_tables": cleared_tables,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to clear tables: {str(e)}")

@app.get("/debug/database-state")
async def debug_database_state():
    """Debug endpoint to check database state for listings and pictures"""
    try:
        # Check listings
        listings_res = supabase.from_("jd_listing").select("id, title").execute()
        listings_count = len(listings_res.data) if listings_res.data else 0
        
        # Check pictures
        pictures_res = supabase.from_("jd_listing_pictures").select("listing_id, full_url, thumbnail_url").execute()
        pictures_count = len(pictures_res.data) if pictures_res.data else 0
        
        # Count unique listing IDs in pictures
        unique_listing_ids = set()
        pictures_by_listing = {}
        
        if pictures_res.data:
            for pic in pictures_res.data:
                listing_id = pic["listing_id"]
                unique_listing_ids.add(listing_id)
                if listing_id not in pictures_by_listing:
                    pictures_by_listing[listing_id] = 0
                pictures_by_listing[listing_id] += 1
        
        return {
            "listings_count": listings_count,
            "pictures_count": pictures_count,
            "unique_listing_ids_in_pictures": len(unique_listing_ids),
            "pictures_per_listing": pictures_by_listing,
            "sample_listings": listings_res.data[:5] if listings_res.data else [],
            "sample_pictures": pictures_res.data[:10] if pictures_res.data else []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Database debug failed: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


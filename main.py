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
    
    params = {
        "fields": " ".join(financial_fields),
        "limit": 100,
        "sort": "-createdAt"
    }
    
    # Try different filtering strategies (matching PHP format)
    filtering_strategies = []
    
    if start_date and end_date:
        # Strategy 1: Filter by check-in date (matching PHP checkIn field)
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
            }
        ]
        filtering_strategies.append(("checkIn_range", strategy1))
        
        # Strategy 2: Filter by check-out date (matching PHP checkOut field)  
        strategy2 = [
            {
                "field": "checkOut",
                "operator": "$gte", 
                "value": start_date
            },
            {
                "field": "checkOut",
                "operator": "$lte", 
                "value": end_date
            }
        ]
        filtering_strategies.append(("checkOut_range", strategy2))
        
        # Strategy 3: Filter reservations that overlap with the date range
        strategy3 = [
            {
                "field": "checkIn",
                "operator": "$lte", 
                "value": end_date
            },
            {
                "field": "checkOut",
                "operator": "$gte", 
                "value": start_date
            }
        ]
        filtering_strategies.append(("overlap_range", strategy3))
        
        # Strategy 4: Add status filter (matching PHP approach)
        strategy4 = [
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
        filtering_strategies.append(("checkIn_with_status", strategy4))
    
    async with httpx.AsyncClient() as client:
        # Try each filtering strategy
        for strategy_name, date_filter in filtering_strategies:
            try:
                # Convert to proper JSON string (matching PHP format)
                import json
                params["filters"] = json.dumps(date_filter)
                
                print(f"DEBUG: Trying strategy: {strategy_name}")
                print(f"DEBUG: Using date filter: {params['filters']}")
                print(f"DEBUG: Start date: {start_date}, End date: {end_date}")
                
                resp = await client.get(revenue_url, headers=headers, params=params)
                resp.raise_for_status()
                data = resp.json()
                
                print(f"DEBUG: Response status: {resp.status_code}")
                print(f"DEBUG: Results count: {len(data.get('results', []))}")
                
                # If we got results, use this strategy
                if data.get("results") and len(data["results"]) > 0:
                    print(f"DEBUG: Strategy {strategy_name} returned {len(data['results'])} results")
                    break
                else:
                    print(f"DEBUG: Strategy {strategy_name} returned no results, trying next...")
                    
            except Exception as e:
                print(f"DEBUG: Strategy {strategy_name} failed: {str(e)}")
                continue
        else:
            # If no strategies worked, try without date filter
            print("DEBUG: All date filtering strategies failed, trying without date filter...")
            if "filters" in params:
                del params["filters"]
            resp = await client.get(revenue_url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
    
    try:
        print(f"DEBUG: Final response status: {resp.status_code}")
        print(f"DEBUG: Final response data keys: {list(data.keys()) if isinstance(data, dict) else 'not_dict'}")
        print(f"DEBUG: Final results count: {len(data.get('results', []))}")
        
        # Calculate summary statistics
        total_revenue = 0
        total_paid = 0
        total_due = 0
        reservation_count = 0
        
        if "results" in data:
            for reservation in data["results"]:
                print(f"DEBUG: Processing reservation: {reservation.get('confirmationCode', 'no_code')}")
                print(f"DEBUG: Reservation status: {reservation.get('status', 'no_status')}")
                print(f"DEBUG: Check-in date: {reservation.get('checkIn', 'no_date')}")
                print(f"DEBUG: Check-out date: {reservation.get('checkOut', 'no_date')}")
                
                if "money" in reservation:
                    money = reservation["money"]
                    host_payout = money.get("hostPayoutUsd", 0)
                    total_paid_amount = money.get("totalPaid", 0)
                    balance_due = money.get("balanceDue", 0)
                    
                    print(f"DEBUG: Host payout: {host_payout}, Total paid: {total_paid_amount}, Balance due: {balance_due}")
                    
                    total_revenue += host_payout
                    total_paid += total_paid_amount
                    total_due += balance_due
                    reservation_count += 1
        
        # Add summary to response
        response_data = data
        response_data["summary"] = {
            "total_revenue_usd": total_revenue,
            "total_paid_usd": total_paid,
            "total_balance_due_usd": total_due,
            "reservation_count": reservation_count,
            "date_range": {
                "start_date": start_date,
                "end_date": end_date
            } if start_date and end_date else None,
            "debug_info": {
                "filters_applied": bool(start_date and end_date),
                "filter_string": params.get("filters", "none"),
                "strategies_tried": [name for name, _ in filtering_strategies] if start_date and end_date else []
            }
        }
        
        return response_data
        
    except httpx.HTTPStatusError as e:
        print(f"DEBUG: HTTP Error {e.response.status_code}: {e.response.text}")
        raise HTTPException(status_code=502, detail="Failed to fetch revenue data") from e
    


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

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


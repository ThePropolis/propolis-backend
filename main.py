import logging
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
    
    # Financial fields to include in the response
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
        "checkInDateLocalized",
        "checkOutDateLocalized",
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
    
    # Add date filters if provided
    if start_date and end_date:
        date_filter = [
            {
                "operator": "$between",
                "field": "checkOutDateLocalized", 
                "from": start_date,
                "to": end_date
            },
            {
                "operator": "$eq",
                "field": "status",
                "value": "confirmed"
            }
        ]
        params["filters"] = str(date_filter).replace("'", '"')
    
    async with httpx.AsyncClient() as client:
        resp = await client.get(revenue_url, headers=headers, params=params)
    
    try:
        resp.raise_for_status()
        data = resp.json()
        
        # Calculate summary statistics
        total_revenue = 0
        total_paid = 0
        total_due = 0
        reservation_count = 0
        
        if "results" in data:
            for reservation in data["results"]:
                if "money" in reservation:
                    money = reservation["money"]
                    total_revenue += money.get("hostPayoutUsd", 0)
                    total_paid += money.get("totalPaid", 0) 
                    total_due += money.get("balanceDue", 0)
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
            } if start_date and end_date else None
        }
        
        return response_data
        
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail="Failed to fetch revenue data") from e

from fastapi import FastAPI, Depends, HTTPException
import httpx
import os
from dotenv import load_dotenv
from auth import router as auth_router
from reservations import router as reservation_router
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta, timezone

# Load environment variables
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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(reservation_router)
# Module‐level cache
_token_cache = {
    "access_token": None,
    "expires_at": datetime.min.replace(tzinfo=timezone.utc)
} 

async def get_guesty_token() -> str:
    """
    Return a cached token if still valid, otherwise fetch a new one
    and update the cache.
    """
    now = datetime.now(timezone.utc)
    if _token_cache["access_token"] and now < _token_cache["expires_at"]:
        return _token_cache["access_token"]

    token_url = "https://open-api.guesty.com/oauth2/token"
    data = {
        "grant_type":    "client_credentials",
        "scope":         "open-api",
        "client_id":     CLIENT_ID,
        "client_secret": GUESTY_SECRET,
    }
    headers = {"accept": "application/json"}

    async with httpx.AsyncClient() as client:
        resp = await client.post(token_url, data=data, headers=headers)
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail="Failed to fetch Guesty token") from e

    body = resp.json()
    access_token = body.get("access_token")
    expires_in = body.get("expires_in", 7200)  # seconds

    if not access_token:
        raise HTTPException(status_code=502, detail="No access_token in Guesty response")

    # Cache it, subtracting a small safety window (e.g., 60s)
    _token_cache["access_token"] = access_token
    _token_cache["expires_at"] = now + timedelta(seconds=expires_in - 60)
    return access_token

@app.get("/")
async def welcome():
    return "Hello, welcome to the Propolis Backend"

@app.get("/api/guesty/listings")
async def list_guesty_listings(token: str = Depends(get_guesty_token)):
    listings_url = "https://open-api.guesty.com/v1/listings"
    headers = {
        "Authorization": f"Bearer {token}",
        "accept":        "application/json",
    }
    params = {"limit": 100}
    async with httpx.AsyncClient() as client:
        resp = await client.get(listings_url, headers=headers, params=params)
    try:
        resp.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(status_code=502, detail="Failed to fetch listings") from e
    return resp.json()

@app.get("/api/guesty/reservations")
async def list_guesty_listings(token: str = Depends(get_guesty_token)):
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
async def list_guesty_users(token: str = Depends(get_guesty_token)):
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

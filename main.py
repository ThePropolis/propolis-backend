from fastapi import FastAPI, Depends, HTTPException
import httpx
import os
from dotenv import load_dotenv
from auth import router as auth_router
from fastapi.middleware.cors import CORSMiddleware
# Load environment variables
load_dotenv()

# Get credentials from environment variables
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
    allow_origins=["http://localhost:5173", "http://locahost:5174"],  # Svelte frontend
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(auth_router)

async def get_guesty_token() -> str:
    """
    Exchange CLIENT_ID & GUESTY_SECRET for a Bearer token.
    """
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

    return resp.json().get("access_token")

@app.get("/")
async def welcome():
    return "Hello, welcome to the Propolis Backend"

@app.get("/guesty/listings")
async def list_guesty_listings(token: str = Depends(get_guesty_token)):
    """
    Fetch all listings from Guesty and return the raw JSON.
    """
    listings_url = "https://open-api.guesty.com/v1/listings"
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

@app.get("/guesty/users")
async def list_guesty_users(token: str = Depends(get_guesty_token)):
    """
    Fetch all users from Guesty and return the raw JSON.
    """
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
    
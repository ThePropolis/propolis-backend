import logging
from typing import Optional
logging.basicConfig(level=logging.INFO)
logging.info("FastAPI app is starting up...")

from fastapi import FastAPI, Depends, HTTPException, Request
import httpx
import os
from dotenv import load_dotenv
load_dotenv()

# Core imports (always available)
from auth import router as auth_router, require_role, get_current_user_payload
from properties import router as properties_router
from admin import router as admin_router
from facilities import router as facilities_router
from inventory import router as inventory_router
from portfolio import router as portfolio_router
from listings import router as listings_router

# Optional integrations - won't fail if API keys are missing
doorloop_router = None
jurny_router = None
longterm_unittype_filter_router = None

try:
    from doorloop import router as doorloop_router
except (ValueError, ImportError) as e:
    print(f"⚠️ Doorloop integration disabled: {e}")

try:
    from jurny import router as jurny_router
except (ValueError, ImportError) as e:
    print(f"⚠️ Jurny integration disabled: {e}")

try:
    from longterm_unittype_filter import router as longterm_unittype_filter_router
except (ValueError, ImportError) as e:
    print(f"⚠️ Longterm filter integration disabled: {e}")

from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta, timezone
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s ▶ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("app")
app = FastAPI(
    title="Propolis Backend",
    description="Property management backend with Doorloop integration",
    version="0.1.0",
)


@app.middleware("http")
async def log_request_scheme(request: Request, call_next):
    print(f"🔍 SCHEME: {request.url.scheme} — FULL URL: {request.url}")
    # Handle OPTIONS preflight requests explicitly
    if request.method == "OPTIONS":
        response = await call_next(request)
        response.headers["Access-Control-Allow-Origin"] = request.headers.get("Origin", "*")
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS, PATCH"
        response.headers["Access-Control-Allow-Headers"] = "*"
        response.headers["Access-Control-Allow-Credentials"] = "true"
        return response
    response = await call_next(request)
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "https://propolis-frontend-new.vercel.app", "https://propolis-dashboard.com", "https://propolis-frontend.vercel.app"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
)


app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(facilities_router)
app.include_router(inventory_router)
app.include_router(portfolio_router)
app.include_router(listings_router)

# Data-source routers were public before this refactor and many frontend
# callsites don't yet send Authorization headers. Keep them open at the router
# level so the existing Dashboard / Properties pages keep working. Per-endpoint
# gating (e.g. /api/doorloop/facilities requires owner+operator) still applies,
# and the frontend sidebar + nav guard prevent non-owners from reaching these
# pages in the first place.
app.include_router(properties_router)
if doorloop_router:
    app.include_router(doorloop_router)
if jurny_router:
    app.include_router(jurny_router)
if longterm_unittype_filter_router:
    app.include_router(longterm_unittype_filter_router)



 
@app.get("/")
async def welcome():
    return "Hello, welcome to the Propolis Backend"


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


import logging
from typing import Optional
logging.basicConfig(level=logging.INFO)
logging.info("FastAPI app is starting up...")

from fastapi import FastAPI, Depends, HTTPException, Request
import httpx
import os
from dotenv import load_dotenv

from auth import router as auth_router
from doorloop import router as doorloop_router
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta, timezone
import logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s ▶ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("app")
load_dotenv()

app = FastAPI(
    title="Propolis Backend",
    description="Property management backend with Doorloop integration",
    version="0.1.0",
)


@app.middleware("http")
async def log_request_scheme(request: Request, call_next):
    print(f"🔍 SCHEME: {request.url.scheme} — FULL URL: {request.url}")
    response = await call_next(request)
    return response

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174","https://propolis-frontend.vercel.app", "https://propolis-dashboard.com"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(doorloop_router)



 
@app.get("/")
async def welcome():
    return "Hello, welcome to the Propolis Backend"









@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.now().isoformat()}


from fastapi import FastAPI, Depends, HTTPException
import httpx
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import logging
from database import supabase

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s ▶ %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("app")

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


class GuestyToken:
    
    async def get_guesty_token(self) -> str:
        """
        Return a cached token from Supabase if still valid, otherwise fetch a new one
        and update the cache in Supabase.
        """
        now = datetime.now(timezone.utc)
        logger.info("Checking Guesty token validity...")
        
        # Check if we have a valid cached token in Supabase
        try:
            result = supabase.from_("jd_guesty_tokens").select("*").eq("id", 1).single().execute()
            if result.data:
                token_data = result.data
                expires_at = datetime.fromisoformat(token_data["expires_at"].replace("Z", "+00:00"))
                
                if token_data["access_token"] and now < expires_at:
                    logger.info("Using cached Guesty token from Supabase")
                    return token_data["access_token"]
        except Exception as e:
            logger.info(f"No cached token found in Supabase or error retrieving: {e}")
        
        logger.info("Fetching new Guesty token...")
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
            logger.error(f"Failed to fetch Guesty token: {e.response.status_code} - {e.response.text}")
            raise HTTPException(status_code=502, detail="Failed to fetch Guesty token") from e

        body = resp.json()
        access_token = body.get("access_token")
        expires_in = body.get("expires_in", 86400)  # seconds

        if not access_token:
            raise HTTPException(status_code=502, detail="No access_token in Guesty response")

        # Cache it in Supabase, subtracting a safety window (30 minutes)
        expires_at = now + timedelta(seconds=expires_in - 1800)
        
        try:
            # Upsert the token data (insert or update if id=1 exists)
            supabase.from_("jd_guesty_tokens").upsert({
                "id": 1,
                "access_token": access_token,
                "expires_at": expires_at.isoformat(),
                "created_at": now.isoformat(),
                "updated_at": now.isoformat()
            }).execute()
            logger.info(f"Successfully cached new Guesty token in Supabase, expires at: {expires_at}")
        except Exception as e:
            logger.error(f"Failed to cache token in Supabase: {e}")
            # Continue anyway, as we still have the token to return
        
        return access_token
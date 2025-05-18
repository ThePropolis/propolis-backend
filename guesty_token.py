from fastapi import FastAPI, Depends, HTTPException
import httpx
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta, timezone
import logging

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
    _token_cache = {
        "access_token": None,
        "expires_at": datetime.min.replace(tzinfo=timezone.utc)
    } 

    async def get_guesty_token(self) -> str:
        """
        Return a cached token if still valid, otherwise fetch a new one
        and update the cache.
        """
        now = datetime.now(timezone.utc)
        logging.info("TESTINGS SSSS")
        if self._token_cache["access_token"] and now < self._token_cache["expires_at"]:
            return self._token_cache["access_token"]

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
        expires_in = body.get("expires_in", 8640)  # seconds

        if not access_token:
            raise HTTPException(status_code=502, detail="No access_token in Guesty response")

        # Cache it, subtracting a small safety window (e.g., 60s)
        self._token_cache["access_token"] = access_token
        self._token_cache["expires_at"] = now + timedelta(seconds=expires_in - 1800)
        return access_token
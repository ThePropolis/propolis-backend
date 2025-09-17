from fastapi import FastAPI, Depends, HTTPException
import httpx
import os
import asyncio
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
    def __init__(self):
        self._last_token_request = None
        self._token_request_cooldown = 60  # seconds - minimum time between token requests
        self._circuit_breaker_failures = 0
        self._circuit_breaker_threshold = 3  # Open circuit after 3 consecutive failures
        self._circuit_breaker_timeout = 300  # 5 minutes before trying again
        self._circuit_breaker_last_failure = None
    
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
                elif token_data["access_token"]:
                    # Token is expired, but check if it's not too old (within 1 hour)
                    time_since_expiry = (now - expires_at).total_seconds()
                    if time_since_expiry < 3600:  # 1 hour
                        logger.warning(f"Using expired token (expired {time_since_expiry:.0f} seconds ago) to avoid rate limiting")
                        return token_data["access_token"]
        except Exception as e:
            logger.info(f"No cached token found in Supabase or error retrieving: {e}")
        
        # Circuit breaker check
        if self._circuit_breaker_failures >= self._circuit_breaker_threshold:
            if self._circuit_breaker_last_failure:
                time_since_last_failure = (now - self._circuit_breaker_last_failure).total_seconds()
                if time_since_last_failure < self._circuit_breaker_timeout:
                    remaining_timeout = self._circuit_breaker_timeout - time_since_last_failure
                    logger.error(f"Circuit breaker OPEN. Guesty API unavailable. Retry in {remaining_timeout:.1f} seconds.")
                    raise HTTPException(
                        status_code=503, 
                        detail=f"Guesty API temporarily unavailable due to rate limiting. Service will retry in {remaining_timeout:.1f} seconds."
                    )
                else:
                    # Reset circuit breaker for retry
                    logger.info("Circuit breaker reset - attempting to reconnect to Guesty API")
                    self._circuit_breaker_failures = 0
                    self._circuit_breaker_last_failure = None
            else:
                logger.error("Circuit breaker OPEN. Guesty API unavailable.")
                raise HTTPException(
                    status_code=503, 
                    detail="Guesty API temporarily unavailable due to rate limiting."
                )

        # Rate limiting check - prevent too frequent token requests
        if self._last_token_request:
            time_since_last_request = (now - self._last_token_request).total_seconds()
            if time_since_last_request < self._token_request_cooldown:
                remaining_cooldown = self._token_request_cooldown - time_since_last_request
                logger.warning(f"Token request too soon. Waiting {remaining_cooldown:.1f} seconds...")
                raise HTTPException(
                    status_code=429, 
                    detail=f"Token request rate limited. Please wait {remaining_cooldown:.1f} seconds before retrying."
                )
        
        logger.info("Fetching new Guesty token...")
        self._last_token_request = now
        token_url = "https://open-api.guesty.com/oauth2/token"
        data = {
            "grant_type":    "client_credentials",
            "scope":         "open-api",
            "client_id":     CLIENT_ID,
            "client_secret": GUESTY_SECRET,
        }
        headers = {"accept": "application/json"}

        # Implement exponential backoff for rate limiting
        max_retries = 3
        base_delay = 1  # seconds
        
        for attempt in range(max_retries):
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.post(token_url, data=data, headers=headers)
                resp.raise_for_status()
                break  # Success, exit retry loop
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429:  # Rate limited
                    if attempt < max_retries - 1:
                        delay = base_delay * (2 ** attempt)  # Exponential backoff
                        logger.warning(f"Rate limited (429). Retrying in {delay} seconds... (attempt {attempt + 1}/{max_retries})")
                        await asyncio.sleep(delay)
                        continue
                    else:
                        logger.error(f"Failed to fetch Guesty token after {max_retries} attempts: 429 - Rate limited")
                        # Track circuit breaker failure
                        self._circuit_breaker_failures += 1
                        self._circuit_breaker_last_failure = datetime.now(timezone.utc)
                        raise HTTPException(
                            status_code=429, 
                            detail="Guesty API rate limit exceeded. Please try again later."
                        ) from e
                else:
                    logger.error(f"Failed to fetch Guesty token: {e.response.status_code} - {e.response.text}")
                    # Track circuit breaker failure for non-429 errors too
                    self._circuit_breaker_failures += 1
                    self._circuit_breaker_last_failure = datetime.now(timezone.utc)
                    raise HTTPException(status_code=502, detail="Failed to fetch Guesty token") from e

        body = resp.json()
        access_token = body.get("access_token")
        expires_in = body.get("expires_in", 86400)  # seconds

        print(f"Token response body: {body}")
        print(f"Access token: {access_token}")

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
        
        # Reset circuit breaker on successful token fetch
        self._circuit_breaker_failures = 0
        self._circuit_breaker_last_failure = None
        
        return access_token
    
    def get_circuit_breaker_status(self) -> dict:
        """Get current circuit breaker status for monitoring"""
        now = datetime.now(timezone.utc)
        status = "CLOSED"
        
        if self._circuit_breaker_failures >= self._circuit_breaker_threshold:
            if self._circuit_breaker_last_failure:
                time_since_last_failure = (now - self._circuit_breaker_last_failure).total_seconds()
                if time_since_last_failure < self._circuit_breaker_timeout:
                    status = "OPEN"
                else:
                    status = "HALF_OPEN"
            else:
                status = "OPEN"
        
        return {
            "status": status,
            "failures": self._circuit_breaker_failures,
            "threshold": self._circuit_breaker_threshold,
            "last_failure": self._circuit_breaker_last_failure.isoformat() if self._circuit_breaker_last_failure else None,
            "timeout_seconds": self._circuit_breaker_timeout
        }
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
        return "eyJraWQiOiJwNTVFdjZtU1lNLVN3blliNmVZQTZ6elptSkQxSm1KMmNLSEhTejhqMDhNIiwiYWxnIjoiUlMyNTYifQ.eyJ2ZXIiOjEsImp0aSI6IkFULjdKYXdmR0xjMXFhSGNXV2tPajlJbkJ5VXRsRF8wR1BGUDlYMElySVhsRDgiLCJpc3MiOiJodHRwczovL2xvZ2luLmd1ZXN0eS5jb20vb2F1dGgyL2F1czFwOHFyaDUzQ2NRVEk5NWQ3IiwiYXVkIjoiaHR0cHM6Ly9vcGVuLWFwaS5ndWVzdHkuY29tIiwiaWF0IjoxNzQ3Nzc1OTUzLCJleHAiOjE3NDc4NjIzNTMsImNpZCI6IjBvYW9zcnNibm16MzQ4b05nNWQ3Iiwic2NwIjpbIm9wZW4tYXBpIl0sInJlcXVlc3RlciI6IkVYVEVSTkFMIiwiYWNjb3VudElkIjoiNWVjM2Y1ZDgyZDViNjYwMDJkNjAwMDEwIiwic3ViIjoiMG9hb3Nyc2JubXozNDhvTmc1ZDciLCJ1c2VyUm9sZXMiOlt7InJvbGVJZCI6eyJwZXJtaXNzaW9ucyI6WyJhZG1pbiJdfX1dLCJyb2xlIjoidXNlciIsImNsaWVudFR5cGUiOiJvcGVuYXBpIiwiaWFtIjoidjMiLCJhY2NvdW50TmFtZSI6IlByb3BvbGlzIE1hbmFnZW1lbnQiLCJuYW1lIjoiUHJvcG9saXNKJkQifQ.Tx-wmW7uQ3FLW194SuvyLekAglzZcgbs7DvUufBSKlwlma8AEUj6Y24SUfiFYetpXwetw9BkdNKTikhluKI9jN7QYTRxDDvDw8Bjh_TTDrf_I7zrUuXaKuqDDDzbws0O1L_YFHsrsIyZNnz0GBBFiR4q0YiuNZt0eW5qnK8ybINeLbnczSugzjdPAB9Ek7M0ATKBIC8tI4EiU5MPXkL1PplQoAJp1TQdAI60s9wu5cpszrFd0_kyXrIQRaFiM5u3JlX2ETkTTqt8S1IXYViqqRYOldkfVyIiDgJ7c7-LJ82r-867j0L4y3nPBW2GVXkNABKVEXQkI1HCGIURQFaS6Q"
        now = datetime.now(timezone.utc)
        logging.info("TESTINGS SSSS")
        # if self._token_cache["access_token"] and now < self._token_cache["expires_at"]:
        #     return self._token_cache["access_token"]
        # print("WE ARE HERE")
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
        expires_in = body.get("expires_in", 86400)  # seconds

        if not access_token:
            raise HTTPException(status_code=502, detail="No access_token in Guesty response")

        # Cache it, subtracting a small safety window (e.g., 60s)
        self._token_cache["access_token"] = access_token
        self._token_cache["expires_at"] = now + timedelta(seconds=expires_in - 1800)
        print(access_token)
        return access_token
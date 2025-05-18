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
        return "eyJraWQiOiJwNTVFdjZtU1lNLVN3blliNmVZQTZ6elptSkQxSm1KMmNLSEhTejhqMDhNIiwiYWxnIjoiUlMyNTYifQ.eyJ2ZXIiOjEsImp0aSI6IkFULk4xVnpnSXp6Q0tRclZZN0pzUXJhUlhWX2YwSWFQTVF0bVY2THNKdHI1ZEkiLCJpc3MiOiJodHRwczovL2xvZ2luLmd1ZXN0eS5jb20vb2F1dGgyL2F1czFwOHFyaDUzQ2NRVEk5NWQ3IiwiYXVkIjoiaHR0cHM6Ly9vcGVuLWFwaS5ndWVzdHkuY29tIiwiaWF0IjoxNzQ3NTkwMTkwLCJleHAiOjE3NDc2NzY1OTAsImNpZCI6IjBvYW9zcnNibm16MzQ4b05nNWQ3Iiwic2NwIjpbIm9wZW4tYXBpIl0sInJlcXVlc3RlciI6IkVYVEVSTkFMIiwiYWNjb3VudElkIjoiNWVjM2Y1ZDgyZDViNjYwMDJkNjAwMDEwIiwic3ViIjoiMG9hb3Nyc2JubXozNDhvTmc1ZDciLCJ1c2VyUm9sZXMiOlt7InJvbGVJZCI6eyJwZXJtaXNzaW9ucyI6WyJhZG1pbiJdfX1dLCJyb2xlIjoidXNlciIsImNsaWVudFR5cGUiOiJvcGVuYXBpIiwiaWFtIjoidjMiLCJhY2NvdW50TmFtZSI6IlByb3BvbGlzIE1hbmFnZW1lbnQiLCJuYW1lIjoiUHJvcG9saXNKJkQifQ.PKdGY2HVM0kzfjPEpwVp7UBZGAWeDdGKsjfKLZ6am-JgvpCWzAV1dwsLjBP0sjEiV--9c097uqEMEKAmsMUIUG8nBeob77z1vabNWCciLPESOCYtWOU4fINnBKON7ONdsbmTL3_IYuVIR9A7QUn2w0yojBsngkCjY3PfKjl-kx-u6hQxRKf0Y1---Sr6O-fV-0TU930hSo01cx7EM-nUVdkPcgYiTHI7l5aQQ1hWIxYR40G4yi04UlGnxrjgLbivLQ-W6mvHNfREIZqjEgXxNqk1CHM3P2yY4YgGv-JSHjWOgoD2Jlub_IZtoCtfuupBjo7Bru0NBO_8Tue-UwyB1g"
        # now = datetime.now(timezone.utc)
        # logging.info("TESTINGS SSSS")
        # if self._token_cache["access_token"] and now < self._token_cache["expires_at"]:
        #     return self._token_cache["access_token"]
        # print("WE ARE HERE")
        # token_url = "https://open-api.guesty.com/oauth2/token"
        # data = {
        #     "grant_type":    "client_credentials",
        #     "scope":         "open-api",
        #     "client_id":     CLIENT_ID,
        #     "client_secret": GUESTY_SECRET,
        # }
        # headers = {"accept": "application/json"}

        # async with httpx.AsyncClient() as client:
        #     resp = await client.post(token_url, data=data, headers=headers)
        # try:
        #     resp.raise_for_status()
        # except httpx.HTTPStatusError as e:
        #     raise HTTPException(status_code=502, detail="Failed to fetch Guesty token") from e

        # body = resp.json()
        # access_token = body.get("access_token")
        # expires_in = body.get("expires_in", 86400)  # seconds

        # if not access_token:
        #     raise HTTPException(status_code=502, detail="No access_token in Guesty response")

        # # Cache it, subtracting a small safety window (e.g., 60s)
        # self._token_cache["access_token"] = access_token
        # self._token_cache["expires_at"] = now + timedelta(seconds=expires_in - 1800)
        # print(access_token)
        # return access_token
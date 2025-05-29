import logging
from fastapi import APIRouter, HTTPException, Depends
import httpx
import os
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger("doorloop")
router = APIRouter(prefix="/api/doorloop", tags=["doorloop"])

DOORLOOP_API_KEY = os.getenv("DOORLOOP_API_KEY")
if not DOORLOOP_API_KEY:
    raise ValueError("DOORLOOP_API_KEY environment variable must be set")

DOORLOOP_BASE_URL = "https://app.doorloop.com/api"

def get_doorloop_headers():
    """Get headers for Doorloop API requests."""
    return {
        "Authorization": f"Bearer {DOORLOOP_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

@router.get("/properties")
async def get_doorloop_properties():
    """Get all properties from Doorloop API."""
    properties_url = f"{DOORLOOP_BASE_URL}/properties"
    headers = get_doorloop_headers()
    
    logger.info(f"Making request to: {properties_url}")
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(properties_url, headers=headers)
            resp.raise_for_status()
            logger.info(f"Successfully fetched {len(resp.json().get('data', []))} properties from Doorloop")
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP Error {e.response.status_code}: {e.response.text}")
            raise HTTPException(status_code=502, detail=f"Failed to fetch properties from Doorloop: {e.response.status_code}") from e
        except Exception as e:
            logger.error(f"Unexpected error fetching properties: {e}")
            raise HTTPException(status_code=500, detail="Internal server error") from e

@router.get("/properties/{property_id}")
async def get_doorloop_property(property_id: str):
    """Get a specific property from Doorloop API."""
    # Clean the property ID - remove quotes if present
    clean_property_id = property_id.strip('"\'')
    
    property_url = f"{DOORLOOP_BASE_URL}/properties/{clean_property_id}"
    headers = get_doorloop_headers()
    
    logger.info(f"Making request to: {property_url}")
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(property_url, headers=headers)
            resp.raise_for_status()
            logger.info(f"Successfully fetched property {clean_property_id} from Doorloop")
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP Error {e.response.status_code} for property {clean_property_id}: {e.response.text}")
            if e.response.status_code == 404:
                raise HTTPException(status_code=404, detail=f"Property {clean_property_id} not found")
            raise HTTPException(status_code=502, detail=f"Failed to fetch property from Doorloop: {e.response.status_code}") from e
        except Exception as e:
            logger.error(f"Unexpected error fetching property {clean_property_id}: {e}")
            raise HTTPException(status_code=500, detail="Internal server error") from e

@router.get("/test")
async def test_doorloop_connection():
    """Test Doorloop API connection and authentication."""
    test_url = f"{DOORLOOP_BASE_URL}/properties"
    headers = get_doorloop_headers()
    
    logger.info(f"Testing connection to: {test_url}")
    logger.info(f"Using headers: {headers}")
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(test_url, headers=headers)
            return {
                "status_code": resp.status_code,
                "url": str(resp.url),
                "headers_sent": headers,
                "response_headers": dict(resp.headers),
                "success": resp.status_code == 200
            }
        except Exception as e:
            return {
                "error": str(e),
                "url": test_url,
                "headers_sent": headers
            }

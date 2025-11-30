from fastapi import APIRouter, HTTPException
from typing import Optional
import httpx
import os
import logging
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load environment variables from .env file
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)

# Create a router instead of a FastAPI app
router = APIRouter(prefix="/api/jurny", tags=["jurny"])

def get_jurny_credentials():
    """Get Jurny credentials from environment variables."""
    client_id = os.getenv("JURNY_CLIENT_ID")
    client_secret = os.getenv("JURNY_CLIENT_SECRET")
    
    if not client_id or not client_secret:
        raise HTTPException(
            status_code=500,
            detail="JURNY_CLIENT_ID and JURNY_CLIENT_SECRET environment variables must be set"
        )
    
    return client_id, client_secret

JURNY_URL = "https://mos.jurny.com/api"

# Token cache
_token_cache = {
    "token": None,
    "expires_at": None
}

async def get_jurny_token() -> str:
    """
    Get Jurny OAuth token. Caches the token to avoid unnecessary requests.
    """
    # Check if we have a valid cached token
    if _token_cache["token"] and _token_cache["expires_at"]:
        if datetime.now() < _token_cache["expires_at"]:
            logger.debug("Using cached Jurny token")
            return _token_cache["token"]
    
    # Get credentials (will raise HTTPException if not set)
    client_id, client_secret = get_jurny_credentials()
    
    # Fetch new token
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{JURNY_URL}/integration/auth/token",
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                json={
                    "clientId": client_id,
                    "clientSecret": client_secret,
                },
                timeout=30.0
            )
            response.raise_for_status()
            data = response.json()
            
            # Extract token from response
            # The response structure may vary, adjust based on actual API response
            token = data.get("access_token") or data.get("token") or data.get("accessToken")
            
            if not token:
                logger.error(f"Token not found in response: {data}")
                raise HTTPException(status_code=500, detail="Failed to get Jurny token: token not in response")
            
            # Cache the token (assume it expires in 1 hour if not specified)
            expires_in = data.get("expires_in", 3600)  # Default to 1 hour
            _token_cache["token"] = token
            _token_cache["expires_at"] = datetime.now() + timedelta(seconds=expires_in - 60)  # Refresh 1 min early
            
            logger.info("Successfully obtained new Jurny token")
            return token
            
    except httpx.HTTPStatusError as e:
        error_text = e.response.text if e.response else "Unknown error"
        logger.error(f"HTTP error getting Jurny token: {e.response.status_code if e.response else 'Unknown'} - {error_text}")
        raise HTTPException(
            status_code=e.response.status_code if e.response else 500,
            detail=f"Failed to get Jurny token: {error_text}"
        )
    except Exception as e:
        logger.error(f"Error getting Jurny token: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to get Jurny token: {str(e)}")

async def get_jurny_headers():
    """
    Get headers for Jurny API requests with OAuth token.
    """
    token = await get_jurny_token()
    return {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

@router.get("/short-term-kpis")
async def get_short_term_kpis(
    date_start: Optional[str] = None,
    date_to: Optional[str] = None,
    property_name: Optional[str] = None,
    calculate_previous_period: Optional[int] = 0,
    hide_empty_groups: Optional[int] = 0,
    group_by: Optional[str] = "month",
):
    """
    Get revenue data from Jurny API
    """
    logger.info(f"Getting short-term KPIs - date_start: {date_start}, date_to: {date_to}")
    
    try:
        headers = await get_jurny_headers()
        logger.info("Successfully obtained Jurny headers")
    except Exception as e:
        logger.error(f"Failed to get Jurny headers: {e}", exc_info=True)
        raise
    
    try:
        async with httpx.AsyncClient() as client:

            if not property_name:
                # Build base params with required fields
                params = {
                    'fromDate': date_start,
                    'toDate': date_to,
                    'calculatePreviousPeriod': calculate_previous_period,
                    'hideEmptyGroups': hide_empty_groups,
                    'groupBy': group_by,
                }
                
                # Remove None values from params
                params = {k: v for k, v in params.items() if v is not None}
                
                logger.info(f"Making request to {JURNY_URL}/integration/stats with params: {params}")
                resp = await client.get(f"{JURNY_URL}/integration/stats", headers=headers, params=params, timeout=30.0)
                resp.raise_for_status()
                data = resp.json()
                
                
                # Log the response structure for debugging
                logger.info(f"Jurny API response structure: {list(data.keys())}")
                logger.debug(f"Full Jurny API response: {data}")

                data_current_period = data.get('currentPeriod', {})
                if not data_current_period:
                    logger.warning(f"No 'currentPeriod' found in response. Available keys: {list(data.keys())}")
                    # Try alternative structure
                    data_current_period = data.get('data', {}) or data
                
                data_total = data_current_period.get('total', {})
                if not data_total:
                    logger.warning(f"No 'total' found in currentPeriod. Available keys: {list(data_current_period.keys())}")
                    # Try using currentPeriod directly if total doesn't exist
                    data_total = data_current_period
                
                # Try multiple possible field names for revenue
                revenue = data_total.get('income', 0)
                occupancy = data_total.get('occupancy', 0)
                adr = data_total.get('adr', 0)
                revpar = data_total.get('revpar', 0)
                
                logger.info(f"Extracted KPIs - revenue: {revenue}, occupancy: {occupancy}, adr: {adr}, revpar: {revpar}")
                
                return {
                    "revenue": revenue,
                    "occupancy": occupancy,
                    "adr": adr,
                    "revpar": revpar
                }

            else:
                # Build base params with required fields
                params = {
                    'fromDate': date_start,
                    'toDate': date_to,
                    'calculatePreviousPeriod': calculate_previous_period,
                    'hideEmptyGroups': hide_empty_groups,
                    'groupBy': group_by,
                }
                
                # Remove None values from params
                params = {k: v for k, v in params.items() if v is not None}
                
                logger.info(f"Making request to {JURNY_URL}/integration/stats with params: {params}")
                resp = await client.get(f"{JURNY_URL}/integration/stats", headers=headers, params=params, timeout=30.0)
                resp.raise_for_status()
                data = resp.json()
                
                
                # Log the response structure for debugging
                logger.info(f"Jurny API response structure: {list(data.keys())}")
                logger.debug(f"Full Jurny API response: {data}")

                data_current_period = data.get('currentPeriod', {})
                if not data_current_period:
                    logger.warning(f"No 'currentPeriod' found in response. Available keys: {list(data.keys())}")
                    # Try alternative structure
                    data_current_period = data.get('data', {}) or data
                
                data_buildings = data_current_period.get('buildings', {})
                
                # Buildings is a dict keyed by UUID, convert to list of building objects
                if isinstance(data_buildings, dict):
                    data_buildings = list(data_buildings.values())
                elif not isinstance(data_buildings, list):
                    logger.warning(f"'buildings' is not a list or dict. Type: {type(data_buildings)}")
                    data_buildings = []
                
                if not data_buildings:
                    logger.warning(f"No 'buildings' found in currentPeriod. Available keys: {list(data_current_period.keys())}")
                    raise HTTPException(status_code=404, detail=f"No buildings data found for property: {property_name}")
                

                
                for building in data_buildings:
                    if not isinstance(building, dict):
                        continue
                    
                    if building.get('name') == property_name:
                        # Try multiple possible field names for revenue
                        revenue = building.get('income', 0)
                        occupancy = building.get('occupancy', 0)
                        adr = building.get('adr', 0)
                        revpar = building.get('revpar', 0)
                        
                        logger.info(f"Extracted KPIs for {property_name} - revenue: {revenue}, occupancy: {occupancy}, adr: {adr}, revpar: {revpar}")
                        
                        return {
                            "revenue": revenue,
                            "occupancy": occupancy,
                            "adr": adr,
                            "revpar": revpar
                        }
                
                # If we get here, property wasn't found
                raise HTTPException(status_code=404, detail=f"Property '{property_name}' not found in buildings data")

                
    except HTTPException:
        # Re-raise HTTPException as-is
        raise
    except httpx.HTTPStatusError as e:
        error_text = e.response.text if e.response else "Unknown error"
        logger.error(f"HTTP error from Jurny API: {e.response.status_code if e.response else 'Unknown'} - {error_text}")
        logger.error(f"Request URL: {e.request.url if e.request else 'Unknown'}")
        logger.error(f"Request headers: {dict(e.request.headers) if e.request else 'Unknown'}")
        raise HTTPException(
            status_code=e.response.status_code if e.response else 500,
            detail=f"Jurny API error: {error_text}"
        )
    except Exception as e:
        logger.error(f"Error getting revenue from Jurny API: {e}", exc_info=True)
        import traceback
        logger.error(f"Full traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Error fetching revenue data: {str(e)}")



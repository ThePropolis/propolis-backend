from fastapi import APIRouter, HTTPException
from typing import Optional
import httpx
import os
import logging
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Set up logging
logger = logging.getLogger(__name__)

# Create a router instead of a FastAPI app
router = APIRouter(prefix="/api/jurny", tags=["jurny"])

JURNY_API_KEY = os.getenv("JURNY_API_KEY")
if not JURNY_API_KEY:
    raise ValueError("JURNY_API_KEY is not set")

JURNY_URL = "https://mos.jurny.com/api"

def get_jurny_headers():
    return {
        "Authorization": f"Bearer {JURNY_API_KEY}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }

@router.get("/short-term-kpis")
async def get_short_term_kpis(
    date_start: Optional[str] = None,
    date_to: Optional[str] = None,
    calculate_previous_period: Optional[int] = 0,
    hide_empty_groups: Optional[int] = 0,
    group_by: Optional[str] = "month",
):
    """
    Get revenue data from Jurny API
    """
    headers = get_jurny_headers()
    
    try:
        async with httpx.AsyncClient() as client:
            # Build base params with required fields
            params = {
                'fromDate': date_start,
                'toDate': date_to,
                'calculatePreviousPeriod': calculate_previous_period,
                'hideEmptyGroups': hide_empty_groups,
                'groupBy': group_by,
            }
            
            resp = await client.get(f"{JURNY_URL}/integration/stats", headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()

            data_current_period = data.get('currentPeriod', {})
            data_total = data_current_period.get('total', {})
            revenue = data_total.get('income', 0)
            occupancy = data_total.get('occupancy', 0)
            adr = data_total.get('adr', 0)
            revpar = data_total.get('revpar', 0)



            
            return {
                "revenue": revenue,
                "occupancy": occupancy,
                "adr": adr,
                "revpar": revpar
            }
             
                
    except HTTPException:
        # Re-raise HTTPException as-is
        raise
    except httpx.HTTPStatusError as e:
        error_text = e.response.text if e.response else "Unknown error"
        logger.error(f"HTTP error from Jurny API: {e.response.status_code if e.response else 'Unknown'} - {error_text}")
        raise HTTPException(
            status_code=e.response.status_code if e.response else 500,
            detail=f"Jurny API error: {error_text}"
        )
    except Exception as e:
        logger.error(f"Error getting revenue from Jurny API: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error fetching revenue data: {str(e)}")



from collections import defaultdict
from datetime import datetime, timedelta
import logging
from typing import Optional
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
            data = resp.json()
            logger.info(f"Successfully fetched {len(data.get('data', []))} properties from Doorloop")
            return data
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

@router.get("/revenue")
async def get_doorloop_revenue():
    """Get revenue data from Doorloop API - tries multiple endpoint patterns."""
    headers = get_doorloop_headers()
    
    # Try different common API endpoint patterns
    possible_endpoints = [
        f"{DOORLOOP_BASE_URL}/revenue",
        f"{DOORLOOP_BASE_URL}/reports/revenue", 
        f"{DOORLOOP_BASE_URL}/financial/revenue",
        f"{DOORLOOP_BASE_URL}/accounting/revenue",
        f"{DOORLOOP_BASE_URL}/reports/financial",
        f"{DOORLOOP_BASE_URL}/reports",
        f"{DOORLOOP_BASE_URL}/transactions",
        f"{DOORLOOP_BASE_URL}/payments/summary"
    ]
    
    async with httpx.AsyncClient() as client:
        for endpoint_url in possible_endpoints:
            try:
                logger.info(f"Trying endpoint: {endpoint_url}")
                resp = await client.get(endpoint_url, headers=headers)
                
                if resp.status_code == 200:
                    content_type = resp.headers.get("content-type", "")
                    
                    # Check if we got HTML (login page) instead of JSON
                    if "text/html" in content_type:
                        logger.warning(f"Endpoint {endpoint_url} returned HTML (likely login page)")
                        continue
                    
                    # Check if response has content
                    if not resp.content:
                        logger.warning(f"Empty response from {endpoint_url}")
                        continue
                    
                    # Try to parse JSON
                    try:
                        data = resp.json()
                        logger.info(f"Successfully fetched data from {endpoint_url}")
                        return {
                            "endpoint_used": endpoint_url,
                            "data": data
                        }
                    except ValueError:
                        logger.warning(f"Non-JSON response from {endpoint_url}")
                        continue
                        
                elif resp.status_code == 404:
                    logger.info(f"Endpoint {endpoint_url} not found (404)")
                    continue
                else:
                    logger.warning(f"Endpoint {endpoint_url} returned status {resp.status_code}")
                    continue
                    
            except Exception as e:
                logger.warning(f"Error trying endpoint {endpoint_url}: {e}")
                continue
    
    # If no endpoints worked, return helpful information
    return {
        "message": "No working revenue endpoints found",
        "tried_endpoints": possible_endpoints,
        "suggestion": "Check Doorloop API documentation or use browser dev tools to find correct endpoints",
        "base_url": DOORLOOP_BASE_URL
    }

@router.get("/rent-roll")
async def get_doorloop_rent_roll():
    """Get rent roll data from Doorloop API."""
    rent_roll_url = f"{DOORLOOP_BASE_URL}/reports/rent-roll"
    headers = get_doorloop_headers()
    
    logger.info(f"Making request to: {rent_roll_url}")
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(rent_roll_url, headers=headers)
            resp.raise_for_status()
            logger.info("Successfully fetched rent roll data from Doorloop")
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP Error {e.response.status_code} for rent roll: {e.response.text}")
            raise HTTPException(status_code=502, detail=f"Failed to fetch rent roll from Doorloop: {e.response.status_code}") from e
        except Exception as e:
            logger.error(f"Unexpected error fetching rent roll: {e}")
            raise HTTPException(status_code=500, detail="Internal server error") from e

@router.get("/payments")
async def get_doorloop_payments():
    """Get payment data from Doorloop API."""
    payments_url = f"{DOORLOOP_BASE_URL}/payments"
    headers = get_doorloop_headers()
    
    logger.info(f"Making request to: {payments_url}")
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(payments_url, headers=headers)
            resp.raise_for_status()
            logger.info("Successfully fetched payments data from Doorloop")
            return resp.json()
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP Error {e.response.status_code} for payments: {e.response.text}")
            raise HTTPException(status_code=502, detail=f"Failed to fetch payments from Doorloop: {e.response.status_code}") from e
        except Exception as e:
            logger.error(f"Unexpected error fetching payments: {e}")
            raise HTTPException(status_code=500, detail="Internal server error") from e

@router.get("/financial-reports")
async def get_doorloop_financial_reports():
    """Get financial reports from Doorloop API."""
    reports_url = f"{DOORLOOP_BASE_URL}/reports/financial"
    headers = get_doorloop_headers()
    
    logger.info(f"Making request to: {reports_url}")
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(reports_url, headers=headers)
            resp.raise_for_status()
            
            # Check if response has content
            if not resp.content:
                logger.warning("Empty response from Doorloop financial reports API")
                return {"message": "No financial reports data available", "data": []}
            
            # Check content type
            content_type = resp.headers.get("content-type", "")
            logger.info(f"Response content type: {content_type}")
            logger.info(f"Response content: {resp.text[:500]}...")  # Log first 500 chars
            
            # Check if we got HTML (login page) instead of JSON
            if "text/html" in content_type:
                return {
                    "message": "Received HTML response (likely login page)",
                    "content_type": content_type,
                    "suggestion": "This endpoint may not exist or requires different authentication"
                }
            
            # Try to parse JSON
            try:
                data = resp.json()
                logger.info("Successfully fetched financial reports from Doorloop")
                return data
            except ValueError as json_error:
                logger.error(f"Failed to parse JSON response: {json_error}")
                # Return the raw text if it's not JSON
                return {
                    "message": "Financial reports data received but not in JSON format",
                    "content_type": content_type,
                    "raw_response": resp.text[:1000]  # First 1000 chars
                }
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP Error {e.response.status_code} for financial reports: {e.response.text}")
            raise HTTPException(status_code=502, detail=f"Failed to fetch financial reports from Doorloop: {e.response.status_code}") from e
        except Exception as e:
            logger.error(f"Unexpected error fetching financial reports: {e}")
            raise HTTPException(status_code=500, detail="Internal server error") from e

@router.get("/discover-api")
async def discover_doorloop_api():
    """Discover available Doorloop API endpoints by testing different patterns."""
    headers = get_doorloop_headers()
    
    # Try different base URLs
    base_urls = [
        "https://app.doorloop.com/api",
        "https://api.doorloop.com",
        "https://api.doorloop.com/v1", 
        "https://app.doorloop.com/api/v1",
        "https://app.doorloop.com/api/v2"
    ]
    
    # Common endpoints to test
    test_endpoints = [
        "",  # Root API
        "/properties",  # We know this works
        "/units",
        "/leases", 
        "/tenants",
        "/payments",
        "/transactions",
        "/reports",
        "/revenue",
        "/financial",
        "/accounting"
    ]
    
    working_endpoints = []
    
    async with httpx.AsyncClient() as client:
        for base_url in base_urls:
            logger.info(f"Testing base URL: {base_url}")
            
            for endpoint in test_endpoints:
                full_url = f"{base_url}{endpoint}"
                
                try:
                    resp = await client.get(full_url, headers=headers)
                    content_type = resp.headers.get("content-type", "")
                    
                    # Skip HTML responses (login pages)
                    if "text/html" in content_type:
                        continue
                    
                    if resp.status_code == 200:
                        try:
                            # Try to parse as JSON
                            data = resp.json()
                            working_endpoints.append({
                                "url": full_url,
                                "status": "success",
                                "content_type": content_type,
                                "has_data": bool(data),
                                "data_type": type(data).__name__,
                                "sample_keys": list(data.keys()) if isinstance(data, dict) else None
                            })
                            logger.info(f"✅ Working endpoint: {full_url}")
                        except ValueError:
                            # Non-JSON but successful response
                            working_endpoints.append({
                                "url": full_url,
                                "status": "success_non_json",
                                "content_type": content_type,
                                "response_length": len(resp.text)
                            })
                    elif resp.status_code == 401:
                        working_endpoints.append({
                            "url": full_url,
                            "status": "unauthorized",
                            "note": "Endpoint exists but requires different auth"
                        })
                    elif resp.status_code == 403:
                        working_endpoints.append({
                            "url": full_url,
                            "status": "forbidden", 
                            "note": "Endpoint exists but access denied"
                        })
                        
                except Exception as e:
                    # Skip connection errors, timeouts, etc.
                    continue
    
    return {
        "discovered_endpoints": working_endpoints,
        "total_found": len(working_endpoints),
        "suggestion": "Use the working endpoints above to build your revenue integration"
    }

@router.get("/explore-financial-data")
async def explore_doorloop_financial_data():
    """Explore existing endpoints for financial data within properties, units, and leases."""
    headers = get_doorloop_headers()
    financial_data = {}
    
    async with httpx.AsyncClient() as client:
        # 1. Check properties for financial fields
        try:
            logger.info("Exploring properties endpoint for financial data...")
            resp = await client.get(f"{DOORLOOP_BASE_URL}/properties", headers=headers)
            if resp.status_code == 200:
                data = resp.json()
                if "data" in data and len(data["data"]) > 0:
                    sample_property = data["data"][0]
                    financial_data["properties"] = {
                        "endpoint": f"{DOORLOOP_BASE_URL}/properties",
                        "sample_fields": list(sample_property.keys()),
                        "potential_financial_fields": [k for k in sample_property.keys() 
                                                     if any(term in k.lower() for term in 
                                                           ['rent', 'price', 'income', 'revenue', 'financial', 'money', 'cost'])]
                    }
        except Exception as e:
            financial_data["properties"] = {"error": str(e)}
        
        # 2. Try to get units for a property (units often have rent amounts)
        try:
            logger.info("Exploring units endpoint...")
            # Try units endpoint
            resp = await client.get(f"{DOORLOOP_BASE_URL}/units", headers=headers)
            if resp.status_code == 200 and "text/html" not in resp.headers.get("content-type", ""):
                data = resp.json()
                financial_data["units"] = {
                    "endpoint": f"{DOORLOOP_BASE_URL}/units",
                    "status": "success",
                    "data_structure": type(data).__name__,
                    "sample_keys": list(data.keys()) if isinstance(data, dict) else None
                }
            else:
                financial_data["units"] = {"status": "not_available", "status_code": resp.status_code}
        except Exception as e:
            financial_data["units"] = {"error": str(e)}
        
        # 3. Try leases endpoint (leases contain rental terms and amounts)
        try:
            logger.info("Exploring leases endpoint...")
            resp = await client.get(f"{DOORLOOP_BASE_URL}/leases", headers=headers)
            if resp.status_code == 200 and "text/html" not in resp.headers.get("content-type", ""):
                data = resp.json()
                financial_data["leases"] = {
                    "endpoint": f"{DOORLOOP_BASE_URL}/leases",
                    "status": "success", 
                    "data_structure": type(data).__name__,
                    "sample_keys": list(data.keys()) if isinstance(data, dict) else None
                }
            else:
                financial_data["leases"] = {"status": "not_available", "status_code": resp.status_code}
        except Exception as e:
            financial_data["leases"] = {"error": str(e)}
        
        # 4. Try to get units for a specific property
        if "properties" in financial_data and "sample_fields" in financial_data["properties"]:
            try:
                # Get first property ID
                resp = await client.get(f"{DOORLOOP_BASE_URL}/properties", headers=headers)
                if resp.status_code == 200:
                    props_data = resp.json()
                    if "data" in props_data and len(props_data["data"]) > 0:
                        property_id = props_data["data"][0].get("id")
                        if property_id:
                            logger.info(f"Exploring units for property {property_id}...")
                            resp = await client.get(f"{DOORLOOP_BASE_URL}/properties/{property_id}/units", headers=headers)
                            if resp.status_code == 200 and "text/html" not in resp.headers.get("content-type", ""):
                                units_data = resp.json()
                                financial_data["property_units"] = {
                                    "endpoint": f"{DOORLOOP_BASE_URL}/properties/{property_id}/units",
                                    "status": "success",
                                    "property_id": property_id,
                                    "data_structure": type(units_data).__name__,
                                    "sample_keys": list(units_data.keys()) if isinstance(units_data, dict) else None
                                }
            except Exception as e:
                financial_data["property_units"] = {"error": str(e)}
    
    return {
        "message": "Financial data exploration results",
        "financial_endpoints_found": financial_data,
        "recommendations": [
            "Check 'potential_financial_fields' in properties data",
            "If units endpoint works, it likely contains rent amounts",
            "If leases endpoint works, it contains rental income data",
            "Use property_units endpoint to get unit-specific financial data"
        ]
    }

@router.get("/profit-and-loss")
async def get_doorloop_profit_and_loss(
    start_date: str = None,
    end_date: str = None,
    property_id: str = None,
    unit_id: str = None,
    accounting_method: str = "CASH"
):
    """Get profit and loss summary from Doorloop API.
    
    Args:
        start_date: Start date for the report (YYYY-MM-DD format) - defaults to today
        end_date: End date for the report (YYYY-MM-DD format) - defaults to today
        property_id: Optional property ID to filter by
        unit_id: Optional unit ID to filter by
        accounting_method: Accounting method - defaults to 'CASH'
    """
    # Set default dates to today if not provided (matching PHP implementation)
    if not start_date:
        start_date = datetime.now().strftime('%Y-%m-%d')
    if not end_date:
        end_date = datetime.now().strftime('%Y-%m-%d')
    
    pl_url = f"{DOORLOOP_BASE_URL}/reports/profit-and-loss-summary"
    headers = get_doorloop_headers()
    
    # Build query parameters matching the PHP implementation
    params = {
        "filter_accountingMethod": accounting_method.upper(),
        "filter_date_from": start_date,
        "filter_date_to": end_date,
        "page_size": 500
    }
    
    # Add optional filters
    if property_id:
        params["filter_property"] = property_id
    if unit_id:
        params["filter_unit"] = unit_id
    
    logger.info(f"Making request to: {pl_url} with params: {params}")
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(pl_url, headers=headers, params=params)
            resp.raise_for_status()
            
            # Check if response has content
            if not resp.content:
                logger.warning("Empty response from Doorloop P&L API")
                return {"success": False, "message": "No profit and loss data available", "data": []}
            
            # Check content type
            content_type = resp.headers.get("content-type", "")
            logger.info(f"Response content type: {content_type}")
            
            # Check if we got HTML (login page) instead of JSON
            if "text/html" in content_type:
                logger.warning("Received HTML response (likely login page)")
                return {
                    "success": False,
                    "message": "Received HTML response (likely login page)",
                    "content_type": content_type,
                    "suggestion": "This endpoint may not exist or requires different authentication"
                }
            
            # Try to parse JSON
            try:
                data = resp.json()
                logger.info("Successfully fetched profit and loss data from Doorloop")
                return {
                    "success": True,
                    "data": data
                }
            except ValueError as json_error:
                logger.error(f"Failed to parse JSON response: {json_error}")
                logger.info(f"Response content: {resp.text[:500]}...")
                return {
                    "success": False,
                    "message": "P&L data received but not in JSON format",
                    "content_type": content_type,
                    "raw_response": resp.text
                }
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP Error {e.response.status_code} for P&L: {e.response.text}")
            return {
                "success": False,
                "status": e.response.status_code,
                "message": "Something went wrong"
            }
        except Exception as e:
            logger.error(f"Unexpected error fetching P&L: {e}")
            return {
                "success": False,
                "message": str(e)
            }

def lease_overlaps_date_range(lease, start_date, end_date):
    """
    Check if a lease overlaps with the given date range.
    Implements the same logic as the PHP code:
    - Lease starts within the date range, OR
    - Lease ends within the date range, OR  
    - Lease spans across the entire date range
    """
    
    # Try different possible date field names
    lease_start = (lease.get('leaseStartDate') or 
                   lease.get('startDate') or 
                   lease.get('start_date') or
                   lease.get('lease_start_date'))
    
    lease_end = (lease.get('leaseEndDate') or 
                 lease.get('endDate') or 
                 lease.get('end_date') or
                 lease.get('lease_end_date'))
    
    if not lease_start:
        logger.debug(f"Lease missing start date - available fields: {list(lease.keys())}")
        return False
    
    try:
        # Normalize date formats (handle ISO dates, timestamps, etc.)
        def normalize_date(date_str):
            if not date_str:
                return None
            
            # Handle ISO format with timestamp (2024-05-01T00:00:00Z)
            if 'T' in date_str:
                date_str = date_str.split('T')[0]
            
            # Handle different date separators and formats
            # Convert to YYYY-MM-DD format for comparison
            if len(date_str) == 10 and '-' in date_str:
                # Already in YYYY-MM-DD format
                return date_str
            elif '/' in date_str:
                # Handle MM/DD/YYYY or DD/MM/YYYY format
                parts = date_str.split('/')
                if len(parts) == 3:
                    # Assume MM/DD/YYYY for now (most common)
                    month, day, year = parts
                    return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            
            return date_str
        
        lease_start_normalized = normalize_date(lease_start)
        lease_end_normalized = normalize_date(lease_end) if lease_end else None
        
        if not lease_start_normalized:
            logger.debug(f"Could not normalize lease start date: {lease_start}")
            return False
        
        # Debug logging for first few comparisons
        if hasattr(lease_overlaps_date_range, '_debug_count'):
            lease_overlaps_date_range._debug_count += 1
        else:
            lease_overlaps_date_range._debug_count = 1
        
        if lease_overlaps_date_range._debug_count <= 3:
            logger.info(f"🔍 Date comparison #{lease_overlaps_date_range._debug_count}:")
            logger.info(f"   Query range: {start_date} to {end_date}")
            logger.info(f"   Lease dates: {lease_start_normalized} to {lease_end_normalized}")
        
        # Check overlap conditions (same as PHP logic)
        # 1. Lease starts within the date range
        if start_date <= lease_start_normalized <= end_date:
            if lease_overlaps_date_range._debug_count <= 3:
                logger.info(f"   ✅ Match: Lease starts within range")
            return True
        
        # 2. Lease ends within the date range (if end date exists)
        if lease_end_normalized and start_date <= lease_end_normalized <= end_date:
            if lease_overlaps_date_range._debug_count <= 3:
                logger.info(f"   ✅ Match: Lease ends within range")
            return True
        
        # 3. Lease spans across the entire date range
        if lease_end_normalized and lease_start_normalized < start_date and lease_end_normalized > end_date:
            if lease_overlaps_date_range._debug_count <= 3:
                logger.info(f"   ✅ Match: Lease spans entire range")
            return True
        
        # 4. For at-will leases (no end date) that started before the range end
        if not lease_end_normalized and lease_start_normalized <= end_date:
            if lease_overlaps_date_range._debug_count <= 3:
                logger.info(f"   ✅ Match: At-will lease overlaps")
            return True
        
        # No match
        if lease_overlaps_date_range._debug_count <= 3:
            logger.info(f"   ❌ No match")
        return False
        
    except Exception as e:
        logger.debug(f"Error parsing lease dates: {e}")
        logger.debug(f"  lease_start: {lease_start}")
        logger.debug(f"  lease_end: {lease_end}")
        # If we can't parse dates, include the lease to be safe
        return True

async def get_total_units_property(headers, property_id):
    """Get total number of units for a specific property"""
    
    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"Fetching units for property {property_id}")
            
            # Try property-specific units endpoint first
            property_units_url = f"{DOORLOOP_BASE_URL}/properties/{property_id}/units"
            response = await client.get(
                property_units_url,
                headers=headers,
                params={"limit": 1000}
            )
            
            logger.info(f"Property units response status: {response.status_code}")
            
            if response.status_code == 200 and response.content:
                content_type = response.headers.get("content-type", "")
                if "text/html" not in content_type:
                    try:
                        units_data = response.json()
                        units = units_data.get("data", [])
                        total_units = len(units)
                        logger.info(f"Found {total_units} units for property {property_id} via property endpoint")
                        return total_units
                    except Exception as json_error:
                        logger.error(f"Failed to parse property units JSON: {json_error}")
            
            # Fallback: Use general units endpoint with property filter
            logger.info(f"Trying general units endpoint with property filter")
            general_units_url = f"{DOORLOOP_BASE_URL}/units"
            
            total_units = 0
            page = 1
            max_pages = 20
            
            while page <= max_pages:
                response = await client.get(
                    general_units_url,
                    headers=headers,
                    params={
                        "property_id": property_id,
                        "page": page
                    }
                )
                
                if response.status_code != 200 or not response.content:
                    break
                
                content_type = response.headers.get("content-type", "")
                if "text/html" in content_type:
                    break
                
                try:
                    units_data = response.json()
                    units = units_data.get("data", [])
                    
                    if not units:
                        break
                    
                    total_units += len(units)
                    logger.info(f"Property {property_id} - Page {page}: {len(units)} units (total: {total_units})")
                    
                    # Check if this is the last page
                    if len(units) < 50:  # Doorloop's typical page size
                        break
                    
                    page += 1
                    
                except Exception as json_error:
                    logger.error(f"Failed to parse units JSON on page {page}: {json_error}")
                    break
            
            if total_units > 0:
                logger.info(f"Found {total_units} units for property {property_id} via general endpoint")
                return total_units
            
            # Last resort: Check if property has unit count field
            logger.info(f"Checking property data for unit count")
            property_response = await client.get(
                f"{DOORLOOP_BASE_URL}/properties/{property_id}",
                headers=headers
            )
            
            if property_response.status_code == 200 and property_response.content:
                try:
                    property_data = property_response.json()
                    property_info = property_data.get("data", {}) if isinstance(property_data.get("data"), dict) else property_data
                    
                    # Look for unit count fields
                    unit_count_fields = ["unitCount", "unit_count", "numberOfUnits", "unitsCount", "totalUnits"]
                    for field in unit_count_fields:
                        if field in property_info and isinstance(property_info[field], (int, float)):
                            total_units = int(property_info[field])
                            logger.info(f"Found {total_units} units for property {property_id} from {field} field")
                            return total_units
                            
                except Exception as json_error:
                    logger.error(f"Failed to parse property JSON: {json_error}")
            
            logger.warning(f"No units found for property {property_id}")
            return 0
            
        except Exception as e:
            logger.error(f"Error in get_total_units_property for property {property_id}: {str(e)}")
            raise


async def get_occupied_units_property(headers, property_id, date_from, date_to):
    """Get number of occupied units for a specific property based on active leases"""
    
    async with httpx.AsyncClient() as client:
        try:
            logger.info(f"🏢 Fetching occupied units for property {property_id} from {date_from} to {date_to}")
            
            # Get leases for the specific property
            leases_url = f"{DOORLOOP_BASE_URL}/leases"
            
            # Try different API filtering strategies for property-specific leases
            api_strategies = [
                {
                    "name": "property_and_date_filter",
                    "params": {
                        "filter_property": property_id,
                        "filter_date_from": date_from,
                        "filter_date_to": date_to,
                        "filter_status": "active"
                    }
                }
            ]
            
            leases_data = None
            successful_strategy = None
            
            for strategy in api_strategies:
                strategy_name = strategy["name"]
                base_params = strategy["params"]
                
                logger.info(f"🔍 Trying strategy: {strategy_name} for property {property_id}")
                logger.info(f"   📋 Params: {base_params}")
                
                strategy_leases = []
                page = 1
                max_pages = 20
                
                while page <= max_pages:
                    page_params = {**base_params, "page": page}
                    
                    try:
                        response = await client.get(leases_url, headers=headers, params=page_params)
                        
                        logger.info(f"   📡 API Response: status={response.status_code}, content_length={len(response.content) if response.content else 0}")
                        
                        if response.status_code != 200:
                            logger.warning(f"   ❌ Strategy {strategy_name} failed with status {response.status_code}")
                            logger.warning(f"   Response: {response.text[:200]}")
                            break
                        
                        if not response.content:
                            logger.info(f"   ⚠️ Empty response on page {page}")
                            break
                        
                        content_type = response.headers.get("content-type", "")
                        if "text/html" in content_type:
                            logger.warning(f"   ❌ Got HTML response (likely login page)")
                            break
                        
                        try:
                            data = response.json()
                        except Exception as json_error:
                            logger.error(f"   ❌ JSON parsing error for strategy {strategy_name}: {json_error}")
                            logger.error(f"   Raw response: {response.text[:300]}")
                            break
                        
                        page_leases = data.get('data', [])
                        
                        if not page_leases:
                            logger.info(f"   📭 No leases on page {page}")
                            break
                        
                        # Debug: Show structure of first lease
                        if page == 1 and page_leases:
                            first_lease = page_leases[0]
                            logger.info(f"   📋 First lease structure:")
                            logger.info(f"      Available fields: {list(first_lease.keys())}")
                            
                            # Show property information
                            property_info = None
                            if 'property' in first_lease and isinstance(first_lease['property'], dict):
                                property_info = first_lease['property']
                                logger.info(f"      Property object: {property_info}")
                            elif 'propertyId' in first_lease:
                                logger.info(f"      PropertyId field: {first_lease['propertyId']}")
                            elif 'property_id' in first_lease:
                                logger.info(f"      Property_id field: {first_lease['property_id']}")
                            else:
                                logger.warning(f"      ⚠️ No obvious property identifier found")
                            
                            # Show date fields
                            logger.info(f"   📅 Date fields in first lease:")
                            for field in ['leaseStartDate', 'leaseEndDate', 'startDate', 'endDate', 'createdAt', 'updatedAt']:
                                if field in first_lease:
                                    logger.info(f"      {field}: {first_lease[field]}")
                            
                            # Show unit fields
                            logger.info(f"   🏠 Unit fields in first lease:")
                            for field in ['units', 'unit_id', 'unitId', 'unit', 'propertyUnitId']:
                                if field in first_lease:
                                    logger.info(f"      {field}: {first_lease[field]}")
                        
                        strategy_leases.extend(page_leases)
                        logger.info(f"   ✅ Strategy {strategy_name} - Page {page}: {len(page_leases)} leases (total: {len(strategy_leases)})")
                        
                        # Check if this is the last page
                        if len(page_leases) < 50:
                            logger.info(f"   📄 Last page reached (got {len(page_leases)} < 50)")
                            break
                        
                        page += 1
                        
                    except Exception as e:
                        logger.error(f"   ❌ Error in strategy {strategy_name} on page {page}: {str(e)}")
                        break
                
                logger.info(f"🎯 Strategy {strategy_name} result: {len(strategy_leases)} total leases")
                
                if len(strategy_leases) > 0:
                    leases_data = strategy_leases
                    successful_strategy = strategy_name
                    logger.info(f"✅ Using strategy: {strategy_name}")
                    break
                else:
                    logger.warning(f"❌ Strategy {strategy_name} returned 0 leases")
            
            if not leases_data:
                logger.error(f"❌ All API strategies failed - no leases retrieved for property {property_id}")
                logger.error("🔍 This could mean:")
                logger.error("   1. No leases exist for this property")
                logger.error("   2. Property ID is incorrect")
                logger.error("   3. API filtering parameters don't work")
                logger.error("   4. Authentication/permission issues")
                return 0
            
            # Filter leases manually (important for date filtering and property verification)
            logger.info(f"🔍 Applying manual filtering to {len(leases_data)} leases for property {property_id}")
            logger.info(f"   📅 Target date range: {date_from} to {date_to}")
            
            occupied_unit_ids = set()
            property_matches = 0
            date_matches = 0
            unit_extraction_successes = 0
            
            for i, lease in enumerate(leases_data):
                # Debug first 5 leases in detail
                if i < 5:
                    logger.info(f"🔍 Detailed analysis of lease {i+1}:")
                    logger.info(f"   Lease keys: {list(lease.keys())}")
                
                # Verify this lease is actually for the requested property
                lease_property_id = None
                
                # Try different ways to get property ID from lease
                if 'property' in lease and isinstance(lease['property'], dict):
                    lease_property_id = lease['property'].get('id')
                    if i < 5:
                        logger.info(f"   Property from 'property' object: {lease_property_id}")
                elif 'propertyId' in lease:
                    lease_property_id = lease['propertyId']
                    if i < 5:
                        logger.info(f"   Property from 'propertyId': {lease_property_id}")
                elif 'property_id' in lease:
                    lease_property_id = lease['property_id']
                    if i < 5:
                        logger.info(f"   Property from 'property_id': {lease_property_id}")
                
                if i < 5:
                    logger.info(f"   Extracted property ID: {lease_property_id}")
                    logger.info(f"   Target property ID: {property_id}")
                    logger.info(f"   Property match: {str(lease_property_id) == str(property_id)}")
                
                # Check property match
                property_match = lease_property_id and str(lease_property_id) == str(property_id)
                if property_match:
                    property_matches += 1
                    
                    # Check if lease overlaps with the date range
                    date_overlap = lease_overlaps_date_range(lease, date_from, date_to)
                    if i < 5:
                        logger.info(f"   Date overlap result: {date_overlap}")
                    
                    if date_overlap:
                        date_matches += 1
                        
                        # Extract unit IDs
                        unit_ids = []
                        
                        # Method 1: Check if 'units' field contains an array
                        if "units" in lease and isinstance(lease["units"], list):
                            unit_ids.extend(lease["units"])
                            if i < 5:
                                logger.info(f"   Units from 'units' array: {lease['units']}")
                        
                        # Method 2: Check for single unit ID fields
                        for field_name in ["unit_id", "unitId", "propertyUnitId", "unit", "unitIds"]:
                            if field_name in lease and lease[field_name]:
                                if isinstance(lease[field_name], list):
                                    unit_ids.extend(lease[field_name])
                                else:
                                    unit_ids.append(lease[field_name])
                                if i < 5:
                                    logger.info(f"   Units from '{field_name}': {lease[field_name]}")
                        
                        if i < 5:
                            logger.info(f"   Total unit IDs extracted: {unit_ids}")
                        
                        # Add all found unit IDs to the set
                        units_added = 0
                        for unit_id in unit_ids:
                            if unit_id:
                                occupied_unit_ids.add(str(unit_id))
                                units_added += 1
                        
                        if units_added > 0:
                            unit_extraction_successes += 1
                        
                        if i < 5:
                            logger.info(f"   Units added to set: {units_added}")
                    else:
                        if i < 5:
                            logger.info(f"   ❌ Lease does not overlap with date range")
                else:
                    if i < 5:
                        logger.info(f"   ❌ Lease property ID doesn't match target")
            
            occupied_count = len(occupied_unit_ids)
            
            logger.info(f"📊 Manual filtering summary for property {property_id}:")
            logger.info(f"   Total leases processed: {len(leases_data)}")
            logger.info(f"   Property matches: {property_matches}")
            logger.info(f"   Date matches: {date_matches}")
            logger.info(f"   Successful unit extractions: {unit_extraction_successes}")
            logger.info(f"   Unique occupied units: {occupied_count}")
            logger.info(f"   Strategy used: {successful_strategy}")
            
            if occupied_count == 0:
                logger.warning(f"⚠️ Found 0 occupied units for property {property_id}. Possible issues:")
                logger.warning(f"   - Property filter not working (got {property_matches} property matches)")
                logger.warning(f"   - Date filter not working (got {date_matches} date matches)")
                logger.warning(f"   - Unit ID extraction failed (got {unit_extraction_successes} extractions)")
                logger.warning(f"   - All leases are outside the date range")
                logger.warning(f"   - No active leases for this property")
            
            return occupied_count
            
        except Exception as e:
            logger.error(f"❌ Error in get_occupied_units_property for property {property_id}: {str(e)}")
            raise

@router.get("/occupancy-rate-doorloop")
async def get_occupancy_rate(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    property_id: Optional[str] = None
):
    """
    Calculate occupancy rate: (occupied units / total units) * 100
    
    Parameters:
    - date_from: Start date (YYYY-MM-DD) - defaults to current month start
    - date_to: End date (YYYY-MM-DD) - defaults to current month end
    - property_id: Optional property ID to calculate occupancy for specific property
    """
    
    if not DOORLOOP_API_KEY:
        raise HTTPException(status_code=500, detail="DoorLoop API token not configured")
    
    # Set default date range to current month if not provided
    if not date_from or not date_to:
        today = datetime.now()
        date_from = today.replace(day=1).strftime("%Y-%m-%d")
        next_month = today.replace(day=28) + timedelta(days=4)
        date_to = (next_month - timedelta(days=next_month.day)).strftime("%Y-%m-%d")
    
    headers = get_doorloop_headers()
    
    if property_id:
        logger.info(f"Calculating occupancy rate for property {property_id} from {date_from} to {date_to}")
        
        try:
            # Get total units for the specific property
            total_units = await get_units_by_property(property_id)
            logger.info(f"Property {property_id}: {total_units} total units")
            
            # Get occupied units for the specific property
            occupied_units = await get_leases_by_property(property_id, date_from, date_to)
            logger.info(f"Property {property_id}: {occupied_units} occupied units")
            
            # Calculate occupancy rate
            if total_units == 0:
                occupancy_rate = 0

            else:
                totalUnits = total_units["numOfUnits"]
                unitsDict = occupied_units.get("units", {})

                percentSum = 0
                for key in unitsDict.keys():
                    if len(unitsDict[key]) > 1:
                        percentSum += sum(unitsDict[key]) / len(unitsDict[key])
                    else:
                        percentSum += unitsDict[key][0]

                
                occupancy_rate_percentage_for_property = percentSum / totalUnits

            return {
                "occupancy_rate": round(occupancy_rate_percentage_for_property, 2),
                "occupied_units": len(unitsDict),
                "total_units": totalUnits,
                "date_from": date_from,
                "date_to": date_to,
                "percentage": f"{round(occupancy_rate_percentage_for_property, 2)}%"
            }
            # return {
            #     "occupied_units": len(unitsDict),
            #     "total_units": totalUnits,
            #     "property_id": property_id,
            #     "date_from": date_from,
            #     "date_to": date_to,
            #     "percentage": f"{round(occupancy_rate_percentage_for_property, 2)}%"
            # }
            
        except Exception as e:
            logger.error(f"Error calculating occupancy rate for property {property_id}: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error calculating occupancy rate for property {property_id}: {str(e)}")
    
    else:
        logger.info(f"Calculating overall occupancy rate from {date_from} to {date_to}")
        
        try:
            # Get total units from all properties
            total_units = await get_total_units(headers)
            logger.info(f"Found {total_units} total units")
            
            # Get occupied units from active leases
            occupied_units = await get_occupied_units(headers, date_from, date_to)
            logger.info(f"Found {occupied_units} occupied units")
            
            # Calculate occupancy rate
            if total_units == 0:
                occupancy_rate = 0
            else:
                occupancy_rate = (occupied_units / total_units) * 100
            
            return {
                "occupancy_rate": round(occupancy_rate, 2),
                "occupied_units": occupied_units,
                "total_units": total_units,
                "date_from": date_from,
                "date_to": date_to,
                "percentage": f"{round(occupancy_rate, 2)}%"
            }
            
        except Exception as e:
            logger.error(f"Error calculating overall occupancy rate: {str(e)}")
            raise HTTPException(status_code=500, detail=f"Error calculating overall occupancy rate: {str(e)}")


    # if property_id:
    #     logger.info(f"Calculating occupancy rate for property {property_id} from {date_from} to {date_to}")
    #     try:
    #         # Get total units for the specific property
    #         total_units_response = await get_units_by_property(property_id)
            
    #         # DEBUG: Log the actual response structure
    #         logger.info(f"DEBUG - total_units_response type: {type(total_units_response)}")
    #         logger.info(f"DEBUG - total_units_response content: {total_units_response}")
            
    #         # Handle different response types
    #         if isinstance(total_units_response, str):
    #             logger.error(f"ERROR: get_units_by_property returned a string instead of dict: {total_units_response}")
    #             raise HTTPException(status_code=500, detail="Invalid response format from units API")
            
    #         if not isinstance(total_units_response, dict):
    #             logger.error(f"ERROR: get_units_by_property returned unexpected type: {type(total_units_response)}")
    #             raise HTTPException(status_code=500, detail="Invalid response format from units API")
            
    #         # Extract total units count
    #         total_units = total_units_response.get("numOfUnits", 0)
    #         logger.info(f"Property {property_id}: {total_units} total units")
            
    #         # Get occupied units for the specific property
    #         occupied_units_response = await get_leases_by_property(property_id, date_from, date_to)
            
    #         # DEBUG: Log the lease response structure
    #         logger.info(f"DEBUG - occupied_units_response type: {type(occupied_units_response)}")
    #         logger.info(f"DEBUG - occupied_units_response content: {occupied_units_response}")
            
    #         # Handle different response types
    #         if isinstance(occupied_units_response, str):
    #             logger.error(f"ERROR: get_leases_by_property returned a string instead of dict: {occupied_units_response}")
    #             raise HTTPException(status_code=500, detail="Invalid response format from leases API")
            
    #         if not isinstance(occupied_units_response, dict):
    #             logger.error(f"ERROR: get_leases_by_property returned unexpected type: {type(occupied_units_response)}")
    #             raise HTTPException(status_code=500, detail="Invalid response format from leases API")
            
    #         # Extract units dictionary
    #         units_dict = occupied_units_response.get("units", {})
    #         logger.info(f"DEBUG - units_dict type: {type(units_dict)}")
    #         logger.info(f"DEBUG - units_dict content: {units_dict}")
            
    #         # Calculate occupancy rate
    #         if total_units == 0:
    #             occupancy_rate_percentage = 0.0
    #             logger.warning(f"Property {property_id} has 0 total units")
    #         else:
    #             if not units_dict:
    #                 occupancy_rate_percentage = 0.0
    #                 logger.info(f"Property {property_id} has no occupied units")
    #             else:
    #                 # Calculate occupancy percentage
    #                 percent_sum = 0.0
    #                 for unit_id, occupancy_data in units_dict.items():
    #                     logger.info(f"DEBUG - Processing unit {unit_id}: {occupancy_data}")
                        
    #                     if isinstance(occupancy_data, list):
    #                         if len(occupancy_data) > 1:
    #                             unit_percentage = sum(occupancy_data) / len(occupancy_data)
    #                         elif len(occupancy_data) == 1:
    #                             unit_percentage = occupancy_data[0]
    #                         else:
    #                             unit_percentage = 0.0
    #                     else:
    #                         # Handle case where occupancy_data is not a list
    #                         unit_percentage = float(occupancy_data) if occupancy_data else 0.0
                        
    #                     percent_sum += unit_percentage
    #                     logger.info(f"DEBUG - Unit {unit_id} percentage: {unit_percentage}")
                    
    #                 occupancy_rate_percentage = percent_sum / total_units
    #                 logger.info(f"DEBUG - Final calculation: {percent_sum} / {total_units} = {occupancy_rate_percentage}")
            
    #         return {
    #             "occupied_units": len(units_dict),
    #             "total_units": total_units,
    #             "property_id": property_id,
    #             "date_from": date_from,
    #             "date_to": date_to,
    #             "percentage": f"{round(occupancy_rate_percentage * 100, 2)}%",
    #             "debug_info": {
    #                 "total_units_response_type": str(type(total_units_response)),
    #                 "occupied_units_response_type": str(type(occupied_units_response)),
    #                 "units_dict_keys": list(units_dict.keys()) if isinstance(units_dict, dict) else "Not a dict"
    #             }
    #         }
            
    #     except Exception as e:
    #         logger.error(f"Error calculating occupancy rate for property {property_id}: {str(e)}")
    #         logger.error(f"Error type: {type(e)}")
    #         import traceback
    #         logger.error(f"Full traceback: {traceback.format_exc()}")
    #         raise HTTPException(
    #             status_code=500, 
    #             detail=f"Error calculating occupancy rate for property {property_id}: {str(e)}"
    #         )




async def get_total_units(headers):
    """Get total number of units from all properties"""
    
    async with httpx.AsyncClient() as client:
        try:
            # Get all properties
            logger.info(f"Fetching properties from {DOORLOOP_BASE_URL}/properties")
            response = await client.get(
                f"{DOORLOOP_BASE_URL}/properties",
                headers=headers,
                params={"limit": 1000}
            )
            
            logger.info(f"Properties response status: {response.status_code}")
            logger.info(f"Properties response content type: {response.headers.get('content-type', '')}")
            logger.info(f"Properties response has content: {bool(response.content)}")
            
            if response.status_code != 200:
                logger.error(f"Failed to fetch properties: Status {response.status_code}, Response: {response.text}")
                raise Exception(f"Failed to fetch properties: Status {response.status_code}")
            
            # Check if response has content
            if not response.content:
                logger.warning("Empty response from properties endpoint")
                return 0
            
            # Check content type
            content_type = response.headers.get("content-type", "")
            if "text/html" in content_type:
                logger.warning("Received HTML response (likely login page) for properties")
                raise Exception("Authentication failed - received HTML instead of JSON")
            
            # Try to parse JSON with detailed error handling
            try:
                properties_data = response.json()
                logger.info(f"Successfully parsed properties JSON. Keys: {list(properties_data.keys()) if isinstance(properties_data, dict) else 'not_dict'}")
            except Exception as json_error:
                logger.error(f"Failed to parse properties JSON: {json_error}")
                logger.error(f"Response content preview: {response.text[:500]}")
                raise Exception(f"Failed to parse properties JSON: {json_error}")
            
            properties = properties_data.get("data", [])
            logger.info(f"Found {len(properties)} properties")
            
            if not properties:
                logger.warning("No properties found in response")
                return 0
            
            total_units = 0
            
            # Try different approaches to count units
            
            # Approach 1: Try to get units from each property's units endpoint
            logger.info("Approach 1: Fetching units from property-specific endpoints")
            units_from_endpoints = 0
            successful_property_requests = 0
            
            for i, property_data in enumerate(properties):
                property_id = property_data.get("id")
                if not property_id:
                    logger.warning(f"Property {i} has no ID, skipping")
                    continue
                
                logger.info(f"Fetching units for property {property_id} ({i+1}/{len(properties)})")
                
                try:
                    units_response = await client.get(
                        f"{DOORLOOP_BASE_URL}/properties/{property_id}/units",
                        headers=headers,
                        params={"limit": 1000}
                    )
                    
                    logger.info(f"Units response for property {property_id}: Status {units_response.status_code}")
                    
                    if units_response.status_code == 200 and units_response.content:
                        content_type = units_response.headers.get("content-type", "")
                        if "text/html" not in content_type:
                            try:
                                units_data = units_response.json()
                                units = units_data.get("data", [])
                                units_from_endpoints += len(units)
                                successful_property_requests += 1
                                logger.info(f"Property {property_id} has {len(units)} units")
                            except Exception as units_json_error:
                                logger.error(f"Failed to parse units JSON for property {property_id}: {units_json_error}")
                                continue
                        else:
                            logger.warning(f"Got HTML response for units of property {property_id}")
                    else:
                        logger.warning(f"Failed to fetch units for property {property_id}: Status {units_response.status_code}")
                        
                except Exception as units_error:
                    logger.error(f"Error fetching units for property {property_id}: {units_error}")
                    continue
            
            logger.info(f"Approach 1 result: {units_from_endpoints} units from {successful_property_requests}/{len(properties)} properties")
            
            # Approach 2: Try to get units from a general units endpoint
            logger.info("Approach 2: Trying general units endpoint")
            units_from_general_endpoint = 0
            
            try:
                general_units_response = await client.get(
                    f"{DOORLOOP_BASE_URL}/units",
                    headers=headers,
                    params={"limit": 1000}
                )
                
                logger.info(f"General units endpoint status: {general_units_response.status_code}")
                
                if general_units_response.status_code == 200 and general_units_response.content:
                    content_type = general_units_response.headers.get("content-type", "")
                    if "text/html" not in content_type:
                        try:
                            general_units_data = general_units_response.json()
                            general_units = general_units_data.get("data", [])
                            units_from_general_endpoint = len(general_units)
                            logger.info(f"General units endpoint returned {units_from_general_endpoint} units")
                        except Exception as general_json_error:
                            logger.error(f"Failed to parse general units JSON: {general_json_error}")
                    else:
                        logger.warning("General units endpoint returned HTML")
                else:
                    logger.info(f"General units endpoint not available (status: {general_units_response.status_code})")
                    
            except Exception as general_error:
                logger.info(f"General units endpoint not accessible: {general_error}")
            
            # Approach 3: Check if properties have unit count fields
            logger.info("Approach 3: Checking for unit count fields in property data")
            units_from_property_fields = 0
            
            for i, property_data in enumerate(properties):
                # Look for common field names that might indicate unit count
                unit_count_fields = ["unitCount", "unit_count", "numberOfUnits", "unitsCount", "totalUnits"]
                
                for field in unit_count_fields:
                    if field in property_data and isinstance(property_data[field], (int, float)):
                        units_from_property_fields += int(property_data[field])
                        logger.info(f"Property {i+1} has {property_data[field]} units (from {field} field)")
                        break
                else:
                    # If no unit count field found, check if there are unit-related fields
                    logger.debug(f"Property {i+1} fields: {list(property_data.keys())}")
            
            logger.info(f"Approach 3 result: {units_from_property_fields} units from property fields")
            
            # Choose the best result
            if units_from_endpoints > 0:
                total_units = units_from_endpoints
                logger.info(f"Using Approach 1 result: {total_units} units from property endpoints")
            elif units_from_general_endpoint > 0:
                total_units = units_from_general_endpoint
                logger.info(f"Using Approach 2 result: {total_units} units from general endpoint")
            elif units_from_property_fields > 0:
                total_units = units_from_property_fields
                logger.info(f"Using Approach 3 result: {total_units} units from property fields")
            else:
                logger.warning("No units found with any approach")
                total_units = 0
            
            logger.info(f"Final total units calculated: {total_units}")
            return total_units
            
        except Exception as e:
            logger.error(f"Error in get_total_units: {str(e)}")
            raise

async def get_occupied_units(headers, date_from, date_to):
    """Get number of occupied units based on active leases"""
    
    async with httpx.AsyncClient() as client:
        try:
            # Get all active leases within the date range
            logger.info(f"Fetching leases from {DOORLOOP_BASE_URL}/leases")
            logger.info(f"Date range: {date_from} to {date_to}")
            
            # Use the correct Doorloop API parameter format (matching profit-and-loss implementation)
            params_to_try = [
                # Strategy 1: Filter by lease start date (most likely for occupancy)
                {
                    "limit": 1000,
                    "filter_date_from": date_from,
                    "filter_date_to": date_to,
                    "filter_status": "active"
                },
                # Strategy 2: Filter by lease end date 
                {
                    "limit": 1000,
                    "filter_end_date_from": date_from,
                    "filter_end_date_to": date_to,
                    "filter_status": "active"
                },
                # Strategy 3: Just active leases without date filter (fallback)
                {
                    "limit": 1000,
                    "filter_status": "active"
                },
                # Strategy 4: All leases without any filters (last resort)
                {
                    "limit": 1000
                }
            ]
            
            leases_data = None
            successful_strategy = None
            
            for i, params in enumerate(params_to_try):
                strategy_name = [
                    "lease_start_date_filter",
                    "lease_end_date_filter", 
                    "active_status_only",
                    "no_filters"
                ][i]
                
                logger.info(f"Trying strategy {i+1} ({strategy_name}) with params: {params}")
                
                response = await client.get(
                    f"{DOORLOOP_BASE_URL}/leases",
                    headers=headers,
                    params=params
                )
                
                logger.info(f"Strategy {strategy_name} - Response status: {response.status_code}")
                logger.info(f"Strategy {strategy_name} - Content type: {response.headers.get('content-type', '')}")
                logger.info(f"Strategy {strategy_name} - Has content: {bool(response.content)}")
                
                if response.status_code == 200 and response.content:
                    content_type = response.headers.get("content-type", "")
                    if "text/html" not in content_type:
                        try:
                            leases_data = response.json()
                            successful_strategy = strategy_name
                            logger.info(f"Successfully parsed leases JSON with strategy: {strategy_name}")
                            
                            # Check if we got meaningful results
                            leases_count = len(leases_data.get("data", []))
                            logger.info(f"Strategy {strategy_name} returned {leases_count} leases")
                            
                            # If this is a date-filtered strategy and we got results, use it
                            if i <= 1 and leases_count > 0:
                                break
                            # If this is a fallback strategy, use it only if no better option
                            elif i > 1:
                                break
                                
                        except Exception as json_error:
                            logger.error(f"Failed to parse leases JSON with strategy {strategy_name}: {json_error}")
                            continue
                else:
                    logger.warning(f"Strategy {strategy_name} failed with status {response.status_code}")
            
            if not leases_data:
                logger.error("All lease request strategies failed")
                raise Exception("Failed to fetch leases with any parameter combination")
            
            logger.info(f"Using strategy: {successful_strategy}")
            logger.info(f"Leases response keys: {list(leases_data.keys()) if isinstance(leases_data, dict) else 'not_dict'}")
            
            leases = leases_data.get("data", [])
            logger.info(f"Found {len(leases)} total leases")
            
            if not leases:
                logger.warning("No leases found")
                return 0
            
            # Count unique units that have active leases within the date range
            occupied_unit_ids = set()
            
            for i, lease in enumerate(leases):
                logger.debug(f"Processing lease {i+1}/{len(leases)}")
                
                # Check if lease is within the date range (if we're using a fallback strategy)
                if successful_strategy in ["active_status_only", "no_filters"]:
                    # Manual date filtering for fallback strategies
                    lease_start = lease.get("startDate") or lease.get("start_date") or lease.get("createdAt")
                    lease_end = lease.get("endDate") or lease.get("end_date") or lease.get("expiresAt")
                    
                    if lease_start:
                        try:
                            from datetime import datetime
                            lease_start_dt = datetime.fromisoformat(lease_start.replace('Z', '+00:00'))
                            date_from_dt = datetime.fromisoformat(f"{date_from}T00:00:00+00:00")
                            date_to_dt = datetime.fromisoformat(f"{date_to}T23:59:59+00:00")
                            
                            # Skip leases that don't overlap with our date range
                            if lease_start_dt > date_to_dt:
                                continue
                            if lease_end:
                                lease_end_dt = datetime.fromisoformat(lease_end.replace('Z', '+00:00'))
                                if lease_end_dt < date_from_dt:
                                    continue
                        except Exception as date_error:
                            logger.debug(f"Could not parse dates for lease {i+1}: {date_error}")
                            # Include the lease if we can't parse dates
                
                # Try different ways to extract unit IDs based on the actual data structure
                unit_ids = []
                
                # Method 1: Check if 'units' field contains an array of unit IDs
                if "units" in lease and isinstance(lease["units"], list):
                    unit_ids.extend(lease["units"])
                    logger.debug(f"Lease {i+1}: Found units array with {len(lease['units'])} units")
                
                # Method 2: Check for single unit ID fields
                for field_name in ["unit_id", "unitId", "propertyUnitId", "unit", "unitIds"]:
                    if field_name in lease and lease[field_name]:
                        if isinstance(lease[field_name], list):
                            unit_ids.extend(lease[field_name])
                        else:
                            unit_ids.append(lease[field_name])
                        logger.debug(f"Lease {i+1}: Found {field_name} = {lease[field_name]}")
                
                # Add all found unit IDs to the set
                for unit_id in unit_ids:
                    if unit_id:  # Make sure it's not None or empty
                        occupied_unit_ids.add(str(unit_id))  # Convert to string for consistency
                
                if not unit_ids:
                    logger.debug(f"Lease {i+1}: No unit_id found. Available keys: {list(lease.keys())}")
                    # Log a sample of the lease data to understand structure
                    if i < 3:  # Only log first few for debugging
                        logger.debug(f"Lease {i+1} sample data: {str(lease)[:200]}...")
            
            occupied_count = len(occupied_unit_ids)
            logger.info(f"Total unique occupied units: {occupied_count}")
            logger.info(f"Sample occupied unit IDs: {list(occupied_unit_ids)[:5]}")  # Show first 5
            logger.info(f"Strategy used: {successful_strategy}")
            return occupied_count
            
        except Exception as e:
            logger.error(f"Error in get_occupied_units: {str(e)}")
            raise

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "DoorLoop Occupancy Rate API"}

@router.get("/debug-occupancy")
async def debug_occupancy_rate():
    """Debug endpoint to test occupancy rate calculation step by step"""
    
    if not DOORLOOP_API_KEY:
        return {"error": "DoorLoop API token not configured"}
    
    headers = get_doorloop_headers()
    debug_info = {}
    
    async with httpx.AsyncClient() as client:
        # Test 1: Check properties endpoint
        try:
            logger.info("DEBUG: Testing properties endpoint")
            response = await client.get(
                f"{DOORLOOP_BASE_URL}/properties",
                headers=headers,
                params={"limit": 5}  # Small limit for testing
            )
            
            debug_info["properties_test"] = {
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type", ""),
                "has_content": bool(response.content),
                "content_length": len(response.content) if response.content else 0,
                "response_preview": response.text[:200] if response.content else "No content"
            }
            
            if response.status_code == 200 and response.content:
                try:
                    data = response.json()
                    debug_info["properties_test"]["json_parse"] = "success"
                    debug_info["properties_test"]["data_keys"] = list(data.keys()) if isinstance(data, dict) else "not_dict"
                    debug_info["properties_test"]["data_count"] = len(data.get("data", [])) if isinstance(data, dict) else 0
                except Exception as json_error:
                    debug_info["properties_test"]["json_parse"] = f"failed: {str(json_error)}"
            
        except Exception as e:
            debug_info["properties_test"] = {"error": str(e)}
        
        # Test 2: Check leases endpoint
        try:
            logger.info("DEBUG: Testing leases endpoint")
            response = await client.get(
                f"{DOORLOOP_BASE_URL}/leases",
                headers=headers,
                params={"limit": 5}  # Small limit for testing
            )
            
            debug_info["leases_test"] = {
                "status_code": response.status_code,
                "content_type": response.headers.get("content-type", ""),
                "has_content": bool(response.content),
                "content_length": len(response.content) if response.content else 0,
                "response_preview": response.text[:200] if response.content else "No content"
            }
            
            if response.status_code == 200 and response.content:
                try:
                    data = response.json()
                    debug_info["leases_test"]["json_parse"] = "success"
                    debug_info["leases_test"]["data_keys"] = list(data.keys()) if isinstance(data, dict) else "not_dict"
                    debug_info["leases_test"]["data_count"] = len(data.get("data", [])) if isinstance(data, dict) else 0
                except Exception as json_error:
                    debug_info["leases_test"]["json_parse"] = f"failed: {str(json_error)}"
            
        except Exception as e:
            debug_info["leases_test"] = {"error": str(e)}
        
        # Test 3: Try alternative API base URLs
        alternative_bases = [
            "https://api.doorloop.com/v1",
            "https://api.doorloop.com",
            "https://app.doorloop.com/api/v1"
        ]
        
        debug_info["alternative_bases"] = {}
        
        for base_url in alternative_bases:
            try:
                test_response = await client.get(
                    f"{base_url}/properties",
                    headers=headers,
                    params={"limit": 1}
                )
                
                debug_info["alternative_bases"][base_url] = {
                    "status_code": test_response.status_code,
                    "content_type": test_response.headers.get("content-type", ""),
                    "has_content": bool(test_response.content),
                    "is_html": "text/html" in test_response.headers.get("content-type", "")
                }
                
            except Exception as e:
                debug_info["alternative_bases"][base_url] = {"error": str(e)}
    
    return {
        "message": "Occupancy rate debug information",
        "current_base_url": DOORLOOP_BASE_URL,
        "headers_used": headers,
        "debug_results": debug_info,
        "recommendations": [
            "Check if properties_test shows successful JSON parsing",
            "Check if leases_test shows successful JSON parsing", 
            "If both fail, the API token might be invalid or the base URL is wrong",
            "Try alternative base URLs if current one fails"
        ]
    }

@router.get("/units")
async def get_units_by_property(property_id: str):
    """Get all units for a specific property from Doorloop API."""
    units_url = f"{DOORLOOP_BASE_URL}/units"
    headers = get_doorloop_headers()
    
    logger.info(f"Making request to: {units_url}")
    
    params = {
        "filter_property": property_id
    }

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(units_url, headers=headers, params=params)
            resp.raise_for_status()
            
            logger.info(f"Successfully fetched units for property {property_id}")
            
            data = resp.json()
            
            # Get the actual units array from the response
            units = data.get('data', [])
            
            # Count unique units
            numOfUnits = set()
            for unit in units:
                if 'id' in unit:
                    numOfUnits.add(unit["id"])

            # Log the results
            logger.info(f"Unique unit IDs found: {numOfUnits}")
            logger.info(f"Total unique units for property {property_id}: {len(numOfUnits)}")
            
            return {
                "success": True,
                "numOfUnits": len(numOfUnits),
                "property_id": params["filter_property"],
                "units": list(numOfUnits),
                "total_units_returned": len(units),
                "raw_response_structure": list(data.keys()) if isinstance(data, dict) else "not_dict"
            }

        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP Error {e.response.status_code} for property {property_id}: {e.response.text}")
            return {
                "success": False,
                "status": e.response.status_code,
                "message": f"HTTP Error {e.response.status_code}",
                "error_details": e.response.text,
                "property_id": params["filter_property"]
            }
        

@router.get("/leases")
async def get_leases_by_property(
    property_id: str,
    start_date: str = None,
    end_date: str = None
):
    """Get all leases for a specific property from Doorloop API with optional date filtering.
    
    Args:
        property_id: The property ID to filter leases by
        date_from: Start date (YYYY-MM-DD) - optional
        date_to: End date (YYYY-MM-DD) - optional
    """
    # leases_url = f"{DOORLOOP_BASE_URL}/leases"
    # headers = get_doorloop_headers()
    
    # # Build base parameters
    # params = {
    #     "filter_property": property_id
    # }

    # start_date = datetime.strptime(start_date, "%Y-%m-%d")
    # end_date = datetime.strptime(end_date, "%Y-%m-%d")
    
    # async with httpx.AsyncClient() as client:
    #     try:
    #         resp = await client.get(leases_url, headers=headers, params=params)
    #         resp.raise_for_status()
            
    #         data = resp.json()

    #         units = defaultdict(list)
            
    #         for lease in data["data"]:
    #             lease_start_date = datetime.strptime(lease["start"], "%Y-%m-%d")
    #             lease_end_date = datetime.strptime(lease["end"], "%Y-%m-%d")

    #             if lease["id"] not in units:
                    
    #                 if lease_end_date < start_date:
    #                     continue

    #                 elif start_date < lease_start_date or lease_end_date < end_date:
    #                     total_days = end_date - start_date
    #                     remaining_days = (end_date - lease_end_date) + (lease_start_date - start_date)
    #                     days_occupied = total_days - remaining_days
    #                     occupied_percentage = (days_occupied / total_days) * 100
                        
    #                     units[lease["id"]].append(occupied_percentage) 

                    
    #                 elif lease_start_date <= start_date and end_date <= lease_end_date:
    #                     units[lease["id"]].append(100)
                
               

    #         logger.info(units)
    #         return {
    #             "success": True,
    #             "units": units
    #         }



            # percentSum = 0
            # total_units = len(units)
            # for unit in units:
            #     if len(units[unit]) > 1:
            #         percentSum += sum(units[unit]) / len(units[unit])
            #     else:
            #         percentSum += units[unit][0]

            
            # occupancy_rate_percentage_for_property = percentSum / total_units

            # return occupancy_rate_percentage_for_property
                    

    try:
        leases_url = f"{DOORLOOP_BASE_URL}/leases"
        headers = get_doorloop_headers()
        
        # Build base parameters
        params = {
            "filter_property": property_id
        }
        
        # Parse dates only if provided
        parsed_start_date = None
        parsed_end_date = None
        
        if start_date:
            try:
                parsed_start_date = datetime.strptime(start_date, "%Y-%m-%d")
            except ValueError:
                return {"success": False, "error": "Invalid start_date format. Use YYYY-MM-DD"}
        
        if end_date:
            try:
                parsed_end_date = datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                return {"success": False, "error": "Invalid end_date format. Use YYYY-MM-DD"}
        
        async with httpx.AsyncClient() as client:
            resp = await client.get(leases_url, headers=headers, params=params)
            resp.raise_for_status()
            data = resp.json()
            
            units = defaultdict(list)
            
            for lease in data["data"]:
                try:
                    lease_start_date = datetime.strptime(lease["start"], "%Y-%m-%d")
                    lease_end_date = datetime.strptime(lease["end"], "%Y-%m-%d")
                    
                    # If no date filtering, just add 100%
                    if not parsed_start_date or not parsed_end_date:
                        units[lease["id"]].append(100)
                        continue
                    
                    # Skip leases that end before our start date
                    if lease_end_date < parsed_start_date:
                        continue
                    
                    # Skip leases that start after our end date
                    if lease_start_date > parsed_end_date:
                        continue
                    
                    # Calculate overlap between lease period and requested period
                    overlap_start = max(lease_start_date, parsed_start_date)
                    overlap_end = min(lease_end_date, parsed_end_date)
                    
                    if overlap_start <= overlap_end:
                        total_days = (parsed_end_date - parsed_start_date).days
                        occupied_days = (overlap_end - overlap_start).days + 1  # +1 to include both dates
                        
                        if total_days > 0:
                            occupied_percentage = (occupied_days / total_days) * 100
                            units[lease["id"]].append(min(100, occupied_percentage))  # Cap at 100%
                
                except (KeyError, ValueError) as e:
                    logger.error(f"Error processing lease {lease.get('id', 'unknown')}: {e}")
                    continue
            
            logger.info(units)
            return {
                "success": True,
                "units": units
            }
            
    except httpx.HTTPError as e:
        logger.error(f"HTTP error: {e}")
        return {"success": False, "error": f"HTTP error: {str(e)}"}
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        return {"success": False, "error": f"Internal server error: {str(e)}"}
            

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP Error {e.response.status_code} for property {property_id}: {e.response.text}")
        return {
            "success": False,
            "status": e.response.status_code,
            "message": f"HTTP Error {e.response.status_code}",
            "error_details": e.response.text,
            "property_id": property_id,
            "date_range": {
                "date_from": start_date,
                "date_to": end_date
            } if start_date and end_date else None
        }



@router.get("/units/{unit_id}")
async def get_unit_by_id(unit_id: str):
    """Get a specific unit by ID from Doorloop API."""
    # Clean the unit ID - remove quotes if present
    clean_unit_id = unit_id.strip('"\'')
    
    unit_url = f"{DOORLOOP_BASE_URL}/units/{clean_unit_id}"
    headers = get_doorloop_headers()
    
    logger.info(f"Making request to: {unit_url}")
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(unit_url, headers=headers)
            resp.raise_for_status()
            
            # Check if response has content
            if not resp.content:
                logger.warning(f"Empty response for unit {clean_unit_id}")
                return {
                    "success": False,
                    "message": f"No data found for unit {clean_unit_id}",
                    "unit_id": clean_unit_id
                }
            
            # Check content type
            content_type = resp.headers.get("content-type", "")
            
            # Check if we got HTML (login page) instead of JSON
            if "text/html" in content_type:
                logger.warning("Received HTML response (likely login page)")
                return {
                    "success": False,
                    "message": "Received HTML response (likely login page)",
                    "content_type": content_type,
                    "suggestion": "This endpoint may not exist or requires different authentication"
                }
            
            # Try to parse JSON
            try:
                data = resp.json()
                logger.info(f"Successfully fetched unit {clean_unit_id} from Doorloop")
                return {
                    "success": True,
                    "data": data,
                    "unit_id": clean_unit_id
                }
            except ValueError as json_error:
                logger.error(f"Failed to parse JSON response for unit {clean_unit_id}: {json_error}")
                return {
                    "success": False,
                    "message": "Unit data received but not in JSON format",
                    "content_type": content_type,
                    "raw_response": resp.text[:1000]
                }
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP Error {e.response.status_code} for unit {clean_unit_id}: {e.response.text}")
            
            if e.response.status_code == 404:
                return {
                    "success": False,
                    "status": 404,
                    "message": f"Unit {clean_unit_id} not found",
                    "unit_id": clean_unit_id
                }
            else:
                return {
                    "success": False,
                    "status": e.response.status_code,
                    "message": f"HTTP Error {e.response.status_code}",
                    "error_details": e.response.text,
                    "unit_id": clean_unit_id
                }
                
        except Exception as e:
            logger.error(f"Unexpected error fetching unit {clean_unit_id}: {e}")
            return {
                "success": False,
                "message": f"Unexpected error: {str(e)}",
                "unit_id": clean_unit_id
            }
        




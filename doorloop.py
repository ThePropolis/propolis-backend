from collections import defaultdict
from datetime import datetime, timedelta
import logging
import asyncio
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
    accounting_method: str = "ACCRUAL"
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

def lease_overlaps_date_range(lease_start, lease_end, filter_start, filter_end):
    """
    Check if a lease overlaps with the given date range.
    Implements the same logic as the PHP code:
    - Lease starts within the date range, OR
    - Lease ends within the date range, OR  
    - Lease spans across the entire date range
    """
    
    if not lease_start:
        logger.debug(f"Lease missing start date - available fields: {list(lease.keys())}")
        return False
    
    try:

        
        # Check overlap conditions (same as PHP logic)
        # 1. Lease starts within the date range
        if filter_start <= lease_start <= filter_end:
            return True
        
        # 2. Lease ends within the date range (if end date exists)
        if lease_end and filter_start <= lease_end <= filter_end:
            logger.info(f"   ✅ Match: Lease ends within range")
            return True
        
        # 3. Lease spans across the entire date range
        if lease_end and lease_start < filter_start and filter_end < lease_end:
            logger.info(f"   ✅ Match: Lease spans entire range")
            return True
        
        # 4. For at-will leases (no end date) that started before the range end
        if not lease_end and lease_start <= filter_end:
            logger.info(f"   ✅ Match: At-will lease overlaps")
            return True
        
        # No match
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
    
    # Convert date format from MM-DD-YYYY to YYYY-MM-DD if needed
    def convert_date_format(date_str):
        if not date_str:
            return date_str
        
        # Check if date is in MM-DD-YYYY format
        if len(date_str) == 10 and date_str[2] == '-' and date_str[5] == '-':
            try:
                # Parse MM-DD-YYYY and convert to YYYY-MM-DD
                month, day, year = date_str.split('-')
                return f"{year}-{month.zfill(2)}-{day.zfill(2)}"
            except:
                pass
        
        # If already in YYYY-MM-DD format or other format, return as-is
        return date_str
    
    date_from = convert_date_format(date_from)
    date_to = convert_date_format(date_to)
    
    logger.info(f"Date range after conversion: {date_from} to {date_to}")
    
    headers = get_doorloop_headers()
    
    if property_id:
        logger.info(f"Calculating occupancy rate for property {property_id} from {date_from} to {date_to}")
        
        try:
            # Get total units for the specific property
            total_units = await get_units_by_property(property_id)
            logger.info(f"Property {property_id}: {total_units} total units")
            
            # Get occupied units for the specific property
            occupied_units = await get_leases_by_property(property_id, start_date=date_from, end_date=date_to)
            logger.info(f"Property {property_id}: {occupied_units} occupied units")
            
            # Calculate occupancy rate
            if total_units == 0:
                occupancy_rate = 0

            else:
                totalUnits = total_units["numOfUnits"]
                unitsDict = occupied_units.get("units", {})

                # Calculate occupancy rate correctly
                # unitsDict contains unit_id -> [occupancy_percentages] for each unit
                # We need to calculate: (sum of all unit occupancy percentages) / total_units
                
                total_occupancy_percentage = 0.0
                
                for unit_id, occupancy_percentages in unitsDict.items():
                    if occupancy_percentages:
                        # Calculate average occupancy for this unit across the time period
                        if len(occupancy_percentages) > 1:
                            unit_avg_occupancy = sum(occupancy_percentages) / len(occupancy_percentages)
                        else:
                            unit_avg_occupancy = occupancy_percentages[0]
                        
                        total_occupancy_percentage += unit_avg_occupancy
                
                # Final occupancy rate = total occupancy percentage / total units
                occupancy_rate_percentage_for_property = total_occupancy_percentage / totalUnits

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
            logger.info(f"=== DOORLOOP OCCUPANCY CALCULATION START ===")
            logger.info(f"Date range: {date_from} to {date_to}")
            try:
                logger.info(f"Calling get_total_units function...")
                total_units = await get_total_units(headers)
                logger.info(f"✅ get_total_units completed successfully: {total_units} total units")
                logger.info(f"Type of total_units: {type(total_units)}")
            except Exception as e:
                logger.error(f"❌ get_total_units failed with error: {str(e)}")
                logger.error(f"Error type: {type(e)}")
                import traceback
                logger.error(f"Full traceback: {traceback.format_exc()}")
                # Fallback to a default value
                total_units = 50
                logger.warning(f"Using fallback total_units: {total_units}")
            
            # Get occupied units from active leases
            occupied_units = await get_occupancy(date_from, date_to)
            logger.info(f"Found {occupied_units} occupied units")
            
            # Calculate occupancy rate
            if total_units == 0:
                occupancy_rate = 0
            else:
                occupancy_rate = (occupied_units / total_units) * 100
            
            logger.info(f"=== DOORLOOP OCCUPANCY CALCULATION RESULT ===")
            logger.info(f"Total units: {total_units}")
            logger.info(f"Occupied units: {occupied_units}")
            logger.info(f"Occupancy rate: {occupancy_rate:.2f}%")
            logger.info(f"=== END DOORLOOP CALCULATION ===")
            
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
            # Get all properties with pagination
            logger.info(f"Fetching properties from {DOORLOOP_BASE_URL}/properties")
            all_properties = []
            skip = 0
            limit = 1000
            
            while True:
                logger.info(f"Fetching properties page: skip={skip}, limit={limit}")
                response = await client.get(
                    f"{DOORLOOP_BASE_URL}/properties",
                    headers=headers,
                    params={"limit": limit, "skip": skip}
                )
            
                logger.info(f"Properties page response status: {response.status_code}")
                
                if response.status_code != 200:
                    logger.error(f"Failed to fetch properties: Status {response.status_code}, Response: {response.text}")
                    raise Exception(f"Failed to fetch properties: Status {response.status_code}")
                
                # Check if response has content
                if not response.content:
                    logger.warning("Empty response from properties endpoint")
                    break
                
                # Check content type
                content_type = response.headers.get("content-type", "")
                if "text/html" in content_type:
                    logger.warning("Received HTML response (likely login page) for properties")
                    raise Exception("Authentication failed - received HTML instead of JSON")
                
                # Try to parse JSON
                try:
                    properties_data = response.json()
                    logger.info(f"Successfully parsed properties JSON. Keys: {list(properties_data.keys()) if isinstance(properties_data, dict) else 'not_dict'}")
                except Exception as json_error:
                    logger.error(f"Failed to parse properties JSON: {json_error}")
                    logger.error(f"Response content preview: {response.text[:500]}")
                    raise Exception(f"Failed to parse properties JSON: {json_error}")
                
                page_properties = properties_data.get("data", [])
                logger.info(f"Found {len(page_properties)} properties on this page")
                
                if not page_properties:
                    logger.info("No more properties found. Pagination complete.")
                    break
                
                all_properties.extend(page_properties)
                
                # If we got fewer properties than the limit, we've reached the end
                if len(page_properties) < limit:
                    logger.info(f"Reached end of properties data. Total properties fetched: {len(all_properties)}")
                    break
                
                # Move to next page
                skip += limit
                
            properties = all_properties
            logger.info(f"Total properties fetched: {len(properties)}")
            
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
                    # Fetch all units for this property with pagination
                    property_units = []
                    units_skip = 0
                    units_limit = 1000
                    
                    while True:
                        units_response = await client.get(
                            f"{DOORLOOP_BASE_URL}/properties/{property_id}/units",
                            headers=headers,
                            params={"limit": units_limit, "skip": units_skip}
                        )
                        
                        logger.info(f"Units response for property {property_id} (page skip={units_skip}): Status {units_response.status_code}")
                        
                        if units_response.status_code == 200 and units_response.content:
                            content_type = units_response.headers.get("content-type", "")
                            if "text/html" not in content_type:
                                try:
                                    units_data = units_response.json()
                                    page_units = units_data.get("data", [])
                                    
                                    if not page_units:
                                        break
                                    
                                    property_units.extend(page_units)
                                    
                                    # If we got fewer units than the limit, we've reached the end
                                    if len(page_units) < units_limit:
                                        break
                                    
                                    # Move to next page
                                    units_skip += units_limit
                                    
                                except Exception as units_json_error:
                                    logger.error(f"Failed to parse units JSON for property {property_id}: {units_json_error}")
                                    break
                            else:
                                logger.warning(f"Got HTML response for units of property {property_id}")
                                break
                        else:
                            logger.warning(f"Failed to fetch units for property {property_id}: Status {units_response.status_code}")
                            break
                    
                    units_from_endpoints += len(property_units)
                    successful_property_requests += 1
                    logger.info(f"Property {property_id} has {len(property_units)} units (total)")
                        
                except Exception as units_error:
                    logger.error(f"Error fetching units for property {property_id}: {units_error}")
                    continue
            
            logger.info(f"Approach 1 result: {units_from_endpoints} units from {successful_property_requests}/{len(properties)} properties")
            
            # Approach 2: Try to get units from general units endpoint filtered by each property
            logger.info("Approach 2: Trying general units endpoint with property filters")
            units_from_general_endpoint = 0
            
            try:
                # For each property, get units using the general endpoint with property filter
                for i, property_data in enumerate(properties):
                    property_id = property_data.get("id")
                    if not property_id:
                        continue
                    
                    logger.info(f"Fetching units for property {property_id} via general endpoint ({i+1}/{len(properties)})")
                    
                    # Use the same pagination approach as get_units function
                    property_units = []
                    current_page = 1
                    
                    while True:
                        page_params = {"page": current_page, "filter_property": property_id}
                        
                        logger.info(f"Fetching units page {current_page} for property {property_id}")
                        general_units_response = await client.get(
                            f"{DOORLOOP_BASE_URL}/units",
                            headers=headers,
                            params=page_params
                        )
                        
                        logger.info(f"General units endpoint status (property {property_id}, page {current_page}): {general_units_response.status_code}")
                        
                        if general_units_response.status_code == 200 and general_units_response.content:
                            content_type = general_units_response.headers.get("content-type", "")
                            if "text/html" not in content_type:
                                try:
                                    general_units_data = general_units_response.json()
                                    page_general_units = general_units_data.get("data", [])
                                    
                                    if not page_general_units:
                                        break
                                    
                                    property_units.extend(page_general_units)
                                    
                                    logger.info(f"Property {property_id} - Page {current_page}: {len(page_general_units)} units (total so far: {len(property_units)})")
                                    
                                    # Check if this is the last page (same logic as get_units)
                                    if len(page_general_units) < 50:  # Doorloop's apparent page size
                                        break
                                    
                                    current_page += 1
                                    
                                except Exception as general_json_error:
                                    logger.error(f"Failed to parse general units JSON for property {property_id}: {general_json_error}")
                                    break
                            else:
                                logger.warning(f"General units endpoint returned HTML for property {property_id}")
                                break
                        else:
                            logger.info(f"General units endpoint not available for property {property_id} (status: {general_units_response.status_code})")
                            break
                    
                    units_from_general_endpoint += len(property_units)
                    logger.info(f"Property {property_id}: {len(property_units)} units via general endpoint")
                
                logger.info(f"General units endpoint returned {units_from_general_endpoint} units total across all properties")
                    
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
            logger.info(f"=== CHOOSING BEST APPROACH ===")
            logger.info(f"Approach 1 (property endpoints): {units_from_endpoints} units")
            logger.info(f"Approach 2 (general endpoint): {units_from_general_endpoint} units")
            logger.info(f"Approach 3 (property fields): {units_from_property_fields} units")
            
            if units_from_endpoints > 0:
                total_units = units_from_endpoints
                logger.info(f"✅ Using Approach 1 result: {total_units} units from property endpoints")
            elif units_from_general_endpoint > 0:
                total_units = units_from_general_endpoint
                logger.info(f"✅ Using Approach 2 result: {total_units} units from general endpoint")
            elif units_from_property_fields > 0:
                total_units = units_from_property_fields
                logger.info(f"✅ Using Approach 3 result: {total_units} units from property fields")
            else:
                logger.warning("❌ No units found with any approach")
                total_units = 0
            
            logger.info(f"=== END APPROACH SELECTION ===")
            
            logger.info(f"Final total units calculated: {total_units}")
            logger.info(f"=== TOTAL UNITS BREAKDOWN ===")
            logger.info(f"Approach 1 (property endpoints): {units_from_endpoints}")
            logger.info(f"Approach 2 (general endpoint): {units_from_general_endpoint}")
            logger.info(f"Approach 3 (property fields): {units_from_property_fields}")
            logger.info(f"=== END TOTAL UNITS BREAKDOWN ===")
            
            logger.info(f"About to return total_units: {total_units} (type: {type(total_units)})")
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
                },
                # Strategy 2: Filter by lease end date 
                {
                    "limit": 1000,
                    "filter_end_date_from": date_from,
                    "filter_end_date_to": date_to,
                },
                # Strategy 3: Just active leases without date filter (fallback)
                {
                    "limit": 1000,
                    
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
                
                # Implement pagination to get ALL leases
                all_leases = []
                skip = 0
                limit = 1000
                total_fetched = 0
                
                try:
                    while True:
                        # Add pagination parameters
                        paginated_params = params.copy()
                        paginated_params["limit"] = limit
                        paginated_params["skip"] = skip
                        
                        logger.info(f"Fetching page: skip={skip}, limit={limit}")
                        
                        try:
                            response = await client.get(
                                f"{DOORLOOP_BASE_URL}/leases",
                                headers=headers,
                                params=paginated_params
                            )
                            
                            logger.info(f"Strategy {strategy_name} - Page response status: {response.status_code}")
                            
                            if response.status_code == 200 and response.content:
                                content_type = response.headers.get("content-type", "")
                                if "text/html" not in content_type:
                                    try:
                                        page_data = response.json()
                                        page_leases = page_data.get("data", [])
                                        leases_count = len(page_leases)
                                        
                                        logger.info(f"Strategy {strategy_name} - Page returned {leases_count} leases")
                                        
                                        if leases_count > 0:
                                            all_leases.extend(page_leases)
                                            total_fetched += leases_count
                                            
                                            # If we got fewer leases than the limit, we've reached the end
                                            if leases_count < limit:
                                                logger.info(f"Reached end of data. Total leases fetched: {total_fetched}")
                                                break
                                            
                                            # Move to next page
                                            skip += limit
                                        else:
                                            logger.info(f"No more leases found. Total leases fetched: {total_fetched}")
                                            break
                                            
                                    except Exception as json_error:
                                        logger.error(f"Failed to parse leases JSON with strategy {strategy_name}: {json_error}")
                                        break
                                else:
                                    logger.warning(f"Strategy {strategy_name} returned HTML content instead of JSON")
                                    break
                            else:
                                logger.warning(f"Strategy {strategy_name} failed with status {response.status_code}")
                                break
                                
                        except Exception as request_error:
                            logger.error(f"Request error with strategy {strategy_name}: {request_error}")
                            break
                            
                except Exception as strategy_error:
                    logger.error(f"Strategy {strategy_name} failed completely: {strategy_error}")
                    all_leases = []  # Reset to empty list
                
                # If we got leases with this strategy, use it
                if all_leases:
                    leases_data = {"data": all_leases}
                    successful_strategy = strategy_name
                    logger.info(f"Successfully fetched {len(all_leases)} total leases with strategy: {strategy_name}")
                    
                    # If this is a date-filtered strategy and we got results, use it
                    if i <= 1 and len(all_leases) > 0:
                        break
                    # If this is a fallback strategy, use it only if no better option
                    elif i > 1:
                        break
                else:
                    logger.warning(f"Strategy {strategy_name} returned no leases")
            
            if not leases_data:
                logger.error("All lease request strategies failed")
                raise Exception("Failed to fetch leases with any parameter combination")
            
            logger.info(f"Using strategy: {successful_strategy}")
            logger.info(f"Leases response keys: {list(leases_data.keys()) if isinstance(leases_data, dict) else 'not_dict'}")
            
            leases = leases_data.get("data", [])
            logger.info(f"Found {len(leases)} total leases")
            
            # Debug: Show details of the leases found
            for i, lease in enumerate(leases[:5]):  # Show first 5 leases
                logger.info(f"Lease {i+1}: Status={lease.get('status')}, Start={lease.get('start')}, End={lease.get('end')}, ID={lease.get('id')}")
                logger.info(f"Lease {i+1} full data: {lease}")
            
            if not leases:
                logger.warning("No leases found")
                return 0
            
            # Count unique units that have active leases within the date range
            occupied_unit_ids = set()
            
            for i, lease in enumerate(leases):
                logger.info(f"Processing lease {i+1}/{len(leases)}: ID={lease.get('id')}, Status={lease.get('status')}")
                
                # Check if lease is within the date range (if we're using a fallback strategy)
                if successful_strategy in ["active_status_only", "no_filters"]:
                    # Manual date filtering for fallback strategies
                    # Try multiple date field combinations since DoorLoop data might be inconsistent
                    lease_start = lease.get("start") or lease.get("startDate") or lease.get("start_date") or lease.get("createdAt")
                    lease_end = lease.get("end") or lease.get("endDate") or lease.get("end_date") or lease.get("expiresAt") or lease.get("updatedAt")
                    
                    # Debug: Log the date fields we found
                    logger.info(f"Lease {i+1} date fields: start={lease_start}, end={lease_end}")
                    
                    # Validate that start date is before end date (if both exist)
                    if lease_start and lease_end:
                        try:
                            from datetime import datetime
                            start_dt = datetime.fromisoformat(lease_start.replace('Z', '+00:00'))
                            end_dt = datetime.fromisoformat(lease_end.replace('Z', '+00:00'))
                            if start_dt > end_dt:
                                logger.warning(f"Lease {i+1}: Invalid date range - start ({lease_start}) is after end ({lease_end}). Skipping this lease.")
                                continue
                        except Exception as date_parse_error:
                            logger.info(f"Could not parse dates for validation: {date_parse_error}")
                    
                    if lease_start:
                        try:
                            from datetime import datetime
                            lease_start_dt = datetime.fromisoformat(lease_start.replace('Z', '+00:00'))
                            date_from_dt = datetime.fromisoformat(f"{date_from}T00:00:00+00:00")
                            date_to_dt = datetime.fromisoformat(f"{date_to}T23:59:59+00:00")
                            
                            # Skip leases that don't overlap with our date range
                            logger.info(f"Lease {i+1}: Checking date overlap - lease_start={lease_start_dt}, lease_end={lease_end_dt if lease_end else 'None'}, date_range={date_from_dt} to {date_to_dt}")
                            
                            if lease_start_dt > date_to_dt:
                                logger.info(f"Lease {i+1}: Skipping - starts after date range ({lease_start_dt} > {date_to_dt})")
                                continue
                            if lease_end:
                                lease_end_dt = datetime.fromisoformat(lease_end.replace('Z', '+00:00'))
                                if lease_end_dt < date_from_dt:
                                    logger.info(f"Lease {i+1}: Skipping - ends before date range ({lease_end_dt} < {date_from_dt})")
                                    continue
                            
                            logger.info(f"Lease {i+1}: Date range check passed - lease overlaps with {date_from} to {date_to}")
                        except Exception as date_error:
                            logger.debug(f"Could not parse dates for lease {i+1}: {date_error}")
                            # Include the lease if we can't parse dates
                
                # Try different ways to extract unit IDs based on the actual data structure
                unit_ids = []
                
                # Method 1: Check if 'units' field contains an array of unit IDs
                if "units" in lease and isinstance(lease["units"], list):
                    unit_ids.extend(lease["units"])
                    logger.debug(f"Lease {i+1}: Found units array with {len(lease['units'])} units")
                
                # Method 2: Check for single unit ID fields (expanded list)
                unit_field_names = [
                    "unit_id", "unitId", "propertyUnitId", "unit", "unitIds",
                    "property_unit_id", "propertyUnit", "unitNumber", "unit_number",
                    "unitName", "unit_name", "unitCode", "unit_code",
                    "propertyId", "property_id", "propertyUnitNumber", "property_unit_number"
                ]
                
                for field_name in unit_field_names:
                    if field_name in lease and lease[field_name]:
                        if isinstance(lease[field_name], list):
                            unit_ids.extend(lease[field_name])
                        else:
                            unit_ids.append(lease[field_name])
                        logger.info(f"Lease {i+1}: Found {field_name} = {lease[field_name]}")
                
                # Method 3: Check if lease itself represents a unit (some APIs work this way)
                if not unit_ids and "id" in lease:
                    # If no unit fields found, maybe the lease ID itself represents a unit
                    unit_ids.append(lease["id"])
                    logger.info(f"Lease {i+1}: Using lease ID as unit ID: {lease['id']}")
                
                # Add all found unit IDs to the set
                for unit_id in unit_ids:
                    if unit_id:  # Make sure it's not None or empty
                        occupied_unit_ids.add(str(unit_id))  # Convert to string for consistency
                
                if not unit_ids:
                    logger.warning(f"Lease {i+1}: No unit_id found. Available keys: {list(lease.keys())}")
                    # Log a sample of the lease data to understand structure
                    if i < 5:  # Log first 5 for debugging
                        logger.warning(f"Lease {i+1} full data: {lease}")
                else:
                    logger.info(f"Lease {i+1}: Found {len(unit_ids)} units: {unit_ids}")
            
            occupied_count = len(occupied_unit_ids)
            logger.info(f"=== OCCUPANCY CALCULATION SUMMARY ===")
            logger.info(f"Total leases processed: {len(leases)} (with pagination)")
            logger.info(f"Total unique occupied units: {occupied_count}")
            logger.info(f"Strategy used: {successful_strategy}")
            logger.info(f"Sample occupied unit IDs: {list(occupied_unit_ids)[:10]}")  # Show first 10
            logger.info(f"All occupied unit IDs: {sorted(list(occupied_unit_ids))}")
            
            # If we got very few units and used a date-filtered strategy, warn about potential issues
            if occupied_count < 20 and successful_strategy in ["lease_start_date_filter", "lease_end_date_filter"]:
                logger.warning(f"Low unit count ({occupied_count}) with date-filtered strategy. This might indicate:")
                logger.warning(f"1. Date filtering is too restrictive")
                logger.warning(f"2. Lease data structure issues")
                logger.warning(f"3. Unit ID extraction problems")
            
            logger.info(f"=== END SUMMARY ===")
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


@router.get("/units")
async def get_units(
    property_id: str = None,
    status: str = None,
    unit_type: str = None,
    page: int = 1,
    fetch_all: bool = False
):
    """Get units from Doorloop API with optional filtering.
    
    Args:
        property_id: Filter by specific property ID
        status: Filter by unit status (e.g., 'available', 'occupied', 'maintenance')
        unit_type: Filter by unit type
        page: Page number (default: 1) - Note: Doorloop controls page size
        fetch_all: If True, fetches all pages and returns combined results
    """
    units_url = f"{DOORLOOP_BASE_URL}/units"
    headers = get_doorloop_headers()
    
    # Build query parameters (Doorloop controls pagination)
    params = {}
    
    # Add page parameter (let Doorloop control page size)
    if not fetch_all:
        params["page"] = page
    
    # Add optional filters
    if property_id:
        params["property_id"] = property_id
    if status:
        params["status"] = status
    if unit_type:
        params["unit_type"] = unit_type
    
    logger.info(f"Making request to: {units_url} with params: {params}")
    
    if fetch_all:
        # Fetch all pages
        all_units = []
        current_page = 1
        total_count = 0
        
        async with httpx.AsyncClient() as client:
            while True:
                page_params = {**params, "page": current_page}
                
                try:
                    logger.info(f"Fetching page {current_page}")
                    resp = await client.get(units_url, headers=headers, params=page_params)
                    resp.raise_for_status()
                    
                    if not resp.content:
                        break
                    
                    data = resp.json()
                    page_units = data.get('data', [])
                    
                    if not page_units:
                        break
                    
                    all_units.extend(page_units)
                    total_count = data.get('total', len(all_units))
                    
                    logger.info(f"Page {current_page}: {len(page_units)} units (total so far: {len(all_units)})")
                    
                    # Check if this is the last page
                    if len(page_units) < 50:  # Doorloop's apparent page size
                        break
                    
                    current_page += 1
                    
                except Exception as e:
                    logger.error(f"Error fetching page {current_page}: {e}")
                    break
        
        return {
            "success": True,
            "data": all_units,
            "pagination": {
                "fetch_all": True,
                "total_pages_fetched": current_page,
                "total_units": len(all_units),
                "doorloop_reported_total": total_count
            },
            "filters_applied": {
                "property_id": property_id,
                "status": status,
                "unit_type": unit_type
            },
            "summary": {
                "total_units_fetched": len(all_units)
            }
        }
    
    else:
        # Single page request
        async with httpx.AsyncClient() as client:
            try:
                resp = await client.get(units_url, headers=headers, params=params)
                
                # Log response details for debugging
                logger.info(f"Units API response status: {resp.status_code}")
                logger.info(f"Units API response headers: {dict(resp.headers)}")
                
                resp.raise_for_status()
                
                # Check if response has content
                if not resp.content:
                    logger.warning("Empty response from Doorloop units API")
                    return {
                        "success": True,
                        "message": "No units data available", 
                        "data": [],
                        "pagination": {
                            "page": page,
                            "units_on_page": 0,
                            "total": 0,
                            "note": "Doorloop controls pagination - actual page size may vary"
                        },
                        "filters_applied": {
                            "property_id": property_id,
                            "status": status,
                            "unit_type": unit_type
                        }
                    }
                
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
                    units = data.get('data', [])
                    total_count = data.get('total', 0)
                    
                    # Doorloop's actual page size (discovered from response)
                    actual_page_size = len(units)
                    
                    logger.info(f"Successfully fetched {len(units)} units from Doorloop (page {page})")
                    logger.info(f"Doorloop's actual page size: {actual_page_size}")
                    logger.info(f"Doorloop reported total: {total_count}")
                    
                    # Calculate pagination info based on Doorloop's actual behavior
                    estimated_page_size = 50  # Doorloop's apparent default
                    if total_count > 0:
                        estimated_total_pages = (total_count + estimated_page_size - 1) // estimated_page_size
                        has_next = page < estimated_total_pages
                        has_prev = page > 1
                    else:
                        estimated_total_pages = 1
                        has_next = actual_page_size >= estimated_page_size  # Might have more if page is full
                        has_prev = page > 1
                    
                    return {
                        "success": True,
                        "data": units,
                        "pagination": {
                            "page": page,
                            "units_on_page": actual_page_size,
                            "total": total_count,
                            "estimated_total_pages": estimated_total_pages,
                            "has_next": has_next,
                            "has_prev": has_prev,
                            "next_page": page + 1 if has_next else None,
                            "prev_page": page - 1 if has_prev else None,
                            "doorloop_page_size": actual_page_size,
                            "note": "Doorloop controls pagination - page size is determined by Doorloop API"
                        },
                        "filters_applied": {
                            "property_id": property_id,
                            "status": status,
                            "unit_type": unit_type
                        },
                        "summary": {
                            "units_on_page": actual_page_size,
                            "total_units": total_count
                        }
                    }
                    
                except ValueError as json_error:
                    logger.error(f"Failed to parse JSON response: {json_error}")
                    logger.error(f"Response content preview: {resp.text[:500]}")
                    return {
                        "success": False,
                        "message": "Units data received but not in JSON format",
                        "content_type": content_type,
                        "raw_response": resp.text[:1000]
                    }
                    
            except httpx.HTTPStatusError as e:
                logger.error(f"HTTP Error {e.response.status_code} for units: {e.response.text}")
                
                if e.response.status_code == 400:
                    try:
                        error_data = e.response.json()
                        return {
                            "success": False,
                            "status": 400,
                            "message": "Bad Request - Invalid parameters",
                            "error_details": error_data,
                            "parameters_sent": params,
                            "suggestion": "Check if the filter parameters are valid"
                        }
                    except:
                        return {
                            "success": False,
                            "status": 400,
                            "message": "Bad Request",
                            "error_text": e.response.text,
                            "parameters_sent": params
                        }
                elif e.response.status_code == 404:
                    return {
                        "success": False,
                        "status": 404,
                        "message": "Units endpoint not found",
                        "suggestion": "The /units endpoint may not be available in your Doorloop plan"
                    }
                else:
                    return {
                        "success": False,
                        "status": e.response.status_code,
                        "message": f"HTTP Error {e.response.status_code}",
                        "error_details": e.response.text
                    }
                            
            except Exception as e:
                logger.error(f"Unexpected error fetching units: {e}")
                return {
                    "success": False,
                    "message": f"Unexpected error: {str(e)}",
                    "error_type": type(e).__name__
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



# @router.get("/occupancy")
async def get_occupancy(
        date_start: str,
        date_end: str,
        property_id: str = None
    ):

    overlapped_leases = []
    
    # Parse the target date range
    date_start_dt = datetime.strptime(date_start, "%Y-%m-%d")
    date_end_dt = datetime.strptime(date_end, "%Y-%m-%d")
    
    logger.info(f"Fetching leases that overlap with {date_start} to {date_end}")

    async with httpx.AsyncClient() as client:
        try: 
            headers = get_doorloop_headers()
            
            # If property_id is specified, fetch only that property
            if property_id:
                properties_to_fetch = [{"id": property_id, "name": "Specified Property"}]
            else:
                # Fetch all properties first
                properties_response = await client.get(f"{DOORLOOP_BASE_URL}/properties", headers=headers)
                properties_response.raise_for_status()
                properties_data = properties_response.json()
                properties_to_fetch = properties_data.get('data', [])
                logger.info(f"Found {len(properties_to_fetch)} properties to fetch leases from")
            
            # Fetch leases from each property individually
            for prop in properties_to_fetch:
                prop_id = prop.get('id')
                prop_name = prop.get('name', 'Unknown')
                
                if not prop_id:
                    continue
                
                logger.info(f"Fetching leases for property: {prop_name} (ID: {prop_id})")
                
                # Use two queries per property to catch both fixed-term and at-will leases
                all_property_leases = []
                
                # Query 1: Fixed-term leases with end date filters
                params_fixed = {
                    "filter_property": prop_id,
                    "filter_start_date_from": "2020-01-01",
                    "filter_start_date_to": date_end,
                    "filter_end_date_from": date_start,
                    "filter_end_date_to": "2030-12-31",
                }
                
                # Query 2: At-will leases (no end date filters)
                params_at_will = {
                    "filter_property": prop_id,
                    "filter_start_date_from": "2020-01-01",
                    "filter_start_date_to": date_end,
                }
                
                try:
                    # Get fixed-term leases
                    response1 = await client.get(
                        f"{DOORLOOP_BASE_URL}/leases", 
                        headers=headers,
                        params=params_fixed
                    )
                    response1.raise_for_status()
                    data1 = response1.json()
                    fixed_term_leases = data1.get('data', [])
                    
                    # Get at-will leases
                    response2 = await client.get(
                        f"{DOORLOOP_BASE_URL}/leases", 
                        headers=headers,
                        params=params_at_will
                    )
                    response2.raise_for_status()
                    data2 = response2.json()
                    at_will_candidates = data2.get('data', [])
                    
                    # Filter at-will candidates to only include actual at-will leases
                    at_will_leases = []
                    for lease in at_will_candidates:
                        lease_end = lease.get('end', '')
                        if not lease_end or lease_end == 'AtWill' or lease_end == 'N/A':
                            at_will_leases.append(lease)
                    
                    # Combine both sets
                    all_property_leases = fixed_term_leases + at_will_leases
                    
                    logger.info(f"Property {prop_name}: {len(fixed_term_leases)} fixed-term + {len(at_will_leases)} at-will = {len(all_property_leases)} total")
                    
                    # Process leases from this property
                    for lease in all_property_leases:
                        # Extract lease dates
                        lease_start_str = lease.get('start', '')
                        lease_end_str = lease.get('end', '')
                        
                        # Skip leases without start dates
                        if not lease_start_str:
                            logger.debug(f"Skipping lease {lease.get('id', 'no-id')} - no start date")
                            continue
                        
                        try:
                            # Parse start date
                            lease_start_dt = datetime.strptime(lease_start_str, "%Y-%m-%d")
                            
                            # Handle at-will leases (no end date, "AtWill", or "N/A")
                            if not lease_end_str or lease_end_str == 'AtWill' or lease_end_str == 'N/A':
                                # At-will lease - overlaps if started before or during the period
                                if lease_start_dt <= date_end_dt:
                                    overlapped_leases.append(lease)
                                    logger.info(f"✅ At-will lease {lease.get('id', 'no-id')} overlaps: {lease_start_str} (no end date)")
                                else:
                                    logger.debug(f"❌ At-will lease {lease.get('id', 'no-id')} doesn't overlap: {lease_start_str} (no end date)")
                            else:
                                # Fixed-term lease - parse end date and check overlap
                                lease_end_dt = datetime.strptime(lease_end_str, "%Y-%m-%d")
                                
                                # Check if lease overlaps with the date range
                                # Lease overlaps if: lease_start <= date_end AND lease_end >= date_start
                                if lease_overlaps_date_range(lease_start_dt, lease_end_dt, date_start_dt, date_end_dt):
                                    overlapped_leases.append(lease) 
                                    logger.info(f"✅ Fixed-term lease {lease.get('id', 'no-id')} overlaps: {lease_start_str} to {lease_end_str}")
                                else:
                                    logger.debug(f"❌ Fixed-term lease {lease.get('id', 'no-id')} doesn't overlap: {lease_start_str} to {lease_end_str}")
                                
                        except ValueError as e:
                            logger.warning(f"Invalid date format in lease {lease.get('id', 'no-id')}: {e}")
                            continue
                    
                    # Small delay between property requests
                    await asyncio.sleep(0.1)
                    
                except httpx.HTTPStatusError as e:
                    if e.response.status_code == 429:
                        logger.warning(f"Rate limit hit for property {prop_name}. Stopping.")
                        break
                    else:
                        logger.error(f"HTTP error {e.response.status_code} for property {prop_name}: {e}")
                except Exception as e:
                    logger.error(f"Error fetching leases for property {prop_name}: {e}")
                
        except Exception as e:
            logger.error(f"Error in get_occupancy: {e}")

    logger.info(f"{len(overlapped_leases)} leases that overlap with {date_start} to {date_end}")
    return int(len(overlapped_leases))
        




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

@router.get("/occupancy-rate-doorloop")
async def get_occupancy_rate(
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
):
    """
    Calculate occupancy rate: (occupied units / total units) * 100
    
    Parameters:
    - date_from: Start date (YYYY-MM-DD) - defaults to current month start
    - date_to: End date (YYYY-MM-DD) - defaults to current month end
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
    
    logger.info(f"Calculating occupancy rate from {date_from} to {date_to}")
    
    try:
        # Get total units from properties
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
        logger.error(f"Error calculating occupancy rate: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error calculating occupancy rate: {str(e)}")

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
            
            # Try with different parameter combinations since we're not sure of the exact API format
            params_to_try = [
                {
                    "limit": 1000,
                    "status": "active",
                    "start_date_from": date_from,
                    "start_date_to": date_to
                },
                {
                    "limit": 1000,
                    "status": "active"
                },
                {
                    "limit": 1000
                }
            ]
            
            leases_data = None
            for i, params in enumerate(params_to_try):
                logger.info(f"Trying leases request {i+1} with params: {params}")
                
                response = await client.get(
                    f"{DOORLOOP_BASE_URL}/leases",
                    headers=headers,
                    params=params
                )
                
                logger.info(f"Leases response status: {response.status_code}")
                logger.info(f"Leases response content type: {response.headers.get('content-type', '')}")
                logger.info(f"Leases response has content: {bool(response.content)}")
                
                if response.status_code == 200 and response.content:
                    content_type = response.headers.get("content-type", "")
                    if "text/html" not in content_type:
                        try:
                            leases_data = response.json()
                            logger.info(f"Successfully parsed leases JSON with params {i+1}")
                            break
                        except Exception as json_error:
                            logger.error(f"Failed to parse leases JSON with params {i+1}: {json_error}")
                            continue
                else:
                    logger.warning(f"Request {i+1} failed with status {response.status_code}")
            
            if not leases_data:
                logger.error("All lease request attempts failed")
                raise Exception("Failed to fetch leases with any parameter combination")
            
            logger.info(f"Successfully parsed leases JSON. Keys: {list(leases_data.keys()) if isinstance(leases_data, dict) else 'not_dict'}")
            
            leases = leases_data.get("data", [])
            logger.info(f"Found {len(leases)} leases")
            
            if not leases:
                logger.warning("No leases found")
                return 0
            
            # Count unique units that have active leases
            occupied_unit_ids = set()
            
            for i, lease in enumerate(leases):
                logger.debug(f"Processing lease {i+1}/{len(leases)}")
                
                # Try different ways to extract unit IDs based on the actual data structure
                unit_ids = []
                
                # Method 1: Check if 'units' field contains an array of unit IDs
                if "units" in lease and isinstance(lease["units"], list):
                    unit_ids.extend(lease["units"])
                    logger.debug(f"Lease {i+1}: Found units array with {len(lease['units'])} units")
                
                # Method 2: Check for single unit ID fields
                for field_name in ["unit_id", "unitId", "propertyUnitId", "unit"]:
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
async def get_units():
    """Get all units from Doorloop API."""
    units_url = f"{DOORLOOP_BASE_URL}/units"
    headers = get_doorloop_headers()
    
    logger.info(f"Making request to: {units_url}")
    
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(units_url, headers=headers)
            resp.raise_for_status()
            
            # Check if response has content
            if not resp.content:
                logger.warning("Empty response from Doorloop units API")
                return {"message": "No units data available", "data": []}
            
            # Check content type
            content_type = resp.headers.get("content-type", "")
            logger.info(f"Response content type: {content_type}")
            
            # Check if we got HTML (login page) instead of JSON
            if "text/html" in content_type:
                logger.warning("Received HTML response (likely login page)")
                return {
                    "message": "Received HTML response (likely login page)",
                    "content_type": content_type,
                    "suggestion": "This endpoint may not exist or requires different authentication"
                }
            
            # Try to parse JSON
            try:
                data = resp.json()
                logger.info(f"Successfully fetched {len(data.get('data', []))} units from Doorloop")
                return data
            except ValueError as json_error:
                logger.error(f"Failed to parse JSON response: {json_error}")
                return {
                    "message": "Units data received but not in JSON format",
                    "content_type": content_type,
                    "raw_response": resp.text
                }
                
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP Error {e.response.status_code} for units: {e.response.text}")
            if e.response.status_code == 404:
                raise HTTPException(status_code=404, detail="Units endpoint not found")
            raise HTTPException(status_code=502, detail=f"Failed to fetch units from Doorloop: {e.response.status_code}") from e
        except Exception as e:
            logger.error(f"Unexpected error fetching units: {e}")
            raise HTTPException(status_code=500, detail="Internal server error") from e


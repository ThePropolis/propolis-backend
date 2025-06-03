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
    accounting_method: str = "cash",
    start_date: str = None,
    end_date: str = None
):
    """Get profit and loss summary from Doorloop API.
    
    Args:
        accounting_method: Accounting method - typically 'cash' or 'accrual'
        start_date: Start date for the report (YYYY-MM-DD format)
        end_date: End date for the report (YYYY-MM-DD format)
    """
    pl_url = f"{DOORLOOP_BASE_URL}/reports/profit-and-loss-summary"
    headers = get_doorloop_headers()
    
    # Try different parameter formats that Doorloop might expect
    params_variations = [
        # Variation 1: filter_accountingMethod
        {
            "filter_accountingMethod": accounting_method
        },
        # Variation 2: accountingMethod
        {
            "accountingMethod": accounting_method
        },
        # Variation 3: accounting_method
        {
            "accounting_method": accounting_method
        },
        # Variation 4: filter[accountingMethod]
        {
            "filter[accountingMethod]": accounting_method
        }
    ]
    
    # Add date filters to each variation if provided
    for params in params_variations:
        if start_date:
            params.update({
                "filter_startDate": start_date,
                "startDate": start_date,
                "start_date": start_date
            })
        if end_date:
            params.update({
                "filter_endDate": end_date,
                "endDate": end_date,
                "end_date": end_date
            })
    
    async with httpx.AsyncClient() as client:
        # Try each parameter variation
        for i, params in enumerate(params_variations):
            try:
                logger.info(f"Trying parameter variation {i+1}: {params}")
                resp = await client.get(pl_url, headers=headers, params=params)
                
                if resp.status_code == 200:
                    content_type = resp.headers.get("content-type", "")
                    logger.info(f"Success with variation {i+1}! Content type: {content_type}")
                    
                    # Check if we got HTML (login page) instead of JSON
                    if "text/html" in content_type:
                        logger.warning("Received HTML response (likely login page)")
                        continue
                    
                    # Try to parse JSON
                    try:
                        data = resp.json()
                        logger.info("Successfully fetched profit and loss data from Doorloop")
                        return {
                            "success": True,
                            "parameters_used": params,
                            "variation_number": i+1,
                            "data": data
                        }
                    except ValueError as json_error:
                        logger.error(f"Failed to parse JSON response: {json_error}")
                        continue
                        
                elif resp.status_code == 400:
                    logger.info(f"Variation {i+1} failed with 400: {resp.text}")
                    continue
                else:
                    logger.info(f"Variation {i+1} failed with status {resp.status_code}")
                    continue
                    
            except Exception as e:
                logger.warning(f"Error with variation {i+1}: {e}")
                continue
    
    # If all variations failed, return detailed error info
    return {
        "error": "All parameter variations failed",
        "tried_variations": params_variations,
        "suggestion": "The API might require additional parameters or different authentication",
        "next_steps": [
            "Check Doorloop API documentation for exact parameter names",
            "Try using browser dev tools to see the exact request format",
            "Contact Doorloop support for API parameter specifications"
        ]
    }

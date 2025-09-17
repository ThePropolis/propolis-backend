from datetime import datetime
import os
from fastapi import APIRouter, FastAPI, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from database import supabase

router = APIRouter()

class ListingPicture(BaseModel):
    full_url: str
    thumbnail_url: Optional[str] = None
    caption: Optional[str] = None
    display_order: int

class GuestyListing(BaseModel):
    id: str = Field(..., description="Primary key, text")
    account_id: str
    created_at: datetime
    last_updated_at: Optional[datetime] = None
    imported_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None

    title: Optional[str] = None
    nickname: Optional[str] = None
    property_type: Optional[str] = None
    room_type: Optional[str] = None

    accommodates: Optional[int] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    area_square_feet: Optional[float] = None
    minimum_age: Optional[int] = None

    complex_id: Optional[str] = None
    cleaning_status: Optional[str] = None
    active: Optional[str] = None

    address_building_name: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = None
    address_neighborhood: Optional[str] = None
    address_latitude: Optional[str] = None
    address_longitude: Optional[str] = None
    address_full: Optional[str] = None

    thumbnail_url: Optional[str] = None

    base_price: Optional[float] = None
    currency: Optional[str] = None
    weekly_price_factor: Optional[float] = None
    monthly_price_factor: Optional[float] = None
    extra_person_fee: Optional[float] = None
    security_deposit_fee: Optional[float] = None

    guests_included: Optional[int] = None
    min_nights: Optional[int] = None
    max_nights: Optional[int] = None

    description_summary: Optional[str] = None

    payment_provider_id: Optional[str] = None
    account_taxes: Optional[Dict[str, Any]] = None
    tags: List[str] = []
    amenities: List[str] = []

class DetailedListing(BaseModel):
    """Extended listing model with detailed picture information"""
    # Inherit all basic fields
    id: str
    account_id: Optional[str] = None
    created_at: Optional[datetime] = None
    last_updated_at: Optional[datetime] = None
    imported_at: Optional[datetime] = None
    last_activity_at: Optional[datetime] = None

    title: Optional[str] = None
    nickname: Optional[str] = None
    property_type: Optional[str] = None
    room_type: Optional[str] = None

    accommodates: Optional[int] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    area_square_feet: Optional[float] = None
    minimum_age: Optional[int] = None

    complex_id: Optional[str] = None
    cleaning_status: Optional[str] = None
    active: Optional[str] = None

    address_building_name: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = None
    address_neighborhood: Optional[str] = None
    address_latitude: Optional[str] = None
    address_longitude: Optional[str] = None
    address_full: Optional[str] = None

    thumbnail_url: Optional[str] = None

    base_price: Optional[float] = None
    currency: Optional[str] = None
    weekly_price_factor: Optional[float] = None
    monthly_price_factor: Optional[float] = None
    extra_person_fee: Optional[float] = None
    security_deposit_fee: Optional[float] = None

    guests_included: Optional[int] = None
    min_nights: Optional[int] = None
    max_nights: Optional[int] = None

    description_summary: Optional[str] = None

    payment_provider_id: Optional[str] = None
    account_taxes: Optional[Dict[str, Any]] = None
    tags: List[str] = []
    amenities: List[str] = []
    
    # Enhanced picture information
    pictures: List[str] = []  # Array of full_url strings for backward compatibility
    detailed_pictures: List[ListingPicture] = []  # Detailed picture objects with metadata

@router.get("/api/properties/listings/{listing_id}",
    response_model=DetailedListing,
    summary="Get a specific property with detailed picture information"
)
def get_property_by_id(listing_id: str) -> Dict[str, Any]:
    """
    Get a specific property by ID with detailed picture information from jd_listing_pictures table.
    
    This endpoint joins jd_listing with jd_listing_pictures using listing_id as the key
    and returns full_url, caption, and display_order for each picture.
    """
    # Fetch the specific listing
    listing_res = (
        supabase
        .table("jd_listing")
        .select("*")
        .eq("id", listing_id)
        .execute()
    )
    
    if not listing_res.data:
        raise HTTPException(status_code=404, detail=f"Property with ID '{listing_id}' not found")
    
    listing = listing_res.data[0]
    
    # Fetch pictures for this specific listing from jd_listing_pictures table
    pictures_res = (
        supabase
        .table("jd_listing_pictures")
        .select("full_url, thumbnail_url, caption, display_order")
        .eq("listing_id", listing_id)
        .order("display_order")
        .execute()
    )
    
    # Process pictures data
    detailed_pictures = []
    picture_urls = []
    
    if pictures_res.data:
        for pic in pictures_res.data:
            if pic["full_url"]:  # Only include pictures with valid full_url
                detailed_pictures.append({
                    "full_url": pic["full_url"],
                    "thumbnail_url": pic.get("thumbnail_url"),
                    "caption": pic.get("caption"),
                    "display_order": pic.get("display_order", 0)
                })
                picture_urls.append(pic["full_url"])
    
    # If no pictures found in jd_listing_pictures, fallback to thumbnail_url
    if not picture_urls and listing.get("thumbnail_url"):
        picture_urls = [listing["thumbnail_url"]]
        detailed_pictures = [{
            "full_url": listing["thumbnail_url"],
            "thumbnail_url": listing["thumbnail_url"],
            "caption": "Property thumbnail",
            "display_order": 0
        }]
    
    # Add picture data to listing
    listing["pictures"] = picture_urls
    listing["detailed_pictures"] = detailed_pictures
    
    return listing

@router.get("/api/properties/listings",
    response_model=List[GuestyListing],
    summary="Get all properties with pictures"
)
def get_reservations() -> List[Dict]:
    # Fetch listings with their associated pictures
    listings_res = (
        supabase
        .table("jd_listing")
        .select("*")
        .execute()
    )
    
    if not listings_res.data:
        return []
    
    # Fetch ALL pictures in a single query instead of N+1 queries
    all_pictures_res = (
        supabase
        .table("jd_listing_pictures")
        .select("listing_id, full_url, thumbnail_url, caption, display_order")
        .order("listing_id, display_order")
        .execute()
    )
    
    # Group pictures by listing_id
    pictures_by_listing = {}
    if all_pictures_res.data:
        for pic in all_pictures_res.data:
            listing_id = pic["listing_id"]
            if listing_id not in pictures_by_listing:
                pictures_by_listing[listing_id] = []
            pictures_by_listing[listing_id].append(pic)
    
    # Add pictures to each listing
    for listing in listings_res.data:
        listing_pictures = pictures_by_listing.get(listing["id"], [])
        
        if listing_pictures:
            # Use full_url (original quality) instead of thumbnail
            listing["pictures"] = [pic["full_url"] for pic in listing_pictures if pic["full_url"]]
        else:
            # Fallback to thumbnail_url if no pictures found
            listing["pictures"] = [listing["thumbnail_url"]] if listing.get("thumbnail_url") else []

    return listings_res.data or []

@router.get("/db/units-for-property")
async def get_units_for_property(
    property: str = Query(..., description="Property name (required)")
):
    """Get all units for a specific property from Supabase"""
    try:
        # Enhanced debugging for deployment issues
        print(f"🔍 Environment check - SUPABASE_URL exists: {bool(os.getenv('SUPABASE_URL'))}")
        print(f"🔍 Environment check - SUPABASE_KEY exists: {bool(os.getenv('SUPABASE_KEY'))}")
        
        # Parse property name to remove "Apartments" suffix
        parsed_property = property.replace(" Apartments", "").replace("Apartments", "")
        print(f"🔍 Original property: {property}")
        print(f"🔍 Parsed property: {parsed_property}")
        
        # Test database connection first
        try:
            test_response = supabase.table("STR-Jul-2025").select("Property").limit(1).execute()
            print(f"🔍 Database connection test successful")
        except Exception as db_test_error:
            print(f"❌ Database connection test failed: {str(db_test_error)}")
            raise HTTPException(status_code=500, detail=f"Database connection failed: {str(db_test_error)}")
        
        # Build the query step by step
        query = supabase.table("STR-Jul-2025").select("Unit")
        query = query.eq("Property", parsed_property)
        
        print(f"🔍 Executing query...")
        response = query.execute()
        
        print(f"🔍 Response received: {len(response.data) if response.data else 0} units found")
        
        # Additional debugging - check if table exists and has data
        if not response.data:
            # Try to get all properties to see what's available
            all_props_response = supabase.table("STR-Jul-2025").select("Property").execute()
            available_properties = list(set([prop.get("Property") for prop in (all_props_response.data or []) if prop.get("Property")]))
            print(f"🔍 Available properties in database: {available_properties[:10]}")  # Show first 10
            print(f"🔍 Total properties in database: {len(available_properties)}")
        
        return {
            "data": response.data or [],
            "count": len(response.data) if response.data else 0,
            "property": property,
            "parsed_property": parsed_property,
            "debug_info": {
                "database_connected": True,
                "table_exists": bool(response.data is not None),
                "available_properties_count": len(set([prop.get("Property") for prop in (supabase.table("STR-Jul-2025").select("Property").execute().data or []) if prop.get("Property")])) if response.data is not None else 0
            }
        }
    except Exception as e:
        print(f"❌ Error in get_units_for_property: {str(e)}")
        print(f"❌ Error type: {type(e)}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")


@router.get("/db/unit-filtering")
async def get_unit_filtering_data(
    property: str = Query(..., description="Property name (required)"),
    unit: str = Query(..., description="Unit name (required)")
):
    """Get unit filtering data from Supabase with mandatory property and unit filters"""
    try:
        # Parse property name to remove "Apartments" suffix
        parsed_property = property.replace(" Apartments", "").replace("Apartments", "")
        print(f"🔍 Original property: {property}")
        print(f"🔍 Parsed property: {parsed_property}")
        print(f"🔍 Unit: {unit}")
        
        response = supabase.table("STR-Jul-2025").select("Property, Unit, Revenue").eq("Property", parsed_property).eq("Unit", unit).execute()
        
        print(f"🔍 Response received: {len(response.data) if response.data else 0} records found")
        
        return {
            "data": response.data,
            "count": len(response.data),
            "filters_applied": {
                "property": property,
                "parsed_property": parsed_property,
                "unit": unit
            }
        }
    except Exception as e:
        print(f"❌ Error in get_unit_filtering_data: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/db/rent-paid-units")
async def get_rent_paid_units(
    property: str = Query(..., description="Property name (required)")
):
    """Get all units and their total paid amounts for a specific property from Rent-Paid-July-2025 table"""
    try:
        # Parse property name to remove "Apartments" suffix
        parsed_property = property.replace(" Apartments", "").replace("Apartments", "")
        print(f"🔍 Original property: {property}")
        print(f"🔍 Parsed property: {parsed_property}")
        
        # Query the Rent-Paid-July-2025 table
        response = supabase.table("Rent-Paid-July-2025").select("Property, Unit, Total_Paid").eq("Property", parsed_property).execute()
        
        print(f"🔍 Response received: {len(response.data) if response.data else 0} units found")
        
        # Calculate total paid for the property
        total_property_paid = sum(float(record.get("Total_Paid", 0)) for record in (response.data or []))
        
        # Debug: Output the units and their data
        print(f"📋 Units found for property '{parsed_property}':")
        for i, record in enumerate(response.data or [], 1):
            unit = record.get("Unit", "N/A")
            total_paid = record.get("Total_Paid", 0)
            print(f"  {i}. Unit: {unit}, Total Paid: ${total_paid}")
        
        print(f"💰 Total property paid: ${round(total_property_paid, 2)}")
        
        return {
            "data": response.data or [],
            "count": len(response.data) if response.data else 0,
            "property": property,
            "parsed_property": parsed_property,
            "total_property_paid": round(total_property_paid, 2),
            "units": [record.get("Unit") for record in (response.data or []) if record.get("Unit")]
        }
    except Exception as e:
        print(f"❌ Error in get_rent_paid_units: {str(e)}")
        print(f"❌ Error type: {type(e)}")
        import traceback
        print(f"❌ Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/db/rent-paid-unit-details")
async def get_rent_paid_unit_details(
    property: str = Query(..., description="Property name (required)"),
    unit: str = Query(..., description="Unit name (required)")
):
    """Get specific unit's total paid amount from Rent-Paid-July-2025 table"""
    try:
        # Parse property name to remove "Apartments" suffix
        parsed_property = property.replace(" Apartments", "").replace("Apartments", "")
        print(f"🔍 Original property: {property}")
        print(f"🔍 Parsed property: {parsed_property}")
        print(f"🔍 Unit: {unit}")
        
        response = supabase.table("Rent-Paid-July-2025").select("Property, Unit, Total_Paid").eq("Property", parsed_property).eq("Unit", unit).execute()
        
        print(f"🔍 Response received: {len(response.data) if response.data else 0} records found")
        
        # Get the total paid amount for this specific unit
        unit_total_paid = 0
        if response.data:
            unit_total_paid = float(response.data[0].get("Total_Paid", 0))
            print(f"📋 Unit details for '{unit}' in property '{parsed_property}':")
            print(f"  Unit: {unit}")
            print(f"  Total Paid: ${unit_total_paid}")
        else:
            print(f"❌ No data found for unit '{unit}' in property '{parsed_property}'")
        
        return {
            "data": response.data,
            "count": len(response.data),
            "unit_total_paid": round(unit_total_paid, 2),
            "filters_applied": {
                "property": property,
                "parsed_property": parsed_property,
                "unit": unit
            }
        }
    except Exception as e:
        print(f"❌ Error in get_rent_paid_unit_details: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/db/rent-paid-properties")
async def get_rent_paid_properties():
    """Get all unique properties from Rent-Paid-July-2025 table"""
    try:
        # Get all unique properties
        response = supabase.table("Rent-Paid-July-2025").select("Property").execute()
        
        # Extract unique property names
        unique_properties = list(set(record.get("Property") for record in (response.data or []) if record.get("Property")))
        unique_properties.sort()  # Sort alphabetically
        
        print(f"🔍 Found {len(unique_properties)} unique properties")
        print(f"📋 Available properties:")
        for i, prop in enumerate(unique_properties, 1):
            print(f"  {i}. {prop}")
        
        return {
            "properties": unique_properties,
            "count": len(unique_properties)
        }
    except Exception as e:
        print(f"❌ Error in get_rent_paid_properties: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/db/health-check")
async def database_health_check():
    """Comprehensive database health check for deployment debugging"""
    try:
        health_info = {
            "environment": {
                "supabase_url_exists": bool(os.getenv("SUPABASE_URL")),
                "supabase_key_exists": bool(os.getenv("SUPABASE_KEY")),
                "supabase_url_length": len(os.getenv("SUPABASE_URL", "")),
                "supabase_key_length": len(os.getenv("SUPABASE_KEY", ""))
            },
            "tables": {},
            "errors": []
        }
        
        # Test each table used by unit filtering
        tables_to_check = ["STR-Jul-2025", "Rent-Paid-July-2025"]
        
        for table_name in tables_to_check:
            try:
                # Test basic connection
                test_response = supabase.table(table_name).select("*").limit(1).execute()
                health_info["tables"][table_name] = {
                    "exists": True,
                    "accessible": True,
                    "has_data": bool(test_response.data),
                    "sample_count": len(test_response.data) if test_response.data else 0
                }
                
                # Get column info if table exists
                if test_response.data:
                    sample_record = test_response.data[0]
                    health_info["tables"][table_name]["columns"] = list(sample_record.keys())
                    
                    # For STR table, get unique properties
                    if table_name == "STR-Jul-2025":
                        props_response = supabase.table(table_name).select("Property").execute()
                        unique_props = list(set([prop.get("Property") for prop in (props_response.data or []) if prop.get("Property")]))
                        health_info["tables"][table_name]["unique_properties"] = unique_props[:10]  # First 10
                        health_info["tables"][table_name]["total_properties"] = len(unique_props)
                        
            except Exception as table_error:
                health_info["tables"][table_name] = {
                    "exists": False,
                    "accessible": False,
                    "error": str(table_error)
                }
                health_info["errors"].append(f"Table {table_name}: {str(table_error)}")
        
        return {
            "status": "healthy" if not health_info["errors"] else "unhealthy",
            "health_info": health_info,
            "timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }
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

class PropertyListing(BaseModel):
    """Property listing model based on imported Excel data"""
    id: str = Field(..., description="Primary key")
    title: str
    nickname: Optional[str] = None
    property_type: Optional[str] = "Apartment"
    room_type: Optional[str] = "Apartment"

    accommodates: Optional[int] = None
    bedrooms: Optional[int] = None
    bathrooms: Optional[int] = None
    area_square_feet: Optional[float] = None

    active: Optional[bool] = True

    address_building_name: Optional[str] = None
    address_city: Optional[str] = None
    address_state: Optional[str] = None
    address_full: Optional[str] = None

    thumbnail_url: Optional[str] = None

    base_price: Optional[float] = None
    currency: Optional[str] = "USD"

    description_summary: Optional[str] = None

    tags: List[str] = []
    amenities: List[str] = []
    pictures: List[str] = []

    # Source indicator for frontend
    source: Optional[str] = "guesty"  # STR data is marked as 'guesty' for frontend compatibility

class STRUnitData(BaseModel):
    """STR unit data model"""
    property: str
    unit: str
    month: int
    year: int
    revenue: Optional[float] = None
    commission: Optional[float] = None
    avg_nightly_rate: Optional[float] = None
    occupancy_pct: Optional[float] = None
    revpal: Optional[float] = None
    period: Optional[str] = None

class RentrollUnitData(BaseModel):
    """Rentroll unit data model"""
    property: str
    unit: str
    month: int
    year: int
    tenant: Optional[str] = None
    is_vacant: Optional[bool] = False
    lease_start: Optional[str] = None
    lease_end: Optional[str] = None
    size_sqft: Optional[float] = None
    rent: Optional[float] = None
    deposits: Optional[float] = None
    listing_price: Optional[float] = None
    balance: Optional[float] = None
    period: Optional[str] = None

@router.get("/api/reservations/names",
    summary="Get unique property and building names"
)
def get_property_and_building_names():
    """
    Get a list of all unique property and building names from the database.
    This provides backward compatibility with the old Guesty reservations endpoint.
    """
    try:
        # Get property names from the properties table
        properties_res = supabase.table("properties").select("name, full_name").execute()

        property_names = []
        building_names = []

        for item in (properties_res.data or []):
            if item.get("full_name"):
                property_names.append(item["full_name"])
            if item.get("name"):
                building_names.append(item["name"])

        return {
            "property_names": sorted(list(set(property_names))),
            "building_names": sorted(list(set(building_names)))
        }
    except Exception as e:
        print(f"Error fetching property names: {e}")
        return {
            "property_names": [],
            "building_names": []
        }

@router.get("/api/properties/listings",
    response_model=List[PropertyListing],
    summary="Get all properties from imported Excel data"
)
def get_listings() -> List[Dict]:
    """
    Get all properties from the properties table.
    This replaces the old Guesty jd_listing table.
    """
    try:
        # Fetch properties from the properties table
        properties_res = (
            supabase
            .table("properties")
            .select("*")
            .execute()
        )

        if not properties_res.data:
            return []

        # Transform to expected format
        listings = []
        for prop in properties_res.data:
            # Get units for this property from str_data to count units
            units_res = (
                supabase
                .table("str_data")
                .select("unit")
                .eq("property", prop["name"])
                .execute()
            )

            unique_units = list(set([u["unit"] for u in (units_res.data or []) if u.get("unit")]))

            # Get latest revenue data for base_price estimation
            revenue_res = (
                supabase
                .table("str_data")
                .select("revenue, avg_nightly_rate")
                .eq("property", prop["name"])
                .order("year", desc=True)
                .order("month", desc=True)
                .limit(1)
                .execute()
            )

            base_price = 0
            if revenue_res.data and len(revenue_res.data) > 0:
                base_price = revenue_res.data[0].get("avg_nightly_rate") or revenue_res.data[0].get("revenue") or 0

            listing = {
                "id": str(prop["id"]),
                "title": prop.get("full_name") or prop["name"],
                "nickname": prop["name"],
                "property_type": "Apartment",
                "room_type": "Apartment",
                "accommodates": len(unique_units) * 2,  # Estimate
                "bedrooms": None,
                "bathrooms": None,
                "area_square_feet": None,
                "active": prop.get("active", True),
                "address_building_name": prop["name"],
                "address_city": "",
                "address_state": "",
                "address_full": prop.get("full_name") or prop["name"],
                "thumbnail_url": None,
                "base_price": float(base_price) if base_price else None,
                "currency": "USD",
                "description_summary": f"Property with {len(unique_units)} units",
                "tags": [],
                "amenities": [],
                "pictures": [],
                "source": "guesty"  # Mark as STR data for frontend
            }
            listings.append(listing)

        return listings

    except Exception as e:
        print(f"Error fetching properties: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/api/properties/listings/{listing_id}",
    response_model=PropertyListing,
    summary="Get a specific property by ID"
)
def get_property_by_id(listing_id: str) -> Dict[str, Any]:
    """
    Get a specific property by ID from the properties table.
    """
    try:
        # Fetch the specific property
        property_res = (
            supabase
            .table("properties")
            .select("*")
            .eq("id", int(listing_id))
            .execute()
        )

        if not property_res.data:
            raise HTTPException(status_code=404, detail=f"Property with ID '{listing_id}' not found")

        prop = property_res.data[0]

        # Get units for this property
        units_res = (
            supabase
            .table("str_data")
            .select("unit")
            .eq("property", prop["name"])
            .execute()
        )

        unique_units = list(set([u["unit"] for u in (units_res.data or []) if u.get("unit")]))

        return {
            "id": str(prop["id"]),
            "title": prop.get("full_name") or prop["name"],
            "nickname": prop["name"],
            "property_type": "Apartment",
            "room_type": "Apartment",
            "accommodates": len(unique_units) * 2,
            "bedrooms": None,
            "bathrooms": None,
            "area_square_feet": None,
            "active": prop.get("active", True),
            "address_building_name": prop["name"],
            "address_city": "",
            "address_state": "",
            "address_full": prop.get("full_name") or prop["name"],
            "thumbnail_url": None,
            "base_price": None,
            "currency": "USD",
            "description_summary": f"Property with {len(unique_units)} units",
            "tags": [],
            "amenities": [],
            "pictures": [],
            "source": "guesty"  # Mark as STR data for frontend
        }

    except HTTPException:
        raise
    except Exception as e:
        print(f"Error fetching property: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/api/properties/str-data",
    summary="Get STR revenue data for properties"
)
async def get_str_data(
    property: Optional[str] = Query(None, description="Property name to filter by"),
    unit: Optional[str] = Query(None, description="Unit name to filter by"),
    year: Optional[int] = Query(None, description="Year to filter by"),
    month: Optional[int] = Query(None, description="Month to filter by")
):
    """Get STR revenue data from imported Excel data"""
    try:
        query = supabase.table("str_data").select("*")

        if property:
            query = query.eq("property", property)
        if unit:
            query = query.eq("unit", unit)
        if year:
            query = query.eq("year", year)
        if month:
            query = query.eq("month", month)

        response = query.order("year", desc=True).order("month", desc=True).execute()

        return {
            "data": response.data or [],
            "count": len(response.data) if response.data else 0
        }
    except Exception as e:
        print(f"Error fetching STR data: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/api/properties/rentroll-data",
    summary="Get rentroll data for properties"
)
async def get_rentroll_data(
    property: Optional[str] = Query(None, description="Property name to filter by"),
    unit: Optional[str] = Query(None, description="Unit name to filter by"),
    year: Optional[int] = Query(None, description="Year to filter by"),
    month: Optional[int] = Query(None, description="Month to filter by")
):
    """Get rentroll data from imported Excel data"""
    try:
        query = supabase.table("rentroll_data").select("*")

        if property:
            query = query.eq("property", property)
        if unit:
            query = query.eq("unit", unit)
        if year:
            query = query.eq("year", year)
        if month:
            query = query.eq("month", month)

        response = query.order("year", desc=True).order("month", desc=True).execute()

        return {
            "data": response.data or [],
            "count": len(response.data) if response.data else 0
        }
    except Exception as e:
        print(f"Error fetching rentroll data: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/api/properties/rent-paid-data",
    summary="Get rent paid data for properties"
)
async def get_rent_paid_data(
    property: Optional[str] = Query(None, description="Property name to filter by"),
    unit: Optional[str] = Query(None, description="Unit name to filter by"),
    year: Optional[int] = Query(None, description="Year to filter by"),
    month: Optional[int] = Query(None, description="Month to filter by")
):
    """Get rent paid data from imported Excel data"""
    try:
        query = supabase.table("rent_paid_data").select("*")

        if property:
            query = query.eq("property", property)
        if unit:
            query = query.eq("unit", unit)
        if year:
            query = query.eq("year", year)
        if month:
            query = query.eq("month", month)

        response = query.order("year", desc=True).order("month", desc=True).execute()

        return {
            "data": response.data or [],
            "count": len(response.data) if response.data else 0
        }
    except Exception as e:
        print(f"Error fetching rent paid data: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/api/properties/pnl-data",
    summary="Get P&L data for properties"
)
async def get_pnl_data(
    property: Optional[str] = Query(None, description="Property name to filter by"),
    year: Optional[int] = Query(None, description="Year to filter by"),
    month: Optional[int] = Query(None, description="Month to filter by"),
    category: Optional[str] = Query(None, description="Category to filter by")
):
    """Get P&L data from imported Excel data"""
    try:
        query = supabase.table("pnl_data").select("*")

        if property:
            query = query.eq("property", property)
        if year:
            query = query.eq("year", year)
        if month:
            query = query.eq("month", month)
        if category:
            query = query.eq("category", category)

        response = query.order("year", desc=True).order("month", desc=True).execute()

        return {
            "data": response.data or [],
            "count": len(response.data) if response.data else 0
        }
    except Exception as e:
        print(f"Error fetching P&L data: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/db/units-for-property")
async def get_units_for_property(
    property: str = Query(..., description="Property name (required)")
):
    """Get all units for a specific property from str_data table"""
    try:
        print(f"🔍 Looking up units for property: {property}")

        # Query the str_data table for unique units
        response = supabase.table("str_data").select("unit").eq("property", property).execute()

        if not response.data:
            # Try without "Apartments" suffix
            parsed_property = property.replace(" Apartments", "").replace("Apartments", "").strip()
            print(f"🔍 Retrying with parsed property: {parsed_property}")
            response = supabase.table("str_data").select("unit").eq("property", parsed_property).execute()

        unique_units = list(set([record.get("unit") for record in (response.data or []) if record.get("unit")]))
        unique_units.sort()

        print(f"🔍 Found {len(unique_units)} unique units")

        return {
            "data": [{"Unit": unit} for unit in unique_units],
            "count": len(unique_units),
            "property": property,
            "units": unique_units
        }
    except Exception as e:
        print(f"Error in get_units_for_property: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/db/unit-filtering")
async def get_unit_filtering_data(
    property: str = Query(..., description="Property name (required)"),
    unit: str = Query(..., description="Unit name (required)")
):
    """Get unit filtering data from str_data table"""
    try:
        print(f"🔍 Property: {property}, Unit: {unit}")

        response = supabase.table("str_data").select("property, unit, revenue, avg_nightly_rate, occupancy_pct, revpal").eq("property", property).eq("unit", unit).execute()

        if not response.data:
            # Try without "Apartments" suffix
            parsed_property = property.replace(" Apartments", "").replace("Apartments", "").strip()
            response = supabase.table("str_data").select("property, unit, revenue, avg_nightly_rate, occupancy_pct, revpal").eq("property", parsed_property).eq("unit", unit).execute()

        print(f"🔍 Found {len(response.data) if response.data else 0} records")

        return {
            "data": response.data,
            "count": len(response.data) if response.data else 0,
            "filters_applied": {
                "property": property,
                "unit": unit
            }
        }
    except Exception as e:
        print(f"Error in get_unit_filtering_data: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/db/rent-paid-units")
async def get_rent_paid_units(
    property: str = Query(..., description="Property name (required)")
):
    """Get all units and their total paid amounts from rent_paid_data table"""
    try:
        print(f"🔍 Looking up rent paid units for property: {property}")

        response = supabase.table("rent_paid_data").select("property, unit, total_paid").eq("property", property).execute()

        if not response.data:
            # Try without "Apartments" suffix
            parsed_property = property.replace(" Apartments", "").replace("Apartments", "").strip()
            response = supabase.table("rent_paid_data").select("property, unit, total_paid").eq("property", parsed_property).execute()

        # Calculate total
        total_property_paid = sum(float(record.get("total_paid", 0) or 0) for record in (response.data or []))
        unique_units = list(set([record.get("unit") for record in (response.data or []) if record.get("unit")]))

        print(f"🔍 Found {len(response.data) if response.data else 0} records, total: ${round(total_property_paid, 2)}")

        return {
            "data": response.data or [],
            "count": len(response.data) if response.data else 0,
            "property": property,
            "total_property_paid": round(total_property_paid, 2),
            "units": unique_units
        }
    except Exception as e:
        print(f"Error in get_rent_paid_units: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/db/rent-paid-unit-details")
async def get_rent_paid_unit_details(
    property: str = Query(..., description="Property name (required)"),
    unit: str = Query(..., description="Unit name (required)")
):
    """Get specific unit's rent paid details from rent_paid_data table"""
    try:
        print(f"🔍 Property: {property}, Unit: {unit}")

        response = supabase.table("rent_paid_data").select("*").eq("property", property).eq("unit", unit).execute()

        if not response.data:
            # Try without "Apartments" suffix
            parsed_property = property.replace(" Apartments", "").replace("Apartments", "").strip()
            response = supabase.table("rent_paid_data").select("*").eq("property", parsed_property).eq("unit", unit).execute()

        unit_total_paid = sum(float(record.get("total_paid", 0) or 0) for record in (response.data or []))

        print(f"🔍 Found {len(response.data) if response.data else 0} records, total: ${round(unit_total_paid, 2)}")

        return {
            "data": response.data,
            "count": len(response.data) if response.data else 0,
            "unit_total_paid": round(unit_total_paid, 2),
            "filters_applied": {
                "property": property,
                "unit": unit
            }
        }
    except Exception as e:
        print(f"Error in get_rent_paid_unit_details: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/db/rent-paid-properties")
async def get_rent_paid_properties():
    """Get all unique properties from rent_paid_data table"""
    try:
        response = supabase.table("rent_paid_data").select("property").execute()

        unique_properties = list(set(record.get("property") for record in (response.data or []) if record.get("property")))
        unique_properties.sort()

        print(f"🔍 Found {len(unique_properties)} unique properties")

        return {
            "properties": unique_properties,
            "count": len(unique_properties)
        }
    except Exception as e:
        print(f"Error in get_rent_paid_properties: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

@router.get("/db/health-check")
async def database_health_check():
    """Comprehensive database health check"""
    try:
        health_info = {
            "environment": {
                "supabase_url_exists": bool(os.getenv("SUPABASE_URL")),
                "supabase_key_exists": bool(os.getenv("SUPABASE_KEY")),
            },
            "tables": {},
            "errors": []
        }

        # Test each table
        tables_to_check = ["properties", "str_data", "rentroll_data", "rent_paid_data", "pnl_data"]

        for table_name in tables_to_check:
            try:
                test_response = supabase.table(table_name).select("*").limit(1).execute()
                health_info["tables"][table_name] = {
                    "exists": True,
                    "accessible": True,
                    "has_data": bool(test_response.data),
                    "sample_count": len(test_response.data) if test_response.data else 0
                }

                if test_response.data:
                    health_info["tables"][table_name]["columns"] = list(test_response.data[0].keys())

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

@router.get("/api/properties/summary",
    summary="Get summary statistics for all properties"
)
async def get_properties_summary():
    """Get summary statistics for all properties"""
    try:
        # Get all properties
        properties_res = supabase.table("properties").select("*").execute()

        # Get STR data summary
        str_res = supabase.table("str_data").select("property, revenue, occupancy_pct").execute()

        # Get rent paid summary
        rent_paid_res = supabase.table("rent_paid_data").select("property, total_paid").execute()

        # Calculate totals
        total_revenue = sum(float(r.get("revenue", 0) or 0) for r in (str_res.data or []))
        total_paid = sum(float(r.get("total_paid", 0) or 0) for r in (rent_paid_res.data or []))
        avg_occupancy = 0
        if str_res.data:
            occupancy_values = [float(r.get("occupancy_pct", 0) or 0) for r in str_res.data if r.get("occupancy_pct")]
            if occupancy_values:
                avg_occupancy = sum(occupancy_values) / len(occupancy_values)

        return {
            "total_properties": len(properties_res.data) if properties_res.data else 0,
            "total_str_revenue": round(total_revenue, 2),
            "total_rent_paid": round(total_paid, 2),
            "average_occupancy_pct": round(avg_occupancy, 2),
            "properties": [p["name"] for p in (properties_res.data or [])]
        }
    except Exception as e:
        print(f"Error fetching summary: {e}")
        raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")

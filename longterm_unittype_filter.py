from fastapi import APIRouter, HTTPException
from typing import Optional
from datetime import datetime
from dateutil.relativedelta import relativedelta
from database import supabase
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/longterm-unittype-filter", tags=["longterm-unittype-filter"])


def parse_date(date_str: str) -> Optional[datetime]:
    """
    Parse date string in various formats.
    Handles: M/D/YY, M/D/YYYY, YYYY-MM-DD
    """
    if not date_str:
        return None
    
    formats = [
        "%m/%d/%y",      # 8/29/24
        "%m/%d/%Y",      # 8/29/2024
        "%Y-%m-%d",      # 2024-08-29
    ]
    
    for fmt in formats:
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    
    return None


def get_months_between(date_from: str, date_to: str) -> list[str]:
    """
    Generate a list of month strings (YYYY-MM) between two dates inclusive.
    e.g., "2025-06-01" to "2025-12-31" returns ["2025-06", "2025-07", ..., "2025-12"]
    """
    start = datetime.strptime(date_from, "%Y-%m-%d")
    end = datetime.strptime(date_to, "%Y-%m-%d")
    
    months = []
    current = start.replace(day=1)  # Start from first of month
    end_month = end.replace(day=1)
    
    while current <= end_month:
        months.append(current.strftime("%Y-%m"))
        current += relativedelta(months=1)
    
    return months


def calculate_occupancy(records: list, date_from: str, date_to: str) -> dict:
    """
    Calculate occupancy metrics based on lease dates within the requested date range.
    
    Returns:
        - total_units: Number of unique units
        - occupied_units: Units with active leases in the date range
        - occupancy_rate: Percentage of occupied units
        - total_occupied_days: Sum of occupied days across all units
        - average_occupied_days: Average occupied days per unit
    """
    if not records:
        return {
            "total_units": 0,
            "occupied_units": 0,
            "occupancy_rate": 0.0,
            "total_occupied_days": 0,
            "average_occupied_days": 0.0
        }
    
    range_start = datetime.strptime(date_from, "%Y-%m-%d")
    range_end = datetime.strptime(date_to, "%Y-%m-%d")
    total_days_in_range = (range_end - range_start).days + 1
    
    # Track unique units and their occupied days
    unit_occupied_days = {}
    
    for record in records:
        unit = record.get("unit")
        lease_start = record.get("lease_start_date")
        lease_end = record.get("lease_end_date")
        
        if not unit:
            continue
            
        # Initialize unit if not seen
        if unit not in unit_occupied_days:
            unit_occupied_days[unit] = 0
        
        # Skip if no lease dates
        if not lease_start:
            continue
            
        # Parse lease dates (handle multiple formats)
        try:
            lease_start_dt = parse_date(lease_start)
            # If no end date, assume ongoing (use range_end)
            lease_end_dt = parse_date(lease_end) if lease_end else range_end
            
            if not lease_start_dt:
                continue
        except (ValueError, TypeError):
            continue
        
        # Calculate overlap between lease period and requested date range
        overlap_start = max(lease_start_dt, range_start)
        overlap_end = min(lease_end_dt, range_end)
        
        if overlap_start <= overlap_end:
            occupied_days = (overlap_end - overlap_start).days + 1
            unit_occupied_days[unit] = max(unit_occupied_days[unit], occupied_days)
    
    total_units = len(unit_occupied_days)
    occupied_units = sum(1 for days in unit_occupied_days.values() if days > 0)
    total_occupied_days = sum(unit_occupied_days.values())
    
    occupancy_rate = (occupied_units / total_units * 100) if total_units > 0 else 0.0
    average_occupied_days = (total_occupied_days / total_units) if total_units > 0 else 0.0
    
    # Calculate occupancy by days (what % of total possible days were occupied)
    total_possible_days = total_units * total_days_in_range
    days_occupancy_rate = (total_occupied_days / total_possible_days * 100) if total_possible_days > 0 else 0.0
    
    return {
        "total_units": total_units,
        "occupied_units": occupied_units,
        "occupancy_rate": round(occupancy_rate, 2),
        "days_occupancy_rate": round(days_occupancy_rate, 2),
        "total_occupied_days": total_occupied_days,
        "average_occupied_days": round(average_occupied_days, 1),
        "total_days_in_range": total_days_in_range
    }


def calculate_financials(records: list) -> dict:
    """
    Calculate financial metrics from records.
    
    Returns:
        - total_revenue: Sum of all revenue
        - total_balance_due: Sum of all balance due
    """
    total_revenue = 0.0
    total_balance_due = 0.0
    
    for record in records:
        # Parse revenue (remove $, commas, and handle parentheses for negative)
        revenue_str = record.get("revenue") or "$0"
        try:
            revenue_str = revenue_str.replace("$", "").replace(",", "")
            total_revenue += float(revenue_str)
        except (ValueError, AttributeError):
            pass
        
        # Parse balance_due (handle parentheses for negative values)
        balance_str = record.get("balance_due") or "$0"
        try:
            balance_str = balance_str.replace("$", "").replace(",", "")
            # Handle negative values in parentheses like "($1,475.00)"
            if "(" in balance_str and ")" in balance_str:
                balance_str = balance_str.replace("(", "-").replace(")", "")
            total_balance_due += float(balance_str)
        except (ValueError, AttributeError):
            pass
    
    return {
        "total_revenue": round(total_revenue, 2),
        "total_balance_due": round(total_balance_due, 2)
    }


@router.get("/")
async def longterm_unittype_filter(
    date_from: str,                     # e.g., "2025-06-01" (required)
    date_to: str,                       # e.g., "2025-12-31" (required)
    property_id: str,                   # e.g., "Aerie" (required)
    unit_type: str,                     # e.g., "3/3" (required)
    length: str = "Long",               # "Long" or "Short"
    unit: Optional[str] = None          # e.g., "21A" (optional)
):
    """
    Filter leases by property, unit type, and length (long/short term).
    Returns lease data with occupancy and financial metrics.
    
    - date_from: Start date (YYYY-MM-DD)
    - date_to: End date (YYYY-MM-DD)
    - property_id: Property name without "Apartments" suffix (e.g., "Aerie")
    - unit_type: Unit type like "3/3", "2/2", "3/2"
    - length: "Long" or "Short" term
    - unit: Optional specific unit (e.g., "21A")
    """
    try:
        # Get all months between date_from and date_to
        months = get_months_between(date_from, date_to)
        
        all_data = []
        
        # Query each month's table and combine results
        for month in months:
            try:
                logger.info(f"Calling RPC for month={month}, property={property_id}, unit_type={unit_type}, length={length}, unit={unit}")
                
                response = supabase.rpc("get_filtered_leases", {
                    "p_date": month,
                    "p_property": property_id,
                    "p_unit_type": unit_type,
                    "p_length": length,
                    "p_unit": unit
                }).execute()
                
                logger.info(f"RPC response for {month}: data={response.data}, count={len(response.data) if response.data else 0}")
                
                if response.data:
                    # Add month info to each record for context
                    for record in response.data:
                        record["month"] = month
                    all_data.extend(response.data)
                    
            except Exception as e:
                # Log but continue if a specific month table doesn't exist
                logger.error(f"Error querying table for {month}: {str(e)}")
                print(f"Warning: Could not query table for {month}: {str(e)}")
                continue
        
        # Calculate occupancy metrics
        occupancy = calculate_occupancy(all_data, date_from, date_to)
        
        # Calculate financial metrics
        financials = calculate_financials(all_data)
        
        return {
            "success": True,
            "data": all_data,
            "count": len(all_data),
            "months_queried": months,
            "occupancy": occupancy,
            "financials": financials
        }
        
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format. Use YYYY-MM-DD")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

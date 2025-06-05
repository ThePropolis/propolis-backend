# from fastapi import FastAPI, HTTPException
# import httpx
# import os
# from typing import Optional
# from datetime import datetime, timedelta

# app = FastAPI(title="DoorLoop Occupancy Rate API", version="1.0.0")

# # Configuration
# DOORLOOP_API_BASE = "https://app.doorloop.com/api"
# DOORLOOP_TOKEN = os.getenv("DOORLOOP_API_TOKEN")

# @app.get("/occupancy-rate-doorloop")
# async def get_occupancy_rate(
#     date_from: Optional[str] = None,
#     date_to: Optional[str] = None
# ):
#     """
#     Calculate occupancy rate: (occupied units / total units) * 100
    
#     Parameters:
#     - date_from: Start date (YYYY-MM-DD) - defaults to current month start
#     - date_to: End date (YYYY-MM-DD) - defaults to current month end
#     """
    
#     if not DOORLOOP_TOKEN:
#         raise HTTPException(status_code=500, detail="DoorLoop API token not configured")
    
#     # Set default date range to current month if not provided
#     if not date_from or not date_to:
#         today = datetime.now()
#         date_from = today.replace(day=1).strftime("%Y-%m-%d")
#         next_month = today.replace(day=28) + timedelta(days=4)
#         date_to = (next_month - timedelta(days=next_month.day)).strftime("%Y-%m-%d")
    
#     headers = {"Authorization": f"Bearer {DOORLOOP_TOKEN}"}
    
#     try:
#         # Get total units from properties
#         total_units = await get_total_units(headers)
        
#         # Get occupied units from active leases
#         occupied_units = await get_occupied_units(headers, date_from, date_to)
        
#         # Calculate occupancy rate
#         if total_units == 0:
#             occupancy_rate = 0
#         else:
#             occupancy_rate = (occupied_units / total_units) * 100
        
#         return {
#             "occupancy_rate": round(occupancy_rate, 2),
#             "occupied_units": occupied_units,
#             "total_units": total_units,
#             "date_from": date_from,
#             "date_to": date_to,
#             "percentage": f"{round(occupancy_rate, 2)}%"
#         }
        
#     except Exception as e:
#         raise HTTPException(status_code=500, detail=f"Error calculating occupancy rate: {str(e)}")

# async def get_total_units(headers):
#     """Get total number of units from all properties"""
    
#     async with httpx.AsyncClient() as client:
#         # Get all properties
#         response = await client.get(
#             f"{DOORLOOP_API_BASE}/properties",
#             headers=headers,
#             params={"limit": 1000}
#         )
        
#         if response.status_code != 200:
#             raise Exception(f"Failed to fetch properties: {response.text}")
        
#         properties = response.json().get("data", [])
        
#         total_units = 0
        
#         # For each property, get its units
#         for property_data in properties:
#             property_id = property_data.get("id")
            
#             units_response = await client.get(
#                 f"{DOORLOOP_API_BASE}/properties/{property_id}/units",
#                 headers=headers,
#                 params={"limit": 1000}
#             )
            
#             if units_response.status_code == 200:
#                 units = units_response.json().get("data", [])
#                 total_units += len(units)
        
#         return total_units

# async def get_occupied_units(headers, date_from, date_to):
#     """Get number of occupied units based on active leases"""
    
#     async with httpx.AsyncClient() as client:
#         # Get all active leases within the date range
#         response = await client.get(
#             f"{DOORLOOP_API_BASE}/leases",
#             headers=headers,
#             params={
#                 "limit": 1000,
#                 "status": "active",
#                 "start_date_from": date_from,
#                 "start_date_to": date_to
#             }
#         )
        
#         if response.status_code != 200:
#             raise Exception(f"Failed to fetch leases: {response.text}")
        
#         leases = response.json().get("data", [])
        
#         # Count unique units that have active leases
#         occupied_unit_ids = set()
        
#         for lease in leases:
#             unit_id = lease.get("unit_id")
#             if unit_id:
#                 occupied_unit_ids.add(unit_id)
        
#         return len(occupied_unit_ids)

# @app.get("/health")
# async def health_check():
#     """Health check endpoint"""
#     return {"status": "healthy", "service": "DoorLoop Occupancy Rate API"}
 
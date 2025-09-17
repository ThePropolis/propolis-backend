#!/usr/bin/env python3
"""
Debug at-will leases to see what the API is returning
"""

import asyncio
import sys
import os
import httpx
import logging

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from doorloop import get_doorloop_headers, DOORLOOP_BASE_URL

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')

async def debug_at_will_leases():
    """Debug what the API returns for at-will leases."""
    
    print("🔍 Debugging At-Will Leases")
    print("=" * 50)
    
    async with httpx.AsyncClient() as client:
        try:
            headers = get_doorloop_headers()
            
            # Get all properties
            properties_response = await client.get(f"{DOORLOOP_BASE_URL}/properties", headers=headers)
            properties_response.raise_for_status()
            properties_data = properties_response.json()
            properties = properties_data.get('data', [])
            
            print(f"Found {len(properties)} properties")
            
            # Check each property for at-will leases
            for prop in properties:
                prop_id = prop.get('id')
                prop_name = prop.get('name', 'Unknown')
                
                if not prop_id:
                    continue
                
                print(f"\n🏢 Checking {prop_name} (ID: {prop_id})")
                
                # Get leases for this property
                params = {
                    "filter_property": prop_id,
                    "filter_start_date_from": "2020-01-01",
                    "filter_start_date_to": "2025-07-31",
                    "filter_end_date_from": "2025-07-01", 
                    "filter_end_date_to": "2030-12-31",
                }
                
                response = await client.get(f"{DOORLOOP_BASE_URL}/leases", headers=headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                leases = data.get('data', [])
                
                print(f"  Total leases: {len(leases)}")
                
                # Look for at-will leases
                at_will_leases = []
                for lease in leases:
                    lease_end = lease.get('end', '')
                    lease_name = lease.get('name', 'Unknown')
                    lease_start = lease.get('start', '')
                    
                    # Check if this looks like an at-will lease
                    if not lease_end or lease_end == 'AtWill' or lease_end == 'At-will':
                        at_will_leases.append({
                            'name': lease_name,
                            'start': lease_start,
                            'end': lease_end,
                            'id': lease.get('id', 'Unknown')
                        })
                
                print(f"  At-will leases found: {len(at_will_leases)}")
                
                # Show details of at-will leases
                for lease in at_will_leases:
                    print(f"    - {lease['name']}: {lease['start']} to '{lease['end']}' (ID: {lease['id']})")
                
                # Check if any of our missing leases are here
                missing_names = [
                    "Scott Grieco", "Jiayu Zhu", "Randolph Wiggins", "Seoyon Lee", 
                    "DaMonte Ward", "ELAINE TEIXEIRA", "CJ Patton", 
                    "Isabella Scarpinato", "Danila Abalakov", "Chance Bain"
                ]
                
                found_missing = []
                for lease in leases:
                    if lease.get('name', '') in missing_names:
                        found_missing.append(lease)
                
                if found_missing:
                    print(f"  🎯 Found missing leases in API:")
                    for lease in found_missing:
                        print(f"    - {lease.get('name', 'Unknown')}: {lease.get('start', 'N/A')} to '{lease.get('end', 'N/A')}'")
                
                await asyncio.sleep(0.1)  # Small delay
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

def main():
    """Main function to run the debug."""
    try:
        asyncio.run(debug_at_will_leases())
    except Exception as e:
        print(f"❌ Debug failed: {e}")

if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Check if missing leases exist in API with different date ranges
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

async def check_missing_leases():
    """Check if missing leases exist in API with broader date ranges."""
    
    print("🔍 Checking for Missing Leases in API")
    print("=" * 50)
    
    missing_names = [
        "Scott Grieco", "Jiayu Zhu", "Randolph Wiggins", "Seoyon Lee", 
        "DaMonte Ward", "ELAINE TEIXEIRA", "CJ Patton", 
        "Isabella Scarpinato", "Danila Abalakov", "Chance Bain"
    ]
    
    async with httpx.AsyncClient() as client:
        try:
            headers = get_doorloop_headers()
            
            # Get all properties
            properties_response = await client.get(f"{DOORLOOP_BASE_URL}/properties", headers=headers)
            properties_response.raise_for_status()
            properties_data = properties_response.json()
            properties = properties_data.get('data', [])
            
            print(f"Searching for {len(missing_names)} missing leases across {len(properties)} properties")
            
            found_leases = []
            
            # Check each property with a very broad date range
            for prop in properties:
                prop_id = prop.get('id')
                prop_name = prop.get('name', 'Unknown')
                
                if not prop_id:
                    continue
                
                print(f"\n🏢 Checking {prop_name}")
                
                # Use a very broad date range to catch all leases
                params = {
                    "filter_property": prop_id,
                    "filter_start_date_from": "2020-01-01",
                    "filter_start_date_to": "2030-12-31",
                }
                
                response = await client.get(f"{DOORLOOP_BASE_URL}/leases", headers=headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                leases = data.get('data', [])
                
                print(f"  Total leases in property: {len(leases)}")
                
                # Look for our missing leases
                for lease in leases:
                    lease_name = lease.get('name', '').strip()
                    if lease_name in missing_names:
                        found_leases.append({
                            'name': lease_name,
                            'property': prop_name,
                            'start': lease.get('start', 'N/A'),
                            'end': lease.get('end', 'N/A'),
                            'status': lease.get('status', 'N/A'),
                            'id': lease.get('id', 'N/A')
                        })
                        print(f"  🎯 FOUND: {lease_name}")
                        print(f"      Start: {lease.get('start', 'N/A')}")
                        print(f"      End: '{lease.get('end', 'N/A')}'")
                        print(f"      Status: {lease.get('status', 'N/A')}")
                
                await asyncio.sleep(0.1)
            
            print(f"\n📊 Results:")
            print(f"  Missing leases searched: {len(missing_names)}")
            print(f"  Found in API: {len(found_leases)}")
            print(f"  Still missing: {len(missing_names) - len(found_leases)}")
            
            if found_leases:
                print(f"\n✅ Found Leases:")
                for lease in found_leases:
                    print(f"  - {lease['name']} ({lease['property']})")
                    print(f"    {lease['start']} to '{lease['end']}' - {lease['status']}")
            
            # Check which ones are still missing
            found_names = {lease['name'] for lease in found_leases}
            still_missing = [name for name in missing_names if name not in found_names]
            
            if still_missing:
                print(f"\n❌ Still Missing ({len(still_missing)}):")
                for name in still_missing:
                    print(f"  - {name}")
            
            # Try a global search without property filter
            print(f"\n🌐 Global Search (No Property Filter):")
            params = {
                "filter_start_date_from": "2020-01-01",
                "filter_start_date_to": "2030-12-31",
            }
            
            response = await client.get(f"{DOORLOOP_BASE_URL}/leases", headers=headers, params=params)
            response.raise_for_status()
            
            data = response.json()
            all_leases = data.get('data', [])
            
            print(f"  Total leases globally: {len(all_leases)}")
            
            global_found = []
            for lease in all_leases:
                lease_name = lease.get('name', '').strip()
                if lease_name in missing_names:
                    global_found.append({
                        'name': lease_name,
                        'start': lease.get('start', 'N/A'),
                        'end': lease.get('end', 'N/A'),
                        'status': lease.get('status', 'N/A'),
                        'property': lease.get('property', 'N/A')
                    })
            
            print(f"  Found in global search: {len(global_found)}")
            
            if global_found:
                print(f"\n✅ Global Search Results:")
                for lease in global_found:
                    print(f"  - {lease['name']}")
                    print(f"    {lease['start']} to '{lease['end']}' - {lease['status']}")
                    print(f"    Property: {lease['property']}")
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

def main():
    """Main function to run the check."""
    try:
        asyncio.run(check_missing_leases())
    except Exception as e:
        print(f"❌ Check failed: {e}")

if __name__ == "__main__":
    main()

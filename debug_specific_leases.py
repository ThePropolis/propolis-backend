#!/usr/bin/env python3
"""
Debug why specific at-will leases are not being included
"""

import asyncio
import sys
import os
import httpx
import logging
from datetime import datetime

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from doorloop import get_doorloop_headers, DOORLOOP_BASE_URL, lease_overlaps_date_range

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')

async def debug_specific_leases():
    """Debug why specific at-will leases are not being included."""
    
    print("🔍 Debugging Specific At-Will Leases")
    print("=" * 50)
    
    # The 10 missing leases we know exist in API
    missing_leases = [
        {"name": "Scott Grieco", "property": "6421b49684fc82179be10fcc", "start": "2023-05-31", "end": "N/A"},
        {"name": "Jiayu Zhu", "property": "6421b49684fc82179be10fcc", "start": "2024-11-12", "end": "N/A"},
        {"name": "Randolph Wiggins", "property": "63879c5598c8715a26d52948", "start": "2024-01-05", "end": "N/A"},
        {"name": "Seoyon Lee", "property": "646cd91f6dacd917aae33ed5", "start": "2025-04-01", "end": "N/A"},
        {"name": "DaMonte Ward", "property": "6421b49684fc82179be10fcc", "start": "2024-05-03", "end": "N/A"},
        {"name": "ELAINE TEIXEIRA", "property": "63879c5598c8715a26d52948", "start": "2024-06-27", "end": "N/A"},
        {"name": "CJ Patton", "property": "6421b49684fc82179be10fcc", "start": "2024-09-09", "end": "N/A"},
        {"name": "Isabella Scarpinato", "property": "67a3a834f8a358c089a8acbe", "start": "2025-03-01", "end": "N/A"},
        {"name": "Danila Abalakov", "property": "66f58ded3e91072ecf17c7ce", "start": "2025-07-19", "end": "N/A"},
        {"name": "Chance Bain", "property": "6421b49684fc82179be10fcc", "start": "2024-06-01", "end": "N/A"},
    ]
    
    # Target date range
    date_start = "2025-07-01"
    date_end = "2025-07-31"
    date_start_dt = datetime.strptime(date_start, "%Y-%m-%d")
    date_end_dt = datetime.strptime(date_end, "%Y-%m-%d")
    
    print(f"Target date range: {date_start} to {date_end}")
    print(f"Checking {len(missing_leases)} leases...")
    
    async with httpx.AsyncClient() as client:
        try:
            headers = get_doorloop_headers()
            
            for lease_info in missing_leases:
                print(f"\n🔍 Checking {lease_info['name']}")
                print(f"  Property: {lease_info['property']}")
                print(f"  Start: {lease_info['start']}")
                print(f"  End: {lease_info['end']}")
                
                # Get the actual lease from API
                params = {
                    "filter_property": lease_info['property'],
                    "filter_start_date_from": "2020-01-01",
                    "filter_start_date_to": "2030-12-31",
                }
                
                response = await client.get(f"{DOORLOOP_BASE_URL}/leases", headers=headers, params=params)
                response.raise_for_status()
                
                data = response.json()
                leases = data.get('data', [])
                
                # Find the specific lease
                found_lease = None
                for lease in leases:
                    if lease.get('name', '').strip() == lease_info['name']:
                        found_lease = lease
                        break
                
                if not found_lease:
                    print(f"  ❌ Lease not found in API")
                    continue
                
                print(f"  ✅ Found in API")
                print(f"    API Start: {found_lease.get('start', 'N/A')}")
                print(f"    API End: '{found_lease.get('end', 'N/A')}'")
                print(f"    API Status: {found_lease.get('status', 'N/A')}")
                
                # Test our date filtering logic
                lease_start_str = found_lease.get('start', '')
                lease_end_str = found_lease.get('end', '')
                
                if not lease_start_str:
                    print(f"  ❌ No start date - would be skipped")
                    continue
                
                try:
                    lease_start_dt = datetime.strptime(lease_start_str, "%Y-%m-%d")
                    
                    # Test at-will logic
                    if not lease_end_str or lease_end_str == 'AtWill' or lease_end_str == 'N/A':
                        print(f"  🔍 At-will lease detected")
                        print(f"    lease_start_dt: {lease_start_dt}")
                        print(f"    date_end_dt: {date_end_dt}")
                        print(f"    lease_start_dt <= date_end_dt: {lease_start_dt <= date_end_dt}")
                        
                        if lease_start_dt <= date_end_dt:
                            print(f"  ✅ Should be included (at-will lease)")
                        else:
                            print(f"  ❌ Would be excluded (start date too late)")
                    else:
                        print(f"  🔍 Fixed-term lease")
                        lease_end_dt = datetime.strptime(lease_end_str, "%Y-%m-%d")
                        overlaps = lease_overlaps_date_range(lease_start_dt, lease_end_dt, date_start_dt, date_end_dt)
                        print(f"  {'✅' if overlaps else '❌'} Overlaps: {overlaps}")
                        
                except ValueError as e:
                    print(f"  ❌ Date parsing error: {e}")
                
                await asyncio.sleep(0.1)
                
        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback
            traceback.print_exc()

def main():
    """Main function to run the debug."""
    try:
        asyncio.run(debug_specific_leases())
    except Exception as e:
        print(f"❌ Debug failed: {e}")

if __name__ == "__main__":
    main()

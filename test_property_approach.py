#!/usr/bin/env python3
"""
Test to check if we can get more leases by using property-specific queries
"""

import asyncio
import sys
import os

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from doorloop import get_occupancy, get_doorloop_headers, DOORLOOP_BASE_URL
import httpx
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')

async def test_property_specific_queries():
    """Test if we can get more leases by querying each property separately."""
    
    print("🔍 Testing Property-Specific Queries")
    print("=" * 50)
    
    # First, get all properties
    async with httpx.AsyncClient() as client:
        try:
            headers = get_doorloop_headers()
            response = await client.get(f"{DOORLOOP_BASE_URL}/properties", headers=headers)
            response.raise_for_status()
            properties_data = response.json()
            properties = properties_data.get('data', [])
            
            print(f"Found {len(properties)} properties:")
            for prop in properties[:5]:  # Show first 5
                print(f"  - {prop.get('name', 'Unknown')} (ID: {prop.get('id', 'Unknown')})")
            
        except Exception as e:
            print(f"Error fetching properties: {e}")
            return
    
    # Test the current approach
    print(f"\n📊 Current Approach (All Properties):")
    current_result = await get_occupancy(
        date_start="2025-07-01",
        date_end="2025-07-31"
    )
    print(f"  Total leases: {len(current_result)}")
    
    # Test property-specific approach
    print(f"\n🏢 Property-Specific Approach:")
    all_property_leases = []
    
    for prop in properties[:3]:  # Test first 3 properties
        prop_id = prop.get('id')
        prop_name = prop.get('name', 'Unknown')
        
        if prop_id:
            try:
                prop_result = await get_occupancy(
                    date_start="2025-07-01",
                    date_end="2025-07-31",
                    property_id=prop_id
                )
                print(f"  {prop_name}: {len(prop_result)} leases")
                all_property_leases.extend(prop_result)
                
            except Exception as e:
                print(f"  {prop_name}: Error - {e}")
    
    # Remove duplicates
    unique_leases = []
    seen_ids = set()
    for lease in all_property_leases:
        lease_id = lease.get('id')
        if lease_id and lease_id not in seen_ids:
            unique_leases.append(lease)
            seen_ids.add(lease_id)
    
    print(f"\n📈 Comparison:")
    print(f"  Current approach: {len(current_result)} leases")
    print(f"  Property-specific: {len(unique_leases)} unique leases")
    print(f"  Expected (Excel): 107 leases")
    
    return len(current_result), len(unique_leases)

def main():
    """Main function to run the test."""
    try:
        current_count, property_count = asyncio.run(test_property_specific_queries())
        print(f"\n📊 Results:")
        print(f"  Current: {current_count} leases")
        print(f"  Property-specific: {property_count} leases")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    main()

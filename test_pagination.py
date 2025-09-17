#!/usr/bin/env python3
"""
Test to check pagination and see what's happening
"""

import asyncio
import sys
import os

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from doorloop import get_occupancy
import logging

# Set up logging to see what's happening
logging.basicConfig(level=logging.INFO, format='%(levelname)s:%(name)s:%(message)s')

async def test_pagination():
    """Test pagination to see if all pages are being fetched."""
    
    print("🔍 Testing Pagination and Data Fetching")
    print("=" * 50)
    
    try:
        # Test July 2025
        result = await get_occupancy(
            date_start="2025-07-01",
            date_end="2025-07-31"
        )
        
        print(f"✅ Final Results:")
        print(f"  Total leases returned: {len(result)}")
        
        # Count by status
        active_count = len([l for l in result if l.get('status') == 'ACTIVE'])
        inactive_count = len([l for l in result if l.get('status') == 'INACTIVE'])
        at_will_count = len([l for l in result if l.get('end') in ['AtWill', '', None]])
        
        print(f"  ACTIVE leases: {active_count}")
        print(f"  INACTIVE leases: {inactive_count}")
        print(f"  At-will leases: {at_will_count}")
        
        # Show some sample leases
        print(f"\n📋 Sample Leases:")
        for i, lease in enumerate(result[:10]):
            name = lease.get('name', 'Unknown')
            start = lease.get('start', 'Unknown')
            end = lease.get('end', 'Unknown')
            status = lease.get('status', 'Unknown')
            print(f"  {i+1}. {name} - {start} to {end} ({status})")
        
        return len(result)
        
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()
        return 0

def main():
    """Main function to run the test."""
    try:
        count = asyncio.run(test_pagination())
        print(f"\n📊 Total leases fetched: {count}")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    main()

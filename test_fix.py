#!/usr/bin/env python3
"""
Quick test to verify the get_occupancy fix
"""

import asyncio
import sys
import os

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from doorloop import get_occupancy

async def test_get_occupancy_fix():
    """Test if get_occupancy now returns the correct number of leases."""
    
    print("🧪 Testing get_occupancy fix")
    print("=" * 40)
    
    try:
        # Test July 2025
        result_raw = await get_occupancy(
            date_start="2025-07-01",
            date_end="2025-07-31"
        )
        
        # Handle the new return format [leases, count]
        if isinstance(result_raw, list) and len(result_raw) == 2:
            result = result_raw[0]  # Get the leases list
            count = result_raw[1]  # Get the count
        else:
            result = result_raw
            count = len(result) if result else 0
        
        print(f"✅ get_occupancy Results:")
        print(f"  Returned leases: {len(result)}")
        print(f"  Count: {count}")
        print(f"  Expected: 107 leases (from Excel data)")
        
        if len(result) == 107:
            print(f"🎉 SUCCESS! Function now returns correct number of leases!")
        elif len(result) > 60:
            print(f"✅ IMPROVEMENT! Function now returns {len(result)} leases (was 60)")
            print(f"   Still missing {107 - len(result)} leases")
        else:
            print(f"❌ STILL ISSUE! Function still returns {len(result)} leases")
        
        # Show sample results
        print(f"\nSample returned leases:")
        for i, lease in enumerate(result[:5]):
            lease_name = lease.get('name', 'Unknown')
            lease_start = lease.get('start', 'Unknown')
            lease_end = lease.get('end', 'Unknown')
            print(f"  {i+1}. {lease_name} - {lease_start} to {lease_end}")
        
        return len(result)
        
    except Exception as e:
        print(f"❌ Error testing get_occupancy: {e}")
        import traceback
        traceback.print_exc()
        return 0

def main():
    """Main function to run the test."""
    try:
        count = asyncio.run(test_get_occupancy_fix())
        print(f"\n📊 Final count: {count} leases")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")

if __name__ == "__main__":
    main()

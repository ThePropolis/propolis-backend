#!/usr/bin/env python3
"""
Final comparison between Excel data and API results
"""

import pandas as pd
import asyncio
import sys
import os
from datetime import datetime

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from doorloop import get_occupancy

async def final_comparison():
    """Final comparison between Excel and API data."""
    
    print("🔍 Final Comparison: Excel vs API")
    print("=" * 50)
    
    # Load Excel data
    df = pd.read_excel('PropolisManagement_Report-Leasing_2025-07-01_2025-07-31.xlsx')
    data_df = df.iloc[3:].copy()
    data_df.columns = ['Lease', 'Start Date', 'End Date', 'Status', 'Property', 'Unit', 'Rent', 'Deposits', 'Current Balance']
    data_df = data_df.dropna(subset=['Lease'])
    data_df['Start Date'] = pd.to_datetime(data_df['Start Date'])
    data_df['End Date'] = pd.to_datetime(data_df['End Date'], errors='coerce')
    
    start_date = "2025-07-01"
    end_date = "2025-07-31"
    start_dt = pd.to_datetime(start_date)
    end_dt = pd.to_datetime(end_date)
    
    # Get Excel overlapping leases
    excel_overlapping = []
    for _, lease in data_df.iterrows():
        lease_start = lease['Start Date']
        lease_end = lease['End Date']
        
        if pd.isna(lease_start):
            continue
        
        overlaps = False
        if pd.isna(lease_end):
            overlaps = lease_start <= end_dt
        else:
            overlaps = lease_start <= end_dt and lease_end >= start_dt
        
        if overlaps:
            excel_overlapping.append(lease)
    
    # Get API results
    api_result = await get_occupancy(
        date_start=start_date,
        date_end=end_date
    )
    
    print(f"📊 Final Results:")
    print(f"  Excel overlapping leases: {len(excel_overlapping)}")
    print(f"  API overlapping leases: {len(api_result)}")
    print(f"  Difference: {len(excel_overlapping) - len(api_result)} leases")
    
    # Calculate accuracy
    accuracy = (len(api_result) / len(excel_overlapping)) * 100
    print(f"  Accuracy: {accuracy:.1f}%")
    
    # Show breakdown by property
    print(f"\n📋 Excel Leases by Property:")
    excel_by_property = {}
    for lease in excel_overlapping:
        prop = lease['Property']
        if prop not in excel_by_property:
            excel_by_property[prop] = []
        excel_by_property[prop].append(lease)
    
    for prop, leases in excel_by_property.items():
        print(f"  {prop}: {len(leases)} leases")
    
    print(f"\n📡 API Leases by Property:")
    api_by_property = {}
    for lease in api_result:
        prop = lease.get('property', 'Unknown')
        if prop not in api_by_property:
            api_by_property[prop] = []
        api_by_property[prop].append(lease)
    
    for prop, leases in api_by_property.items():
        print(f"  {prop}: {len(leases)} leases")
    
    # Show some sample leases from each
    print(f"\n📋 Sample Excel Leases:")
    for i, lease in enumerate(excel_overlapping[:5]):
        end_date_str = 'At-will' if pd.isna(lease['End Date']) else lease['End Date'].strftime('%Y-%m-%d')
        print(f"  {i+1}. {lease['Lease']} ({lease['Property']}) - {lease['Start Date'].strftime('%Y-%m-%d')} to {end_date_str}")
    
    print(f"\n📡 Sample API Leases:")
    for i, lease in enumerate(api_result[:5]):
        lease_name = lease.get('name', 'Unknown')
        lease_start = lease.get('start', 'Unknown')
        lease_end = lease.get('end', 'Unknown')
        print(f"  {i+1}. {lease_name} - {lease_start} to {lease_end}")
    
    return len(excel_overlapping), len(api_result)

def main():
    """Main function to run the comparison."""
    try:
        excel_count, api_count = asyncio.run(final_comparison())
        print(f"\n🎯 Summary:")
        print(f"  Excel: {excel_count} leases")
        print(f"  API: {api_count} leases")
        print(f"  Missing: {excel_count - api_count} leases")
        
        if api_count >= excel_count * 0.9:  # 90% accuracy
            print(f"✅ SUCCESS! API results are very close to Excel data!")
        elif api_count >= excel_count * 0.8:  # 80% accuracy
            print(f"✅ GOOD! API results are close to Excel data.")
        else:
            print(f"⚠️  API results still missing significant data.")
        
    except Exception as e:
        print(f"❌ Comparison failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

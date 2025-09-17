#!/usr/bin/env python3
"""
Analyze which specific leases are being missed by comparing Excel vs API data
"""

import pandas as pd
import asyncio
import sys
import os
from datetime import datetime

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from doorloop import get_occupancy

async def analyze_missing_leases():
    """Analyze which specific leases are missing from API results."""
    
    print("🔍 Analyzing Missing Leases")
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
    api_result_raw = await get_occupancy(
        date_start=start_date,
        date_end=end_date
    )
    
    # Handle the new return format [leases, count]
    if isinstance(api_result_raw, list) and len(api_result_raw) == 2:
        api_result = api_result_raw[0]  # Get the leases list
    else:
        api_result = api_result_raw
    
    # Extract API lease names for comparison
    api_lease_names = set()
    for lease in api_result:
        lease_name = lease.get('name', '').strip()
        if lease_name:
            api_lease_names.add(lease_name)
    
    print(f"📊 Data Summary:")
    print(f"  Excel overlapping leases: {len(excel_overlapping)}")
    print(f"  API overlapping leases: {len(api_result)}")
    print(f"  API unique lease names: {len(api_lease_names)}")
    
    # Find missing leases
    missing_leases = []
    found_leases = []
    
    for excel_lease in excel_overlapping:
        excel_name = excel_lease['Lease'].strip()
        excel_property = excel_lease['Property']
        excel_start = excel_lease['Start Date'].strftime('%Y-%m-%d')
        excel_end = 'At-will' if pd.isna(excel_lease['End Date']) else excel_lease['End Date'].strftime('%Y-%m-%d')
        
        # Check if this lease exists in API results
        found = False
        for api_lease in api_result:
            api_name = api_lease.get('name', '').strip()
            if api_name == excel_name:
                found = True
                found_leases.append({
                    'excel': excel_lease,
                    'api': api_lease,
                    'name': excel_name
                })
                break
        
        if not found:
            missing_leases.append({
                'name': excel_name,
                'property': excel_property,
                'start': excel_start,
                'end': excel_end,
                'status': excel_lease['Status']
            })
    
    print(f"\n❌ Missing Leases ({len(missing_leases)}):")
    print("-" * 30)
    for i, lease in enumerate(missing_leases, 1):
        print(f"{i:2d}. {lease['name']} ({lease['property']})")
        print(f"     {lease['start']} to {lease['end']} - {lease['status']}")
    
    print(f"\n✅ Found Leases ({len(found_leases)}):")
    print("-" * 30)
    for i, lease in enumerate(found_leases[:10], 1):  # Show first 10
        excel_lease = lease['excel']
        api_lease = lease['api']
        print(f"{i:2d}. {lease['name']}")
        print(f"     Excel: {excel_lease['Start Date'].strftime('%Y-%m-%d')} to {'At-will' if pd.isna(excel_lease['End Date']) else excel_lease['End Date'].strftime('%Y-%m-%d')}")
        print(f"     API:   {api_lease.get('start', 'N/A')} to {api_lease.get('end', 'N/A')}")
    
    if len(found_leases) > 10:
        print(f"     ... and {len(found_leases) - 10} more")
    
    # Analyze missing leases by property
    print(f"\n📋 Missing Leases by Property:")
    print("-" * 30)
    missing_by_property = {}
    for lease in missing_leases:
        prop = lease['property']
        if prop not in missing_by_property:
            missing_by_property[prop] = []
        missing_by_property[prop].append(lease)
    
    for prop, leases in missing_by_property.items():
        print(f"  {prop}: {len(leases)} missing")
        for lease in leases:
            print(f"    - {lease['name']} ({lease['start']} to {lease['end']})")
    
    # Analyze missing leases by status
    print(f"\n📊 Missing Leases by Status:")
    print("-" * 30)
    missing_by_status = {}
    for lease in missing_leases:
        status = lease['status']
        if status not in missing_by_status:
            missing_by_status[status] = []
        missing_by_status[status].append(lease)
    
    for status, leases in missing_by_status.items():
        print(f"  {status}: {len(leases)} missing")
    
    # Analyze missing leases by date pattern
    print(f"\n📅 Missing Leases by Date Pattern:")
    print("-" * 30)
    at_will_missing = 0
    recent_start_missing = 0
    old_leases_missing = 0
    
    for lease in missing_leases:
        if lease['end'] == 'At-will':
            at_will_missing += 1
        elif lease['start'] >= '2025-01-01':
            recent_start_missing += 1
        else:
            old_leases_missing += 1
    
    print(f"  At-will leases: {at_will_missing}")
    print(f"  Recent leases (2025+): {recent_start_missing}")
    print(f"  Older leases (<2025): {old_leases_missing}")
    
    return missing_leases, found_leases

def main():
    """Main function to run the analysis."""
    try:
        missing, found = asyncio.run(analyze_missing_leases())
        print(f"\n🎯 Summary:")
        print(f"  Total Excel leases: {len(missing) + len(found)}")
        print(f"  Found in API: {len(found)}")
        print(f"  Missing from API: {len(missing)}")
        print(f"  Success rate: {len(found)/(len(missing) + len(found))*100:.1f}%")
        
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

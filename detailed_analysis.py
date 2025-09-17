#!/usr/bin/env python3
"""
Detailed analysis to find the remaining missing leases
"""

import pandas as pd
import sys
import os
from datetime import datetime

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from doorloop import get_occupancy
import asyncio

async def detailed_analysis():
    """Detailed analysis to find remaining missing leases."""
    
    print("🔍 Detailed Analysis: Finding Missing Leases")
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
    
    print(f"📊 Excel Analysis:")
    print(f"  Total overlapping leases: {len(excel_overlapping)}")
    
    # Get API results
    api_result = await get_occupancy(
        date_start=start_date,
        date_end=end_date
    )
    
    print(f"📡 API Results:")
    print(f"  Returned leases: {len(api_result)}")
    print(f"  Missing: {len(excel_overlapping) - len(api_result)} leases")
    
    # Analyze by status
    excel_by_status = {}
    for lease in excel_overlapping:
        status = lease['Status']
        if status not in excel_by_status:
            excel_by_status[status] = []
        excel_by_status[status].append(lease)
    
    print(f"\n📋 Excel Leases by Status:")
    for status, leases in excel_by_status.items():
        print(f"  {status}: {len(leases)} leases")
    
    # Check if API is filtering by status
    api_by_status = {}
    for lease in api_result:
        status = lease.get('status', 'Unknown')
        if status not in api_by_status:
            api_by_status[status] = []
        api_by_status[status].append(lease)
    
    print(f"\n📡 API Leases by Status:")
    for status, leases in api_by_status.items():
        print(f"  {status}: {len(leases)} leases")
    
    # Check for date format issues
    print(f"\n🔍 Checking for Date Format Issues:")
    excel_at_will = [lease for lease in excel_overlapping if pd.isna(lease['End Date'])]
    api_at_will = [lease for lease in api_result if lease.get('end') in ['AtWill', '', None]]
    
    print(f"  Excel at-will leases: {len(excel_at_will)}")
    print(f"  API at-will leases: {len(api_at_will)}")
    
    # Show sample at-will leases from Excel
    print(f"\n📋 Sample Excel At-will Leases:")
    for i, lease in enumerate(excel_at_will[:5]):
        print(f"  {i+1}. {lease['Lease']} - Started: {lease['Start Date'].strftime('%Y-%m-%d')}")
    
    # Show sample at-will leases from API
    print(f"\n📡 Sample API At-will Leases:")
    for i, lease in enumerate(api_at_will[:5]):
        lease_name = lease.get('name', 'Unknown')
        lease_start = lease.get('start', 'Unknown')
        print(f"  {i+1}. {lease_name} - Started: {lease_start}")
    
    return len(excel_overlapping), len(api_result)

def main():
    """Main function to run the analysis."""
    try:
        excel_count, api_count = asyncio.run(detailed_analysis())
        print(f"\n📊 Summary:")
        print(f"  Excel: {excel_count} leases")
        print(f"  API: {api_count} leases")
        print(f"  Missing: {excel_count - api_count} leases")
        
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

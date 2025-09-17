#!/usr/bin/env python3
"""
Test to identify why get_occupancy returns 60 leases instead of 107
"""

import pandas as pd
import sys
import os
from datetime import datetime

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def analyze_discrepancy():
    """Analyze the discrepancy between Excel data and get_occupancy function."""
    
    print("🔍 Analyzing Discrepancy: Excel (107) vs get_occupancy (60)")
    print("=" * 60)
    
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
    
    # Count leases by type
    total_leases = len(data_df)
    leases_with_end_date = len(data_df.dropna(subset=['End Date']))
    at_will_leases = len(data_df[data_df['End Date'].isna()])
    
    print(f"📊 Excel Data Breakdown:")
    print(f"  Total leases in Excel: {total_leases}")
    print(f"  Leases with end date: {leases_with_end_date}")
    print(f"  At-will leases (no end date): {at_will_leases}")
    
    # Find overlapping leases
    overlapping_leases = []
    overlapping_with_end_date = []
    overlapping_at_will = []
    
    for _, lease in data_df.iterrows():
        lease_start = lease['Start Date']
        lease_end = lease['End Date']
        
        if pd.isna(lease_start):
            continue
        
        overlaps = False
        if pd.isna(lease_end):
            # At-will lease
            overlaps = lease_start <= end_dt
            if overlaps:
                overlapping_at_will.append(lease)
        else:
            # Fixed-term lease
            overlaps = lease_start <= end_dt and lease_end >= start_dt
            if overlaps:
                overlapping_with_end_date.append(lease)
        
        if overlaps:
            overlapping_leases.append(lease)
    
    print(f"\n📅 Overlapping Leases Analysis:")
    print(f"  Total overlapping: {len(overlapping_leases)}")
    print(f"  With end date: {len(overlapping_with_end_date)}")
    print(f"  At-will (no end date): {len(overlapping_at_will)}")
    
    print(f"\n🚨 ISSUE IDENTIFIED:")
    print(f"  get_occupancy function skips leases without end dates")
    print(f"  This excludes {len(overlapping_at_will)} at-will leases!")
    print(f"  Expected: {len(overlapping_leases)} leases")
    print(f"  Actual (get_occupancy): {len(overlapping_with_end_date)} leases")
    print(f"  Missing: {len(overlapping_at_will)} at-will leases")
    
    print(f"\n📋 At-will leases being excluded:")
    for i, lease in enumerate(overlapping_at_will[:10]):
        print(f"  {i+1}. {lease['Lease']} ({lease['Property']}) - Started: {lease['Start Date'].strftime('%Y-%m-%d')}")
    
    return overlapping_at_will

def show_fix():
    """Show the fix needed in get_occupancy function."""
    
    print(f"\n🔧 REQUIRED FIX in get_occupancy function:")
    print("=" * 50)
    
    print("CURRENT CODE (lines 2497-2498):")
    print("```python")
    print("# Skip leases without dates")
    print("if not lease_start_str or not lease_end_str:")
    print("    continue")
    print("```")
    
    print("\nPROBLEM: This skips at-will leases (no end date)")
    
    print("\nFIXED CODE:")
    print("```python")
    print("# Skip leases without start dates")
    print("if not lease_start_str:")
    print("    continue")
    print("")
    print("# Handle at-will leases (no end date)")
    print("if not lease_end_str or lease_end_str == 'AtWill':")
    print("    # At-will lease - overlaps if started before or during the period")
    print("    lease_start_dt = datetime.strptime(lease_start_str, '%Y-%m-%d')")
    print("    if lease_start_dt <= date_end_dt:")
    print("        overlapped_leases.append(lease)")
    print("    continue")
    print("")
    print("# Handle fixed-term leases")
    print("lease_start_dt = datetime.strptime(lease_start_str, '%Y-%m-%d')")
    print("lease_end_dt = datetime.strptime(lease_end_str, '%Y-%m-%d')")
    print("if lease_overlaps_date_range(lease_start_dt, lease_end_dt, date_start_dt, date_end_dt):")
    print("    overlapped_leases.append(lease)")
    print("```")

def main():
    """Main function to run the analysis."""
    try:
        at_will_leases = analyze_discrepancy()
        show_fix()
        
        print(f"\n✅ Analysis complete!")
        print(f"The get_occupancy function is missing {len(at_will_leases)} at-will leases")
        print(f"because it skips leases without end dates.")
        
    except Exception as e:
        print(f"❌ Analysis failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

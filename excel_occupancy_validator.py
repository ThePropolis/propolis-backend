#!/usr/bin/env python3
"""
Direct integration script that uses Excel data to test and validate 
the get_occupancy_rate function from doorloop.py
"""

import pandas as pd
import asyncio
import sys
import os
from datetime import datetime

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from doorloop import get_occupancy

class ExcelOccupancyValidator:
    """Validates occupancy calculations using Excel data."""
    
    def __init__(self, excel_file_path):
        """Initialize with Excel file path."""
        self.excel_file_path = excel_file_path
        self.leases_data = None
        self.load_excel_data()
    
    def load_excel_data(self):
        """Load and process Excel data."""
        try:
            # Read the Excel file
            df = pd.read_excel(self.excel_file_path)
            
            # Skip the header rows and get the actual data
            data_df = df.iloc[3:].copy()  # Skip first 3 rows (title, empty, headers)
            
            # Set proper column names
            data_df.columns = ['Lease', 'Start Date', 'End Date', 'Status', 'Property', 'Unit', 'Rent', 'Deposits', 'Current Balance']
            
            # Remove rows with NaN in Lease column (empty rows)
            data_df = data_df.dropna(subset=['Lease'])
            
            # Convert dates to datetime
            data_df['Start Date'] = pd.to_datetime(data_df['Start Date'])
            data_df['End Date'] = pd.to_datetime(data_df['End Date'], errors='coerce')
            
            # Clean up Status column
            data_df['Status'] = data_df['Status'].fillna('Unknown')
            
            # Clean up Property column
            data_df['Property'] = data_df['Property'].fillna('Unknown Property')
            
            self.leases_data = data_df
            
            print(f"✅ Loaded {len(data_df)} leases from Excel file")
            print(f"Properties: {sorted(data_df['Property'].unique())}")
            print(f"Status values: {sorted(data_df['Status'].unique())}")
            
        except Exception as e:
            print(f"❌ Error loading Excel file: {e}")
            raise
    
    def calculate_excel_occupancy(self, start_date, end_date):
        """Calculate occupancy based on Excel data using the same logic as get_occupancy_rate."""
        
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        
        # Filter for active leases that overlap the date range
        active_overlapping_leases = []
        
        for _, lease in self.leases_data.iterrows():
            # Only consider active leases
            if lease['Status'] != 'Active':
                continue
            
            lease_start = lease['Start Date']
            lease_end = lease['End Date']
            
            # Skip if no start date
            if pd.isna(lease_start):
                continue
            
            # Check for overlap using the same logic as lease_overlaps_date_range
            overlaps = False
            
            if pd.isna(lease_end):
                # At-will lease (no end date) - overlaps if started before or during the period
                overlaps = lease_start <= end_dt
            else:
                # Fixed-term lease - overlaps if lease period intersects with our period
                overlaps = lease_start <= end_dt and lease_end >= start_dt
            
            if overlaps:
                active_overlapping_leases.append(lease)
        
        # Get unique units from overlapping active leases
        unique_units = set()
        for lease in active_overlapping_leases:
            unit = lease['Unit']
            if pd.notna(unit):
                unique_units.add(unit)
        
        occupied_units = len(unique_units)
        
        # Get total units (all unique units in the dataset)
        all_units = set()
        for _, lease in self.leases_data.iterrows():
            unit = lease['Unit']
            if pd.notna(unit):
                all_units.add(unit)
        
        total_units = len(all_units)
        
        occupancy_rate = (occupied_units / total_units * 100) if total_units > 0 else 0
        
        return {
            'occupied_units': occupied_units,
            'total_units': total_units,
            'occupancy_rate': round(occupancy_rate, 2),
            'active_leases_count': len(active_overlapping_leases),
            'unique_units': sorted(list(unique_units)),
            'overlapping_leases': active_overlapping_leases
        }
    
    def print_detailed_analysis(self, start_date, end_date):
        """Print detailed analysis of occupancy for the date range."""
        print(f"\n📊 Detailed Occupancy Analysis for {start_date} to {end_date}")
        print("=" * 70)
        
        # Calculate Excel-based occupancy
        excel_result = self.calculate_excel_occupancy(start_date, end_date)
        
        print(f"📈 Excel Data Results:")
        print(f"  Active leases overlapping period: {excel_result['active_leases_count']}")
        print(f"  Unique occupied units: {excel_result['occupied_units']}")
        print(f"  Total units in dataset: {excel_result['total_units']}")
        print(f"  Occupancy rate: {excel_result['occupancy_rate']}%")
        
        # Show breakdown by property
        print(f"\n🏢 Breakdown by Property:")
        property_counts = {}
        property_units = {}
        
        for lease in excel_result['overlapping_leases']:
            prop = lease['Property']
            unit = lease['Unit']
            
            if prop not in property_counts:
                property_counts[prop] = 0
                property_units[prop] = set()
            
            property_counts[prop] += 1
            if pd.notna(unit):
                property_units[prop].add(unit)
        
        for prop in sorted(property_counts.keys()):
            count = property_counts[prop]
            units = len(property_units[prop])
            print(f"  {prop}: {count} leases, {units} unique units")
        
        # Show at-will leases
        at_will_leases = [lease for lease in excel_result['overlapping_leases'] if pd.isna(lease['End Date'])]
        if at_will_leases:
            print(f"\n🔄 At-will leases (no end date): {len(at_will_leases)}")
            for lease in at_will_leases[:10]:  # Show first 10
                print(f"  - {lease['Lease']} ({lease['Property']}) - Started: {lease['Start Date'].strftime('%Y-%m-%d')}")
        
        # Show some sample overlapping leases
        print(f"\n📋 Sample Overlapping Leases:")
        for i, lease in enumerate(excel_result['overlapping_leases'][:10]):
            end_date_str = lease['End Date'].strftime('%Y-%m-%d') if pd.notna(lease['End Date']) else 'At-will'
            print(f"  {i+1}. {lease['Lease']} ({lease['Property']}) - {lease['Start Date'].strftime('%Y-%m-%d')} to {end_date_str}")
        
        return excel_result

async def test_with_real_api():
    """Test the actual get_occupancy function (requires real API access)."""
    print(f"\n🌐 Testing with Real DoorLoop API...")
    print("=" * 50)
    
    try:
        # Test July 2025
        result = await get_occupancy(
            date_start="2025-07-01",
            date_end="2025-07-31"
        )
        
        print(f"✅ Real API Results:")
        print(f"  Occupied Units: {result['occupied_units']}")
        print(f"  Total Units: {result['total_units']}")
        print(f"  Occupancy Rate: {result['occupancy_rate']}%")
        print(f"  Date Range: {result['date_from']} to {result['date_to']}")
        
        return result
        
    except Exception as e:
        print(f"❌ Error calling real API: {e}")
        return None

def main():
    """Main function to run the analysis."""
    print("🧪 Excel Occupancy Validator")
    print("=" * 50)
    
    # Initialize validator
    validator = ExcelOccupancyValidator('PropolisManagement_Report-Leasing_2025-07-01_2025-07-31.xlsx')
    
    # Test different date ranges
    test_ranges = [
        ("2025-07-01", "2025-07-31"),  # July 2025
    ]
    
    excel_results = {}
    
    for start_date, end_date in test_ranges:
        excel_result = validator.print_detailed_analysis(start_date, end_date)
        excel_results[f"{start_date}_to_{end_date}"] = excel_result
        print("\n" + "="*80 + "\n")
    
    # Try to test with real API if possible
    print("🔄 Attempting to test with real DoorLoop API...")
    try:
        real_result = asyncio.run(test_with_real_api())
        
        if real_result:
            # Compare with Excel results for July 2025
            july_excel = excel_results["2025-07-01_to_2025-07-31"]
            
            print(f"\n📊 Comparison: Excel vs Real API (July 2025)")
            print("=" * 50)
            print(f"Excel Data:")
            print(f"  Occupied Units: {july_excel['occupied_units']}")
            print(f"  Total Units: {july_excel['total_units']}")
            print(f"  Occupancy Rate: {july_excel['occupancy_rate']}%")
            
            print(f"\nReal API:")
            print(f"  Occupied Units: {real_result['occupied_units']}")
            print(f"  Total Units: {real_result['total_units']}")
            print(f"  Occupancy Rate: {real_result['occupancy_rate']}%")
            
            # Calculate differences
            occupied_diff = abs(real_result['occupied_units'] - july_excel['occupied_units'])
            total_diff = abs(real_result['total_units'] - july_excel['total_units'])
            rate_diff = abs(real_result['occupancy_rate'] - july_excel['occupancy_rate'])
            
            print(f"\nDifferences:")
            print(f"  Occupied Units: ±{occupied_diff}")
            print(f"  Total Units: ±{total_diff}")
            print(f"  Occupancy Rate: ±{rate_diff}%")
            
    except Exception as e:
        print(f"⚠️  Could not test with real API: {e}")
        print("This is normal if API credentials are not configured.")
    
    print(f"\n✅ Analysis complete!")

if __name__ == "__main__":
    main()

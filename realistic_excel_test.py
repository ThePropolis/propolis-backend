#!/usr/bin/env python3
"""
Realistic test script that connects get_occupancy_rate function to Excel data.
This script accounts for the fact that the Excel file shows lease history for 
individual units rather than all units in the properties.
"""

import pandas as pd
import asyncio
import sys
import os
from datetime import datetime
from unittest.mock import AsyncMock, patch
import httpx

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from doorloop import get_occupancy_rate

class RealisticExcelOccupancyTester:
    """Realistic tester that accounts for Excel data limitations."""
    
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
            data_df = df.iloc[3:].copy()
            data_df.columns = ['Lease', 'Start Date', 'End Date', 'Status', 'Property', 'Unit', 'Rent', 'Deposits', 'Current Balance']
            
            # Remove rows with NaN in Lease column
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
            print(f"Unique units in Excel: {len(data_df['Unit'].dropna().unique())}")
            
        except Exception as e:
            print(f"❌ Error loading Excel file: {e}")
            raise
    
    def create_realistic_mock_data(self, start_date, end_date):
        """
        Create realistic mock data based on Excel data.
        Since Excel only shows 5 units, we'll simulate a realistic scenario
        where each property has multiple units.
        """
        
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        
        # Get active leases that overlap the date range
        active_overlapping_leases = []
        
        for _, lease in self.leases_data.iterrows():
            if lease['Status'] != 'Active':
                continue
            
            lease_start = lease['Start Date']
            lease_end = lease['End Date']
            
            if pd.isna(lease_start):
                continue
            
            # Check for overlap
            overlaps = False
            if pd.isna(lease_end):
                overlaps = lease_start <= end_dt
            else:
                overlaps = lease_start <= end_dt and lease_end >= start_dt
            
            if overlaps:
                active_overlapping_leases.append(lease)
        
        # Create realistic mock data
        # Assume each property has multiple units (based on typical apartment buildings)
        property_unit_counts = {
            'Aerie Apartments': 25,    # Assume 25 units
            'Otto Apartments': 30,     # Assume 30 units  
            'Pastel Apartments': 20,   # Assume 20 units
            'Plum Apartments': 25,     # Assume 25 units
            'Saffron Apartments': 21,  # Assume 21 units
        }
        
        # Create mock leases with unique unit IDs
        mock_leases = []
        unit_counter = 1
        
        for i, lease in enumerate(active_overlapping_leases):
            property_name = lease['Property']
            if property_name in property_unit_counts:
                # Create multiple leases per property to simulate multiple units
                units_per_property = min(property_unit_counts[property_name], len(active_overlapping_leases))
                
                for j in range(units_per_property):
                    mock_lease = {
                        "id": f"lease_{unit_counter}",
                        "units": [f"unit_{unit_counter}"],
                        "start": lease['Start Date'].strftime("%Y-%m-%d"),
                        "end": lease['End Date'].strftime("%Y-%m-%d") if pd.notna(lease['End Date']) else "AtWill",
                        "status": "ACTIVE",
                        "property": f"property_{property_name.replace(' ', '_').lower()}",
                        "name": f"{lease['Lease']} - Unit {unit_counter}",
                        "recurringRentFrequency": "Monthly",
                        "reference": f"ref-{unit_counter}",
                        "term": "Fixed" if pd.notna(lease['End Date']) else "AtWill",
                        "totalRecurringRent": lease['Rent'] if pd.notna(lease['Rent']) else 1500,
                    }
                    mock_leases.append(mock_lease)
                    unit_counter += 1
                    
                    # Only create a few leases per property to keep it realistic
                    if j >= 2:  # Max 3 leases per property
                        break
        
        # Create mock units data
        total_units = sum(property_unit_counts.values())
        mock_units = [{"id": f"unit_{i}", "property_id": "test_property"} for i in range(1, total_units + 1)]
        
        return mock_leases, mock_units, total_units
    
    def print_realistic_analysis(self, start_date, end_date):
        """Print realistic analysis based on Excel data."""
        print(f"\n📊 Realistic Occupancy Analysis for {start_date} to {end_date}")
        print("=" * 70)
        
        # Get Excel data analysis
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)
        
        active_overlapping_leases = []
        for _, lease in self.leases_data.iterrows():
            if lease['Status'] != 'Active':
                continue
            
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
                active_overlapping_leases.append(lease)
        
        print(f"📈 Excel Data Analysis:")
        print(f"  Active leases overlapping period: {len(active_overlapping_leases)}")
        print(f"  Unique units in Excel: {len(self.leases_data['Unit'].dropna().unique())}")
        
        # Create realistic mock data
        mock_leases, mock_units, total_units = self.create_realistic_mock_data(start_date, end_date)
        
        print(f"\n🏗️  Realistic Scenario (Simulated):")
        print(f"  Simulated occupied units: {len(mock_leases)}")
        print(f"  Simulated total units: {total_units}")
        print(f"  Simulated occupancy rate: {len(mock_leases)/total_units*100:.2f}%")
        
        # Show breakdown by property
        print(f"\n🏢 Breakdown by Property:")
        property_counts = {}
        for lease in active_overlapping_leases:
            prop = lease['Property']
            if prop not in property_counts:
                property_counts[prop] = 0
            property_counts[prop] += 1
        
        for prop in sorted(property_counts.keys()):
            count = property_counts[prop]
            print(f"  {prop}: {count} active leases")
        
        return mock_leases, mock_units, total_units

async def test_with_realistic_mock_data():
    """Test get_occupancy_rate with realistic mock data based on Excel."""
    
    tester = RealisticExcelOccupancyTester('PropolisManagement_Report-Leasing_2025-07-01_2025-07-31.xlsx')
    
    # Test July 2025
    start_date = "2025-07-01"
    end_date = "2025-07-31"
    
    # Get realistic mock data
    mock_leases, mock_units, expected_total_units = tester.print_realistic_analysis(start_date, end_date)
    
    # Mock httpx.AsyncClient for leases
    mock_leases_client = AsyncMock(spec=httpx.AsyncClient)
    
    # Prepare paginated responses for leases
    lease_responses = []
    total_leases = len(mock_leases)
    limit = 50
    
    for i in range(0, total_leases, limit):
        page_leases = mock_leases[i : i + limit]
        mock_response = AsyncMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "data": page_leases,
            "total": total_leases
        }
        mock_response.raise_for_status.return_value = None
        lease_responses.append(mock_response)
    
    # Add empty response to signal end
    empty_response = AsyncMock()
    empty_response.status_code = 200
    empty_response.json.return_value = {"data": [], "total": total_leases}
    empty_response.raise_for_status.return_value = None
    lease_responses.append(empty_response)
    
    # Configure mock client for leases
    mock_leases_client.get.side_effect = lease_responses
    
    # Mock httpx.AsyncClient for units
    mock_units_client = AsyncMock(spec=httpx.AsyncClient)
    
    # Prepare response for units
    units_response = AsyncMock()
    units_response.status_code = 200
    units_response.json.return_value = {
        "data": mock_units,
        "total": len(mock_units)
    }
    units_response.raise_for_status.return_value = None
    
    mock_units_client.get.return_value = units_response
    
    # Patch httpx.AsyncClient to use our mocks
    with patch('httpx.AsyncClient') as mock_httpx:
        mock_httpx.side_effect = [mock_leases_client, mock_units_client]
        
        # Call the function under test
        result = await get_occupancy_rate(
            date_start=start_date,
            date_end=end_date
        )
        
        print(f"\n✅ Test Results:")
        print(f"  Occupied Units: {result['occupied_units']}")
        print(f"  Total Units: {result['total_units']}")
        print(f"  Occupancy Rate: {result['occupancy_rate']}%")
        print(f"  Date Range: {result['date_from']} to {result['date_to']}")
        
        # Verify results
        assert result["occupied_units"] == len(mock_leases)
        assert result["total_units"] == len(mock_units)
        assert result["date_from"] == start_date
        assert result["date_to"] == end_date
        
        print(f"\n🎉 Test passed! Function correctly processed {len(mock_leases)} occupied units out of {len(mock_units)} total units.")
        
        return result

def main():
    """Main function to run the realistic test."""
    print("🧪 Realistic Excel Occupancy Test")
    print("=" * 50)
    
    try:
        result = asyncio.run(test_with_realistic_mock_data())
        print(f"\n✅ Test completed successfully!")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()

"""
Comprehensive Excel Data Import Script for Propolis
Imports all data from Master Sheet.cash.xlsx to Supabase

Tables created (matching backend expectations):
1. properties - Master list of properties
2. pnl_data - Profit & Loss data (consolidated)
3. str_data - Short Term Rental revenue data (consolidated, replaces STR-xxx tables)
4. rentroll_data - Rent roll data (consolidated)
5. rent_paid_data - Rent payment tracking (consolidated, replaces Rent-Paid-xxx tables)
"""

import pandas as pd
import os
import re
from datetime import datetime
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

EXCEL_FILE = "/Users/Coding/propolis-backend/Master Sheet.cash.xlsx"

# Property name mapping
PROPERTIES = ["Aerie", "Otto", "Pastel", "Olive", "Saffron", "Plum"]

def parse_month_year(sheet_name: str) -> tuple:
    """Extract month and year from sheet name"""
    # Handle various naming patterns
    patterns = [
        r'(\w+)-(\d{4})',  # P&L-Jan-2024, Rentroll-Jan-2024
        r'(\w+)- (\d{4})',  # STR- Mar-2024
        r'(\w+) (\d{4})',   # Rent Paid Jan 2024
        r'(\w+)\.- (\d{4})', # STR-Jun.- 2025
    ]

    month_map = {
        'jan': 1, 'january': 1,
        'feb': 2, 'february': 2,
        'mar': 3, 'march': 3, 'mach': 3,
        'apr': 4, 'april': 4,
        'may': 5,
        'jun': 6, 'june': 6,
        'jul': 7, 'july': 7,
        'aug': 8, 'august': 8, 'agust': 8,
        'sep': 9, 'sept': 9, 'september': 9,
        'oct': 10, 'october': 10,
        'nov': 11, 'november': 11,
        'dec': 12, 'december': 12,
    }

    # Clean sheet name
    clean_name = sheet_name.strip().lower()

    for pattern in patterns:
        match = re.search(pattern, clean_name, re.IGNORECASE)
        if match:
            month_str = match.group(1).strip().lower()
            year = int(match.group(2))
            month = month_map.get(month_str, None)
            if month:
                return month, year

    return None, None


def import_properties():
    """Create properties master table"""
    print("\n" + "="*60)
    print("IMPORTING PROPERTIES")
    print("="*60)

    properties_data = []
    for i, prop in enumerate(PROPERTIES):
        properties_data.append({
            "id": i + 1,
            "name": prop,
            "full_name": f"{prop} Apartments",
            "active": True
        })

    # Delete existing and insert fresh
    try:
        supabase.table("properties").delete().gte("id", 0).execute()
    except Exception as e:
        print(f"Note: Could not delete existing properties: {e}")

    result = supabase.table("properties").insert(properties_data).execute()
    print(f"✅ Imported {len(properties_data)} properties")
    return result


def import_pnl_data(xlsx):
    """Import Profit & Loss data from all P&L sheets"""
    print("\n" + "="*60)
    print("IMPORTING P&L DATA")
    print("="*60)

    pnl_sheets = [s for s in xlsx.sheet_names if s.startswith('P&L')]
    all_pnl_data = []

    for sheet_name in pnl_sheets:
        month, year = parse_month_year(sheet_name)
        if not month or not year:
            print(f"⚠️ Skipping {sheet_name} - couldn't parse date")
            continue

        print(f"Processing {sheet_name} ({month}/{year})...")
        df = pd.read_excel(xlsx, sheet_name=sheet_name)

        # Find the header row (contains "Account")
        header_row = None
        for idx, row in df.iterrows():
            if 'Account' in str(row.values):
                header_row = idx
                break

        if header_row is None:
            print(f"⚠️ Couldn't find header row in {sheet_name}")
            continue

        # Get property columns from header
        header = df.iloc[header_row]
        property_cols = {}
        for col_idx, col_val in enumerate(header):
            col_str = str(col_val).strip()
            for prop in PROPERTIES:
                if prop in col_str:
                    property_cols[prop] = col_idx
                    break

        # Parse data rows
        current_category = None
        for idx in range(header_row + 1, len(df)):
            row = df.iloc[idx]

            # Check for category (Income, Expenses, etc.)
            col0 = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ""
            col1 = str(row.iloc[1]) if len(row) > 1 and pd.notna(row.iloc[1]) else ""
            col2 = str(row.iloc[2]) if len(row) > 2 and pd.notna(row.iloc[2]) else ""

            if col1 in ['Income', 'Expenses', 'Net Operating Income', 'Other Income', 'Other Expenses', 'Net Other Income', 'Net Income']:
                current_category = col1
                continue

            # Get account name from column 2
            account_name = col2.strip() if col2 and col2 != 'nan' else None
            if not account_name or account_name in ['nan', 'NaN', '']:
                continue

            # Skip total rows
            if 'Total' in account_name:
                continue

            # Get values for each property
            for prop, col_idx in property_cols.items():
                value = row.iloc[col_idx] if col_idx < len(row) else None
                if pd.notna(value) and value != '' and value != 'nan':
                    try:
                        amount = float(value)
                        all_pnl_data.append({
                            "month": month,
                            "year": year,
                            "property": prop,
                            "category": current_category or "Unknown",
                            "account_name": account_name,
                            "amount": amount,
                            "period": f"{year}-{month:02d}"
                        })
                    except (ValueError, TypeError):
                        pass

    # Clear and insert
    try:
        supabase.table("pnl_data").delete().neq("id", 0).execute()
    except:
        pass

    if all_pnl_data:
        # Insert in batches
        batch_size = 500
        for i in range(0, len(all_pnl_data), batch_size):
            batch = all_pnl_data[i:i+batch_size]
            supabase.table("pnl_data").insert(batch).execute()
        print(f"✅ Imported {len(all_pnl_data)} P&L records")
    else:
        print("⚠️ No P&L data found")

    return all_pnl_data


def import_str_data(xlsx):
    """Import Short Term Rental data from all STR sheets"""
    print("\n" + "="*60)
    print("IMPORTING STR DATA")
    print("="*60)

    str_sheets = [s for s in xlsx.sheet_names if 'STR' in s]
    all_str_data = []

    for sheet_name in str_sheets:
        month, year = parse_month_year(sheet_name)
        if not month or not year:
            print(f"⚠️ Skipping {sheet_name} - couldn't parse date")
            continue

        print(f"Processing {sheet_name} ({month}/{year})...")
        df = pd.read_excel(xlsx, sheet_name=sheet_name)

        # Find the header row with Property, Unit, Revenue columns
        header_row = None
        for idx, row in df.iterrows():
            row_str = ' '.join([str(v) for v in row.values])
            if 'Property' in row_str and 'Unit' in row_str and 'Revenue' in row_str:
                header_row = idx
                break

        if header_row is None:
            print(f"⚠️ Couldn't find header row in {sheet_name}")
            continue

        # Parse data rows (start after header)
        for idx in range(header_row + 1, len(df)):
            row = df.iloc[idx]

            # Get values
            property_name = str(row.iloc[0]).strip() if pd.notna(row.iloc[0]) else None
            unit = str(row.iloc[1]).strip() if len(row) > 1 and pd.notna(row.iloc[1]) else None

            # Skip if not a valid property
            if not property_name or property_name == 'nan' or property_name not in PROPERTIES:
                continue
            if not unit or unit == 'nan':
                continue

            try:
                revenue = float(row.iloc[2]) if len(row) > 2 and pd.notna(row.iloc[2]) else 0
                commission = float(row.iloc[3]) if len(row) > 3 and pd.notna(row.iloc[3]) else 0
                avg_nightly_rate = float(row.iloc[4]) if len(row) > 4 and pd.notna(row.iloc[4]) else 0
                occupancy_pct = float(row.iloc[5]) if len(row) > 5 and pd.notna(row.iloc[5]) else 0
                revpal = float(row.iloc[6]) if len(row) > 6 and pd.notna(row.iloc[6]) else 0

                all_str_data.append({
                    "month": month,
                    "year": year,
                    "property": property_name,
                    "unit": unit,
                    "revenue": revenue,
                    "commission": commission,
                    "avg_nightly_rate": avg_nightly_rate,
                    "occupancy_pct": occupancy_pct,
                    "revpal": revpal,
                    "period": f"{year}-{month:02d}"
                })
            except (ValueError, TypeError) as e:
                pass

    # Clear and insert
    try:
        supabase.table("str_data").delete().neq("id", 0).execute()
    except:
        pass

    if all_str_data:
        batch_size = 500
        for i in range(0, len(all_str_data), batch_size):
            batch = all_str_data[i:i+batch_size]
            supabase.table("str_data").insert(batch).execute()
        print(f"✅ Imported {len(all_str_data)} STR records")
    else:
        print("⚠️ No STR data found")

    return all_str_data


def import_rentroll_data(xlsx):
    """Import Rent Roll data from all Rentroll sheets"""
    print("\n" + "="*60)
    print("IMPORTING RENTROLL DATA")
    print("="*60)

    rentroll_sheets = [s for s in xlsx.sheet_names if s.startswith('Rentroll')]
    all_rentroll_data = []

    for sheet_name in rentroll_sheets:
        month, year = parse_month_year(sheet_name)
        if not month or not year:
            print(f"⚠️ Skipping {sheet_name} - couldn't parse date")
            continue

        print(f"Processing {sheet_name} ({month}/{year})...")
        df = pd.read_excel(xlsx, sheet_name=sheet_name)

        current_property = None

        for idx, row in df.iterrows():
            col0 = str(row.iloc[0]) if pd.notna(row.iloc[0]) else ""

            # Check for property header
            if 'property:' in col0.lower():
                for prop in PROPERTIES:
                    if prop.lower() in col0.lower():
                        current_property = prop
                        break
                continue

            # Skip header row
            if 'Unit' in col0 or 'Lease' in str(row.iloc[2] if len(row) > 2 else ""):
                continue

            # Get unit from column 1
            unit = str(row.iloc[1]).strip() if len(row) > 1 and pd.notna(row.iloc[1]) else None
            if not unit or unit == 'nan' or not unit.startswith('Unit'):
                # Check for summary row
                if unit and 'Units' in unit:
                    continue
                continue

            if not current_property:
                continue

            try:
                tenant = str(row.iloc[2]).strip() if len(row) > 2 and pd.notna(row.iloc[2]) else None
                is_vacant = tenant and tenant.upper() == 'VACANT'

                # Parse dates
                start_date = None
                end_date = None
                if len(row) > 3 and pd.notna(row.iloc[3]):
                    try:
                        start_date = pd.to_datetime(row.iloc[3]).strftime('%Y-%m-%d')
                    except:
                        pass
                if len(row) > 4 and pd.notna(row.iloc[4]):
                    try:
                        end_date = pd.to_datetime(row.iloc[4]).strftime('%Y-%m-%d')
                    except:
                        pass

                # Get other fields
                size_sqft = float(row.iloc[6]) if len(row) > 6 and pd.notna(row.iloc[6]) else None
                rent = float(row.iloc[7]) if len(row) > 7 and pd.notna(row.iloc[7]) else None
                deposits = float(row.iloc[8]) if len(row) > 8 and pd.notna(row.iloc[8]) else None
                listing_price = float(row.iloc[9]) if len(row) > 9 and pd.notna(row.iloc[9]) else None
                balance = float(row.iloc[10]) if len(row) > 10 and pd.notna(row.iloc[10]) else None

                all_rentroll_data.append({
                    "month": month,
                    "year": year,
                    "property": current_property,
                    "unit": unit.replace('Unit ', ''),
                    "tenant": tenant if not is_vacant else None,
                    "is_vacant": is_vacant,
                    "lease_start": start_date,
                    "lease_end": end_date,
                    "size_sqft": size_sqft,
                    "rent": rent,
                    "deposits": deposits,
                    "listing_price": listing_price,
                    "balance": balance,
                    "period": f"{year}-{month:02d}"
                })
            except (ValueError, TypeError) as e:
                pass

    # Clear and insert
    try:
        supabase.table("rentroll_data").delete().neq("id", 0).execute()
    except:
        pass

    if all_rentroll_data:
        batch_size = 500
        for i in range(0, len(all_rentroll_data), batch_size):
            batch = all_rentroll_data[i:i+batch_size]
            supabase.table("rentroll_data").insert(batch).execute()
        print(f"✅ Imported {len(all_rentroll_data)} Rentroll records")
    else:
        print("⚠️ No Rentroll data found")

    return all_rentroll_data


def import_rent_paid_data(xlsx):
    """Import Rent Paid data from all Rent Paid sheets"""
    print("\n" + "="*60)
    print("IMPORTING RENT PAID DATA")
    print("="*60)

    rent_paid_sheets = [s for s in xlsx.sheet_names if 'Rent Paid' in s]
    all_rent_paid_data = []

    for sheet_name in rent_paid_sheets:
        month, year = parse_month_year(sheet_name)
        if not month or not year:
            print(f"⚠️ Skipping {sheet_name} - couldn't parse date")
            continue

        print(f"Processing {sheet_name} ({month}/{year})...")
        df = pd.read_excel(xlsx, sheet_name=sheet_name)

        current_property = None

        for idx, row in df.iterrows():
            col1 = str(row.iloc[1]) if len(row) > 1 and pd.notna(row.iloc[1]) else ""

            # Check for property header
            for prop in PROPERTIES:
                if prop.lower() in col1.lower() and 'apartment' in col1.lower():
                    current_property = prop
                    break

            # Skip header row
            if 'Unit' in str(row.iloc[0]) or 'Lease Name' in str(row.iloc[3] if len(row) > 3 else ""):
                continue

            # Get unit from column 2
            unit = str(row.iloc[2]).strip() if len(row) > 2 and pd.notna(row.iloc[2]) else None
            if not unit or unit == 'nan' or not unit.startswith('Unit'):
                continue

            if not current_property:
                continue

            try:
                tenant = str(row.iloc[3]).strip() if len(row) > 3 and pd.notna(row.iloc[3]) else None

                # Parse dates
                lease_start = None
                lease_end = None
                if len(row) > 4 and pd.notna(row.iloc[4]):
                    try:
                        lease_start = pd.to_datetime(row.iloc[4]).strftime('%Y-%m-%d')
                    except:
                        pass
                if len(row) > 5 and pd.notna(row.iloc[5]):
                    try:
                        lease_end = pd.to_datetime(row.iloc[5]).strftime('%Y-%m-%d')
                    except:
                        pass

                # Get financial fields
                rent_charges = float(row.iloc[6]) if len(row) > 6 and pd.notna(row.iloc[6]) else None
                other_charges = float(row.iloc[7]) if len(row) > 7 and pd.notna(row.iloc[7]) else None
                total_charges = float(row.iloc[8]) if len(row) > 8 and pd.notna(row.iloc[8]) else None
                rent_paid = float(row.iloc[9]) if len(row) > 9 and pd.notna(row.iloc[9]) else None
                other_paid = float(row.iloc[10]) if len(row) > 10 and pd.notna(row.iloc[10]) else None
                total_paid = float(row.iloc[11]) if len(row) > 11 and pd.notna(row.iloc[11]) else None
                prev_balance = float(row.iloc[12]) if len(row) > 12 and pd.notna(row.iloc[12]) else None
                balance_due = float(row.iloc[13]) if len(row) > 13 and pd.notna(row.iloc[13]) else None

                all_rent_paid_data.append({
                    "month": month,
                    "year": year,
                    "property": current_property,
                    "unit": unit.replace('Unit ', ''),
                    "tenant": tenant,
                    "lease_start": lease_start,
                    "lease_end": lease_end,
                    "rent_charges": rent_charges,
                    "other_charges": other_charges,
                    "total_charges": total_charges,
                    "rent_paid": rent_paid,
                    "other_paid": other_paid,
                    "total_paid": total_paid,
                    "prev_balance": prev_balance,
                    "balance_due": balance_due,
                    "period": f"{year}-{month:02d}"
                })
            except (ValueError, TypeError) as e:
                pass

    # Clear and insert
    try:
        supabase.table("rent_paid_data").delete().neq("id", 0).execute()
    except:
        pass

    if all_rent_paid_data:
        batch_size = 500
        for i in range(0, len(all_rent_paid_data), batch_size):
            batch = all_rent_paid_data[i:i+batch_size]
            supabase.table("rent_paid_data").insert(batch).execute()
        print(f"✅ Imported {len(all_rent_paid_data)} Rent Paid records")
    else:
        print("⚠️ No Rent Paid data found")

    return all_rent_paid_data


def main():
    print("="*60)
    print("PROPOLIS DATA IMPORT")
    print(f"Excel file: {EXCEL_FILE}")
    print(f"Supabase URL: {SUPABASE_URL}")
    print("="*60)

    # Load Excel file
    xlsx = pd.ExcelFile(EXCEL_FILE)
    print(f"\nLoaded {len(xlsx.sheet_names)} sheets")

    # Import all data
    import_properties()
    pnl_data = import_pnl_data(xlsx)
    str_data = import_str_data(xlsx)
    rentroll_data = import_rentroll_data(xlsx)
    rent_paid_data = import_rent_paid_data(xlsx)

    print("\n" + "="*60)
    print("IMPORT SUMMARY")
    print("="*60)
    print(f"Properties: {len(PROPERTIES)}")
    print(f"P&L records: {len(pnl_data)}")
    print(f"STR records: {len(str_data)}")
    print(f"Rentroll records: {len(rentroll_data)}")
    print(f"Rent Paid records: {len(rent_paid_data)}")
    print(f"\nTotal records: {len(pnl_data) + len(str_data) + len(rentroll_data) + len(rent_paid_data)}")
    print("="*60)


if __name__ == "__main__":
    main()

"""
Create Supabase tables for Propolis data import
"""

import os
from dotenv import load_dotenv
from supabase import create_client, Client

load_dotenv()

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set in .env")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# SQL to create tables
CREATE_TABLES_SQL = """
-- Properties table
CREATE TABLE IF NOT EXISTS properties (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL UNIQUE,
    full_name TEXT,
    active BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- P&L Data table
CREATE TABLE IF NOT EXISTS pnl_data (
    id SERIAL PRIMARY KEY,
    month INTEGER NOT NULL,
    year INTEGER NOT NULL,
    property TEXT NOT NULL,
    category TEXT,
    account_name TEXT NOT NULL,
    amount DECIMAL(15,2),
    period TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- STR Revenue table
CREATE TABLE IF NOT EXISTS str_revenue (
    id SERIAL PRIMARY KEY,
    month INTEGER NOT NULL,
    year INTEGER NOT NULL,
    property TEXT NOT NULL,
    unit TEXT NOT NULL,
    revenue DECIMAL(15,2),
    commission DECIMAL(15,2),
    avg_nightly_rate DECIMAL(10,2),
    occupancy_pct DECIMAL(5,2),
    revpal DECIMAL(10,2),
    period TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Rentroll table
CREATE TABLE IF NOT EXISTS rentroll (
    id SERIAL PRIMARY KEY,
    month INTEGER NOT NULL,
    year INTEGER NOT NULL,
    property TEXT NOT NULL,
    unit TEXT NOT NULL,
    tenant TEXT,
    is_vacant BOOLEAN DEFAULT false,
    lease_start DATE,
    lease_end DATE,
    size_sqft DECIMAL(10,2),
    rent DECIMAL(10,2),
    deposits DECIMAL(10,2),
    listing_price DECIMAL(10,2),
    balance DECIMAL(10,2),
    period TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Rent Paid table
CREATE TABLE IF NOT EXISTS rent_paid (
    id SERIAL PRIMARY KEY,
    month INTEGER NOT NULL,
    year INTEGER NOT NULL,
    property TEXT NOT NULL,
    unit TEXT NOT NULL,
    tenant TEXT,
    lease_start DATE,
    lease_end DATE,
    rent_charges DECIMAL(10,2),
    other_charges DECIMAL(10,2),
    total_charges DECIMAL(10,2),
    rent_paid DECIMAL(10,2),
    other_paid DECIMAL(10,2),
    total_paid DECIMAL(10,2),
    prev_balance DECIMAL(10,2),
    balance_due DECIMAL(10,2),
    period TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create indexes for better query performance
CREATE INDEX IF NOT EXISTS idx_pnl_period ON pnl_data(period);
CREATE INDEX IF NOT EXISTS idx_pnl_property ON pnl_data(property);
CREATE INDEX IF NOT EXISTS idx_str_period ON str_revenue(period);
CREATE INDEX IF NOT EXISTS idx_str_property ON str_revenue(property);
CREATE INDEX IF NOT EXISTS idx_rentroll_period ON rentroll(period);
CREATE INDEX IF NOT EXISTS idx_rentroll_property ON rentroll(property);
CREATE INDEX IF NOT EXISTS idx_rent_paid_period ON rent_paid(period);
CREATE INDEX IF NOT EXISTS idx_rent_paid_property ON rent_paid(property);
"""

def main():
    print("Creating tables in Supabase...")
    print(f"URL: {SUPABASE_URL}")

    # Execute SQL via Supabase RPC or direct query
    # Note: Supabase client doesn't support direct SQL, so we'll test table creation
    # by inserting a test record

    # Test connection
    try:
        # Try to create a simple test
        result = supabase.table("properties").select("*").limit(1).execute()
        print("✅ Connection successful, tables may already exist")
    except Exception as e:
        print(f"Note: {e}")
        print("\n⚠️ Tables need to be created manually in Supabase Dashboard")
        print("\nGo to: https://supabase.com/dashboard/project/rlzcwkiffgokufbrgtgy/sql/new")
        print("\nCopy and paste the following SQL:\n")
        print(CREATE_TABLES_SQL)

    print("\n" + "="*60)
    print("MANUAL STEPS REQUIRED:")
    print("="*60)
    print("""
1. Go to Supabase Dashboard:
   https://supabase.com/dashboard/project/rlzcwkiffgokufbrgtgy/sql/new

2. Copy and paste this SQL to create tables:
""")
    print(CREATE_TABLES_SQL)

if __name__ == "__main__":
    main()

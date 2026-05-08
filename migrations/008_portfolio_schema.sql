-- Run this in the Supabase SQL editor.
--
-- Strictly additive. No existing table or column is modified.
-- 
-- Adds the new normalized "portfolio" schema that backs the unified
-- /portfolio page: a stable amenity catalog, structural tables for
-- buildings/units/rooms (mirroring inv_*), money fields split into their
-- own table, and the monthly performance time series.
--
-- The legacy inv_*, facility_*, properties tables are left intact.

-- ── 1. Amenity catalog ───────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.prop_amenities (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name        text UNIQUE NOT NULL,
  category    text,                          -- free-form: "appliance", "comfort", "building", …
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_prop_amenities_category ON public.prop_amenities(category);

-- ── 2. Buildings ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.prop_buildings (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name          text UNIQUE NOT NULL,
  full_name     text,
  address       text,
  owner_llc     text,
  floors        integer,
  has_elevator  boolean,
  units_count   integer,
  beds_count    integer,
  description   text,
  photos        text[] NOT NULL DEFAULT '{}',
  amenity_ids   uuid[] NOT NULL DEFAULT '{}',
  notes         text,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);

-- ── 3. Units ─────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.prop_units (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  building_id  uuid NOT NULL REFERENCES public.prop_buildings(id) ON DELETE CASCADE,
  name         text NOT NULL,
  unit_type    text,
  notes        text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (building_id, name)
);
CREATE INDEX IF NOT EXISTS idx_prop_units_building ON public.prop_units(building_id);

-- ── 4. Rooms (structural only) ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.prop_rooms (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  unit_id         uuid NOT NULL REFERENCES public.prop_units(id) ON DELETE CASCADE,
  name            text NOT NULL,
  length          text CHECK (length IN ('LTR','STR')),
  strategy        text CHECK (strategy IN ('Coliving','Entire Apt')),
  bed_size        text,
  bathroom        text,
  ceiling_height  text,
  balcony         text,
  room_type_name  text,
  is_ada          boolean,
  listing_date    date,
  amenity_ids     uuid[] NOT NULL DEFAULT '{}',
  notes           text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (unit_id, name)
);
CREATE INDEX IF NOT EXISTS idx_prop_rooms_unit ON public.prop_rooms(unit_id);

-- ── 5. Financials (1:1 with rooms) ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS public.prop_financials (
  id                          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  room_id                     uuid UNIQUE NOT NULL REFERENCES public.prop_rooms(id) ON DELETE CASCADE,
  actual_rent                 numeric(10,2),
  base_rent                   numeric(10,2),
  market_rent                 numeric(10,2),
  actual_rent_with_util       numeric(10,2),
  pessimistic_rent            numeric(10,2),
  concession_rent             numeric(10,2),
  concession_rent_with_util   numeric(10,2),
  adjustment                  numeric(10,2),
  stake_5_cashback            numeric(10,2),
  stake_8_cashback            numeric(10,2),
  revenue_month               numeric(10,2),
  revenue_year                numeric(12,2),
  revenue_per_apartment       numeric(12,2),
  extras                      text,
  created_at                  timestamptz NOT NULL DEFAULT now(),
  updated_at                  timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_prop_financials_room ON public.prop_financials(room_id);

-- ── 6. Monthly performance time series ───────────────────────────────────
CREATE TABLE IF NOT EXISTS public.prop_monthly_performance (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  building_id     uuid NOT NULL REFERENCES public.prop_buildings(id) ON DELETE CASCADE,
  period_year     integer NOT NULL,
  period_month    integer NOT NULL CHECK (period_month BETWEEN 1 AND 12),
  occupancy_pct   numeric(5,2),
  adr             numeric(10,2),
  revpar          numeric(10,2),
  revenue         numeric(12,2),
  notes           text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (building_id, period_year, period_month)
);
CREATE INDEX IF NOT EXISTS idx_prop_perf_building ON public.prop_monthly_performance(building_id);
CREATE INDEX IF NOT EXISTS idx_prop_perf_period   ON public.prop_monthly_performance(period_year, period_month);

-- ── updated_at trigger ───────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.set_portfolio_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['prop_buildings','prop_units','prop_rooms','prop_financials','prop_monthly_performance']
  LOOP
    EXECUTE format('DROP TRIGGER IF EXISTS trg_%s_updated_at ON public.%s', t, t);
    EXECUTE format('CREATE TRIGGER trg_%s_updated_at BEFORE UPDATE ON public.%s FOR EACH ROW EXECUTE FUNCTION public.set_portfolio_updated_at()', t, t);
  END LOOP;
END $$;

-- ── RLS off + permissive policies (same pattern as user_profiles / inv_*)
DO $$
DECLARE t text;
BEGIN
  FOREACH t IN ARRAY ARRAY['prop_amenities','prop_buildings','prop_units','prop_rooms','prop_financials','prop_monthly_performance']
  LOOP
    EXECUTE format('ALTER TABLE public.%s DISABLE ROW LEVEL SECURITY', t);
    EXECUTE format('DROP POLICY IF EXISTS "allow all" ON public.%s', t);
    EXECUTE format('CREATE POLICY "allow all" ON public.%s FOR ALL USING (true) WITH CHECK (true)', t);
  END LOOP;
END $$;

NOTIFY pgrst, 'reload schema';

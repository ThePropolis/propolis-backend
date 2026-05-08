-- Run this in the Supabase SQL editor.
--
-- Adds the financial fields that come straight from the XLSX (rent, revenue,
-- ADA flag, extras) onto inv_rooms, plus a per-building monthly performance
-- time-series table for the data at the bottom of the Olive sheet.

ALTER TABLE public.inv_rooms
  ADD COLUMN IF NOT EXISTS base_rent      numeric(10,2),
  ADD COLUMN IF NOT EXISTS market_rent    numeric(10,2),
  ADD COLUMN IF NOT EXISTS actual_rent    numeric(10,2),
  ADD COLUMN IF NOT EXISTS revenue_year   numeric(12,2),
  ADD COLUMN IF NOT EXISTS revenue_month  numeric(10,2),
  ADD COLUMN IF NOT EXISTS is_ada         boolean,
  ADD COLUMN IF NOT EXISTS extras         text;

CREATE TABLE IF NOT EXISTS public.inv_monthly_performance (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  building_id     uuid NOT NULL REFERENCES public.inv_buildings(id) ON DELETE CASCADE,
  period_year     integer NOT NULL,
  period_month    integer NOT NULL CHECK (period_month BETWEEN 1 AND 12),
  occupancy_pct   numeric(5,2),    -- 0..100
  adr             numeric(10,2),   -- average daily rate
  revpar          numeric(10,2),   -- revenue per available room
  revenue         numeric(12,2),   -- total revenue for that month
  notes           text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (building_id, period_year, period_month)
);

CREATE INDEX IF NOT EXISTS idx_inv_monthly_perf_building
  ON public.inv_monthly_performance(building_id);
CREATE INDEX IF NOT EXISTS idx_inv_monthly_perf_period
  ON public.inv_monthly_performance(period_year, period_month);

DROP TRIGGER IF EXISTS trg_inv_monthly_perf_updated_at ON public.inv_monthly_performance;
CREATE TRIGGER trg_inv_monthly_perf_updated_at
BEFORE UPDATE ON public.inv_monthly_performance
FOR EACH ROW EXECUTE FUNCTION public.set_inventory_updated_at();

ALTER TABLE public.inv_monthly_performance DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "allow all" ON public.inv_monthly_performance;
CREATE POLICY "allow all" ON public.inv_monthly_performance FOR ALL USING (true) WITH CHECK (true);

NOTIFY pgrst, 'reload schema';

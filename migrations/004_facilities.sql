-- Run this in the Supabase SQL editor.
--
-- Adds Supabase-owned tables for the Facilities page. DoorLoop is only used
-- for the one-time import — after that, all reads and writes go through
-- these tables via the admin panel.

CREATE TABLE IF NOT EXISTS public.facility_buildings (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  doorloop_id  text UNIQUE,                 -- NULL for locally-created buildings
  name         text NOT NULL,
  address      text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.facility_units (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  doorloop_id  text UNIQUE,
  building_id  uuid NOT NULL REFERENCES public.facility_buildings(id) ON DELETE CASCADE,
  name         text NOT NULL,
  beds         integer,
  baths        numeric(3,1),
  amenities    text[] NOT NULL DEFAULT '{}',
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_facility_units_building  ON public.facility_units(building_id);
CREATE INDEX IF NOT EXISTS idx_facility_units_doorloop  ON public.facility_units(doorloop_id);

-- Auto-update timestamp trigger
CREATE OR REPLACE FUNCTION public.set_facility_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_facility_buildings_updated_at ON public.facility_buildings;
CREATE TRIGGER trg_facility_buildings_updated_at
BEFORE UPDATE ON public.facility_buildings
FOR EACH ROW EXECUTE FUNCTION public.set_facility_updated_at();

DROP TRIGGER IF EXISTS trg_facility_units_updated_at ON public.facility_units;
CREATE TRIGGER trg_facility_units_updated_at
BEFORE UPDATE ON public.facility_units
FOR EACH ROW EXECUTE FUNCTION public.set_facility_updated_at();

-- Backend is sole writer, auth is enforced at FastAPI layer (same pattern as user_profiles).
ALTER TABLE public.facility_buildings DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.facility_units    DISABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "allow all" ON public.facility_buildings;
CREATE POLICY "allow all" ON public.facility_buildings FOR ALL USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS "allow all" ON public.facility_units;
CREATE POLICY "allow all" ON public.facility_units FOR ALL USING (true) WITH CHECK (true);

NOTIFY pgrst, 'reload schema';

-- Run this in the Supabase SQL editor.
--
-- Canonical inventory: buildings → units → rooms. The XLSX
-- (Documentations/Properties Sheet/Propolis Properties Overview.xlsx)
-- seeds these tables once; after that the website is the source of truth.

CREATE TABLE IF NOT EXISTS public.inv_buildings (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name          text UNIQUE NOT NULL,
  full_name     text,
  address       text,
  owner_llc     text,
  units_count   integer,
  beds_count    integer,
  floors        integer,
  has_elevator  boolean,
  notes         text,
  created_at    timestamptz NOT NULL DEFAULT now(),
  updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.inv_units (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  building_id  uuid NOT NULL REFERENCES public.inv_buildings(id) ON DELETE CASCADE,
  name         text NOT NULL,
  notes        text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  updated_at   timestamptz NOT NULL DEFAULT now(),
  UNIQUE (building_id, name)
);

CREATE TABLE IF NOT EXISTS public.inv_rooms (
  id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  unit_id         uuid NOT NULL REFERENCES public.inv_units(id) ON DELETE CASCADE,
  name            text NOT NULL,
  length          text CHECK (length IN ('LTR','STR')),
  strategy        text CHECK (strategy IN ('Coliving','Entire Apt')),
  bed_size        text,
  bathroom        text,
  ceiling_height  text,
  balcony         text,
  room_type_name  text,
  amenities       text[] NOT NULL DEFAULT '{}',
  notes           text,
  created_at      timestamptz NOT NULL DEFAULT now(),
  updated_at      timestamptz NOT NULL DEFAULT now(),
  UNIQUE (unit_id, name)
);

CREATE INDEX IF NOT EXISTS idx_inv_units_building ON public.inv_units(building_id);
CREATE INDEX IF NOT EXISTS idx_inv_rooms_unit     ON public.inv_rooms(unit_id);

-- updated_at auto-bump trigger (shared function across all three tables)
CREATE OR REPLACE FUNCTION public.set_inventory_updated_at()
RETURNS trigger AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_inv_buildings_updated_at ON public.inv_buildings;
CREATE TRIGGER trg_inv_buildings_updated_at
BEFORE UPDATE ON public.inv_buildings
FOR EACH ROW EXECUTE FUNCTION public.set_inventory_updated_at();

DROP TRIGGER IF EXISTS trg_inv_units_updated_at ON public.inv_units;
CREATE TRIGGER trg_inv_units_updated_at
BEFORE UPDATE ON public.inv_units
FOR EACH ROW EXECUTE FUNCTION public.set_inventory_updated_at();

DROP TRIGGER IF EXISTS trg_inv_rooms_updated_at ON public.inv_rooms;
CREATE TRIGGER trg_inv_rooms_updated_at
BEFORE UPDATE ON public.inv_rooms
FOR EACH ROW EXECUTE FUNCTION public.set_inventory_updated_at();

-- Backend is sole writer; auth is enforced at FastAPI layer (require_role).
-- Disable RLS + permissive fallback policy (matches the user_profiles / facility_*
-- pattern used elsewhere in this project).
ALTER TABLE public.inv_buildings DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.inv_units     DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.inv_rooms     DISABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "allow all" ON public.inv_buildings;
CREATE POLICY "allow all" ON public.inv_buildings FOR ALL USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS "allow all" ON public.inv_units;
CREATE POLICY "allow all" ON public.inv_units     FOR ALL USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS "allow all" ON public.inv_rooms;
CREATE POLICY "allow all" ON public.inv_rooms     FOR ALL USING (true) WITH CHECK (true);

NOTIFY pgrst, 'reload schema';

-- Run this in the Supabase SQL editor.
--
-- Strictly additive. Adds the listings layer that the new "Publishing" page
-- will write into. Inventory tables (prop_*) are referenced read-only.

-- A listing is a public-ready offering composed of one or more rooms.
CREATE TABLE IF NOT EXISTS public.prop_listings (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  building_id         uuid REFERENCES public.prop_buildings(id) ON DELETE SET NULL,

  -- Marketing identity
  title               text NOT NULL,
  subtitle            text,
  description         text,
  slug                text UNIQUE,                                  -- url-safe id; auto-generated if NULL
  meta_description    text,                                          -- SEO

  -- Status lifecycle
  status              text NOT NULL DEFAULT 'draft'
                      CHECK (status IN ('draft','published','archived','rented')),
  published_at        timestamptz,
  archived_at         timestamptz,

  -- Visuals
  cover_photo         text,                                          -- URL
  photos              text[] NOT NULL DEFAULT '{}',                  -- URLs

  -- Pricing
  asking_rent         numeric(10,2),
  deposit             numeric(10,2),
  application_fee     numeric(10,2),

  -- Availability + terms
  available_from      date,
  available_until     date,
  min_lease_months    integer,
  max_lease_months    integer,
  is_furnished        boolean,
  utilities_included  boolean,
  utilities_note      text,                                          -- free-form list/notes
  pets_allowed        boolean,
  smoking_allowed     boolean,

  -- Curated marketing tags / highlights
  highlights          text[] NOT NULL DEFAULT '{}',
  tags                text[] NOT NULL DEFAULT '{}',

  -- Lead capture
  inquiry_email       text,
  inquiry_phone       text,

  -- Audit
  created_by          uuid REFERENCES auth.users(id) ON DELETE SET NULL,
  created_at          timestamptz NOT NULL DEFAULT now(),
  updated_at          timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_prop_listings_status   ON public.prop_listings(status);
CREATE INDEX IF NOT EXISTS idx_prop_listings_building ON public.prop_listings(building_id);

-- Many-to-many: a listing covers one or more rooms.
CREATE TABLE IF NOT EXISTS public.prop_listing_rooms (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  listing_id    uuid NOT NULL REFERENCES public.prop_listings(id) ON DELETE CASCADE,
  room_id       uuid NOT NULL REFERENCES public.prop_rooms(id)    ON DELETE CASCADE,
  display_order integer NOT NULL DEFAULT 0,
  created_at    timestamptz NOT NULL DEFAULT now(),
  UNIQUE (listing_id, room_id)
);

CREATE INDEX IF NOT EXISTS idx_prop_listing_rooms_listing ON public.prop_listing_rooms(listing_id);
CREATE INDEX IF NOT EXISTS idx_prop_listing_rooms_room    ON public.prop_listing_rooms(room_id);

-- updated_at trigger (reuse the helper from migration 008)
DROP TRIGGER IF EXISTS trg_prop_listings_updated_at ON public.prop_listings;
CREATE TRIGGER trg_prop_listings_updated_at
BEFORE UPDATE ON public.prop_listings
FOR EACH ROW EXECUTE FUNCTION public.set_portfolio_updated_at();

-- RLS off + permissive (same pattern as the rest of the new schema)
ALTER TABLE public.prop_listings      DISABLE ROW LEVEL SECURITY;
ALTER TABLE public.prop_listing_rooms DISABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "allow all" ON public.prop_listings;
CREATE POLICY "allow all" ON public.prop_listings      FOR ALL USING (true) WITH CHECK (true);
DROP POLICY IF EXISTS "allow all" ON public.prop_listing_rooms;
CREATE POLICY "allow all" ON public.prop_listing_rooms FOR ALL USING (true) WITH CHECK (true);

NOTIFY pgrst, 'reload schema';

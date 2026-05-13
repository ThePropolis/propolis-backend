-- Run in Supabase SQL editor.
-- Adds amenity_ids array to prop_units so apartments can have their own amenity tags.

ALTER TABLE public.prop_units
  ADD COLUMN IF NOT EXISTS amenity_ids uuid[] NOT NULL DEFAULT '{}';

NOTIFY pgrst, 'reload schema';

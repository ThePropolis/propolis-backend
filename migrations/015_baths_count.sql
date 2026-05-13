-- Run in Supabase SQL editor.
-- Adds baths (number of bathrooms) to prop_rooms.

ALTER TABLE public.prop_rooms
  ADD COLUMN IF NOT EXISTS baths integer;

NOTIFY pgrst, 'reload schema';

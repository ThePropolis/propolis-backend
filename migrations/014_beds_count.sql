-- Run in Supabase SQL editor.
-- Adds beds (number of beds) to prop_rooms.

ALTER TABLE public.prop_rooms
  ADD COLUMN IF NOT EXISTS beds integer;

NOTIFY pgrst, 'reload schema';

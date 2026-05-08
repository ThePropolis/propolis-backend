-- Run in Supabase SQL editor.
-- Adds square footage to prop_rooms (nullable — filled via the editor UI).

ALTER TABLE public.prop_rooms
  ADD COLUMN IF NOT EXISTS sqft integer;

NOTIFY pgrst, 'reload schema';

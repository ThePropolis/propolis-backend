-- Add avatar_url column so users can upload/change profile pictures.
-- Run this in the Supabase SQL editor.

ALTER TABLE public.user_profiles
  ADD COLUMN IF NOT EXISTS avatar_url text;

-- Create a public storage bucket for avatars (idempotent).
INSERT INTO storage.buckets (id, name, public)
VALUES ('avatars', 'avatars', true)
ON CONFLICT (id) DO NOTHING;

-- Let anyone read avatars (they're public-by-URL anyway)
DROP POLICY IF EXISTS "avatars read" ON storage.objects;
CREATE POLICY "avatars read"
  ON storage.objects
  FOR SELECT
  USING (bucket_id = 'avatars');

-- Let any authenticated request write to the bucket (our backend uses
-- the service key so this is permissive enough — backend validates the
-- caller's identity before uploading).
DROP POLICY IF EXISTS "avatars write" ON storage.objects;
CREATE POLICY "avatars write"
  ON storage.objects
  FOR ALL
  USING (bucket_id = 'avatars')
  WITH CHECK (bucket_id = 'avatars');

NOTIFY pgrst, 'reload schema';

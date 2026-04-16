-- Run this in the Supabase SQL editor (paste the whole file, click "Run").
--
-- Problem: the new sb_secret_ API keys don't auto-bypass RLS the way the old
-- service_role JWT did on some projects, so writes against user_profiles 404.
-- Fix (belt-and-braces): disable RLS AND add a permissive policy in case RLS
-- gets re-enabled somehow. Backend auth is enforced at the FastAPI layer.

ALTER TABLE public.user_profiles DISABLE ROW LEVEL SECURITY;

-- Defence-in-depth: if something re-enables RLS later, these policies keep
-- the backend working.
DROP POLICY IF EXISTS "allow all" ON public.user_profiles;
CREATE POLICY "allow all"
  ON public.user_profiles
  FOR ALL
  USING (true)
  WITH CHECK (true);

-- Make sure PostgREST picks this up immediately
NOTIFY pgrst, 'reload schema';

-- Verify: this SELECT should return relrowsecurity = false
SELECT relname, relrowsecurity, relforcerowsecurity
FROM pg_class
WHERE relname = 'user_profiles';

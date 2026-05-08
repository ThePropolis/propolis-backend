-- Run this in the Supabase SQL editor.
--
-- Captures the remaining XLSX columns that vary across building sheets so the
-- spreadsheet can be retired entirely. All optional — old data is unaffected.

ALTER TABLE public.inv_rooms
  ADD COLUMN IF NOT EXISTS listing_date              date,
  ADD COLUMN IF NOT EXISTS unit_type                 text,
  ADD COLUMN IF NOT EXISTS adjustment                numeric(10,2),
  ADD COLUMN IF NOT EXISTS actual_rent_with_util     numeric(10,2),
  ADD COLUMN IF NOT EXISTS pessimistic_rent          numeric(10,2),
  ADD COLUMN IF NOT EXISTS concession_rent           numeric(10,2),
  ADD COLUMN IF NOT EXISTS concession_rent_with_util numeric(10,2),
  ADD COLUMN IF NOT EXISTS stake_5_cashback          numeric(10,2),
  ADD COLUMN IF NOT EXISTS stake_8_cashback          numeric(10,2),
  ADD COLUMN IF NOT EXISTS revenue_per_apartment     numeric(12,2);

NOTIFY pgrst, 'reload schema';

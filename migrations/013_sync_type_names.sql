-- Run in Supabase SQL editor.
-- Backfills room_type_name in prop_rooms from inv_rooms, and unit_type in prop_units from inv_units.
-- Matches rows by building name → unit name → room name chain.
-- Safe to re-run: only updates NULL values.

-- 1. Sync room_type_name
-- Uses comma-separated FROM (not JOIN) so the target table alias can be referenced in WHERE.
UPDATE public.prop_rooms pr
SET room_type_name = ir.room_type_name
FROM public.inv_rooms ir,
     public.prop_units pu,
     public.inv_units iu,
     public.prop_buildings pb,
     public.inv_buildings ib
WHERE pu.id = pr.unit_id
  AND pb.id = pu.building_id
  AND ib.name = pb.name
  AND iu.building_id = ib.id
  AND iu.name = pu.name
  AND ir.unit_id = iu.id
  AND pr.name = ir.name
  AND ir.room_type_name IS NOT NULL
  AND pr.room_type_name IS NULL;

-- Note: unit_type has no source in inv_units (that table only stores name/notes).
-- unit_type must be entered manually via the portfolio edit form.

NOTIFY pgrst, 'reload schema';

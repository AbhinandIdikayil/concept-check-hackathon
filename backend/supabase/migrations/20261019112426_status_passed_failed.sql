-- Concept Check: statuses are decided by code.
--
-- `message_status` now holds 'passed' / 'failed' instead of 'success' / 'recite'.
-- Pass/fail is decided by comparing an answer to the case's reference answer in
-- app/services/chat_service.py. The model never returns a verdict.
--
-- Idempotent, so it is safe to run against a project that already ran it.
--
--   psql "$SUPABASE_DB_URL" -f supabase/migrations/20261019112426_status_passed_failed.sql

-- Postgres has no "rename value if exists", so each rename is guarded: a fresh
-- database that created the new labels directly is left alone, and a re-run
-- finds nothing to rename instead of erroring on a missing label.
do $$
begin
  if exists (
    select 1
    from pg_enum e
    join pg_type t on t.oid = e.enumtypid
    join pg_namespace n on n.oid = t.typnamespace
    where t.typname = 'message_status' and n.nspname = 'public' and e.enumlabel = 'success'
  ) then
    alter type public.message_status rename value 'success' to 'passed';
  end if;

  if exists (
    select 1
    from pg_enum e
    join pg_type t on t.oid = e.enumtypid
    join pg_namespace n on n.oid = t.typnamespace
    where t.typname = 'message_status' and n.nspname = 'public' and e.enumlabel = 'recite'
  ) then
    alter type public.message_status rename value 'recite' to 'failed';
  end if;
end;
$$;

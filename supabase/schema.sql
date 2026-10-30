-- The web app's database in Supabase (R11.6a): one saved game per account.
-- Run once in the Supabase dashboard's SQL Editor; see docs/supabase-setup.md.
-- Running it again is safe.
--
-- Row-level security makes the database itself refuse anyone else's save
-- (R11.9): the page holds only the public key, which can't get around it.

create table if not exists public.saves (
  user_id uuid primary key references auth.users (id) on delete cascade,
  save jsonb not null,  -- the save of R11.8, as the page made it
  saved_at timestamptz not null default now()
);

alter table public.saves enable row level security;

drop policy if exists "read own save" on public.saves;
create policy "read own save" on public.saves
  for select to authenticated using (user_id = (select auth.uid()));

drop policy if exists "add own save" on public.saves;
create policy "add own save" on public.saves
  for insert to authenticated with check (user_id = (select auth.uid()));

drop policy if exists "change own save" on public.saves;
create policy "change own save" on public.saves
  for update to authenticated
  using (user_id = (select auth.uid())) with check (user_id = (select auth.uid()));

drop policy if exists "delete own save" on public.saves;
create policy "delete own save" on public.saves
  for delete to authenticated using (user_id = (select auth.uid()));

-- Deleting an account (R11.11). The page can't delete sign-in accounts
-- itself, so this function does it for the signed-in player only; their
-- save goes with it (on delete cascade).
create or replace function public.delete_account() returns void
language sql security definer set search_path = ''
as $$
  delete from auth.users where id = (select auth.uid());
$$;

revoke all on function public.delete_account() from public, anon;
grant execute on function public.delete_account() to authenticated;

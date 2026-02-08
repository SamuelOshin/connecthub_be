-- Message read cursors table for cursor-based read receipts
-- Apply in Supabase SQL editor (or migration tool)

create table if not exists public.message_read_cursors (
    id uuid primary key default gen_random_uuid(),
    match_id uuid not null references public.matches(id) on delete cascade,
    user_id uuid not null references public.profiles(id) on delete cascade,
    last_read_message_id uuid references public.messages(id) on delete set null,
    last_read_at timestamptz,
    updated_at timestamptz not null default now(),
    unique (match_id, user_id)
);

create index if not exists idx_message_read_cursors_match_id on public.message_read_cursors(match_id);
create index if not exists idx_message_read_cursors_user_id on public.message_read_cursors(user_id);

-- RLS (adjust to your auth model)
alter table public.message_read_cursors enable row level security;

-- Allow users to view cursors for matches they are part of
create policy if not exists "read_cursors_select" on public.message_read_cursors
for select
using (
    exists (
        select 1 from public.matches
        where matches.id = message_read_cursors.match_id
          and (matches.user1_id = auth.uid()::text or matches.user2_id = auth.uid()::text)
    )
);

-- Allow users to upsert their own cursor in a match they belong to
create policy if not exists "read_cursors_upsert" on public.message_read_cursors
for insert
with check (
    user_id = auth.uid()::text
    and exists (
        select 1 from public.matches
        where matches.id = message_read_cursors.match_id
          and (matches.user1_id = auth.uid()::text or matches.user2_id = auth.uid()::text)
    )
);

create policy if not exists "read_cursors_update" on public.message_read_cursors
for update
using (
    user_id = auth.uid()::text
)
with check (
    user_id = auth.uid()::text
);

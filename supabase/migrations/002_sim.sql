-- Create channel_msgs table for DAK simulator
create table channel_msgs (
  id uuid primary key default gen_random_uuid(),
  msg_id uuid not null references outbox_msgs(id),
  bubble jsonb not null,
  ticks int not null default 1,
  ts timestamptz not null default now()
);

-- RLS for channel_msgs
alter table channel_msgs enable row level security;
create policy staff_select_channel_msgs on channel_msgs for select to authenticated
  using (exists (select 1 from profiles p where p.id = auth.uid()));
create policy service_insert_channel_msgs on channel_msgs for insert to service_role with check (true);

-- Add to realtime publication
alter publication supabase_realtime add table channel_msgs;

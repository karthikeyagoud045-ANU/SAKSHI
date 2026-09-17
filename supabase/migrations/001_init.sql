-- Supabase migration 001_init.sql
-- SAKSHI Backend Core Schema

-- Profiles table for operators and supervisors
create table profiles (
  id uuid primary key references auth.users,
  role text check (role in ('operator','supervisor'))
);

-- Tickets table for complaints
create table tickets (
  id uuid primary key default gen_random_uuid(),
  tracking_code text unique not null default upper(substr(md5(random()::text),1,6)),
  category text,
  urgency text check (urgency in ('LOW','MEDIUM','HIGH')),
  dept text,
  loc_lat float8,
  loc_lng float8,
  loc_conf float8,
  status text not null default 'intake'
    check (status in ('intake','triage','tray','merged','human_review','approved','sent')),
  dup_score float8,
  parent_id uuid references tickets(id),
  missing text[],
  conflicts jsonb,
  created_at timestamptz not null default now()
);

-- Evidence table for all types of evidence
create table evidence (
  id uuid primary key default gen_random_uuid(),
  ticket_id uuid not null references tickets(id) on delete cascade,
  kind text not null check (kind in ('photo_original','photo_blurred','audio','transcript','gps','text')),
  storage_path text,
  span tsrange,
  meta jsonb not null default '{}',
  sha256 text not null,
  created_at timestamptz not null default now()
);

-- Claim links connecting ticket fields to evidence
create table claim_links (
  id uuid primary key default gen_random_uuid(),
  ticket_id uuid not null references tickets(id),
  field text not null,
  value text not null,
  evidence_id uuid not null references evidence(id),
  conf float8 not null
);

-- Audit log for all actions (append-only)
create table audit_log (
  id bigserial primary key,
  ts timestamptz not null default now(),
  actor text not null,
  action text not null,
  detail jsonb not null default '{}'
);

-- Append-only rules for audit_log
create rule audit_no_update as on update to audit_log do instead nothing;
create rule audit_no_delete as on delete to audit_log do instead nothing;

-- Outbox messages for DAK sender
create table outbox_msgs (
  id uuid primary key default gen_random_uuid(),
  ticket_id uuid not null references tickets(id),
  payload jsonb not null,
  status text not null default 'draft'
    check (status in ('draft','approved','sent','rejected')),
  approved_by uuid references auth.users(id),
  sent_at timestamptz
);

-- Evaluation runs table
create table eval_runs (
  id uuid primary key default gen_random_uuid(),
  seed_id text not null,
  metrics jsonb not null,
  ts timestamptz not null default now()
);

-- Row Level Security (RLS) Policies
alter table tickets enable row level security;
alter table evidence enable row level security;
alter table claim_links enable row level security;
alter table audit_log enable row level security;
alter table outbox_msgs enable row level security;
alter table eval_runs enable row level security;
alter table profiles enable row level security;

-- Tickets policies
create policy cit_insert_tickets on tickets for insert to anon with check (true);
create policy cit_read_own_tickets on tickets for select to anon
  using (tracking_code = current_setting('app.tracking', true));
create policy staff_read_tickets on tickets for select to authenticated
  using (exists (select 1 from profiles p where p.id = auth.uid()));
create policy staff_write_tickets on tickets for update to authenticated
  using (exists (select 1 from profiles p where p.id = auth.uid()));

-- Evidence policies
create policy staff_read_evidence on evidence for select to authenticated
  using (exists (select 1 from profiles p where p.id = auth.uid())
     and kind <> 'photo_original');
create policy sup_read_originals on evidence for select to authenticated
  using (kind = 'photo_original' and exists
    (select 1 from profiles p where p.id = auth.uid() and p.role = 'supervisor'));
create policy service_insert_evidence on evidence for insert to service_role with check (true);

-- Claim links policies
create policy staff_read_links on claim_links for select to authenticated
  using (exists (select 1 from profiles p where p.id = auth.uid()));
create policy service_write_links on claim_links for insert to service_role with check (true);

-- Audit log policies
create policy staff_read_audit on audit_log for select to authenticated
  using (exists (select 1 from profiles p where p.id = auth.uid()));
create policy service_insert_audit on audit_log for insert to service_role with check (true);

-- Outbox messages policies
create policy staff_read_outbox on outbox_msgs for select to authenticated
  using (exists (select 1 from profiles p where p.id = auth.uid()));
create policy staff_approve_outbox on outbox_msgs for update to authenticated
  using (exists (select 1 from profiles p where p.id = auth.uid()))
  with check (status in ('approved','rejected'));

-- Eval runs policies
create policy staff_read_eval on eval_runs for select to authenticated
  using (exists (select 1 from profiles p where p.id = auth.uid()));
create policy service_write_eval on eval_runs for insert to service_role with check (true);

-- Profiles policy
create policy self_profile on profiles for select to authenticated using (id = auth.uid());

-- Storage Buckets (to be created via Supabase UI or CLI)
-- 3 PRIVATE buckets: originals, blurred, outbox.
-- originals: NO anon/authenticated insert or select policies (service_role only).
-- blurred: select for authenticated staff; insert service_role only.
-- outbox: select/update service_role only (sender edge fn + worker).
-- Signed URLs ≤ 300 seconds everywhere in worker code.

-- Realtime publication
alter publication supabase_realtime add table tickets;
alter publication supabase_realtime add table audit_log;
alter publication supabase_realtime add table outbox_msgs;
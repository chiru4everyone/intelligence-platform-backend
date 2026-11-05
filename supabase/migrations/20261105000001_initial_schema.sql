-- ═══════════════════════════════════════════════════════════════════════════
-- Intelligence Platform — Supabase Schema  v1.0
-- Migration: 20261105000001_initial_schema
--
-- Tables:
--   profiles            — analyst accounts (extends auth.users)
--   analyst_sessions    — login events & role-at-login audit
--   reports             — research report pipeline
--   workflow_events     — stage-change audit trail per report
--   data_sources        — platform data feed registry
--   model_uploads       — Excel / PPT / Word file uploads
--   factsheets          — public-facing research factsheets
--   notify_subscriptions — email capture for factsheet updates
-- ═══════════════════════════════════════════════════════════════════════════

-- ─── 1. PROFILES ─────────────────────────────────────────────────────────────
-- Extends auth.users. Created automatically on signup via trigger.
create table if not exists public.profiles (
  id          uuid references auth.users(id) on delete cascade primary key,
  email       text not null,
  full_name   text,
  role        text not null default 'analyst'
                check (role in ('analyst', 'senior', 'head')),
  vertical    text not null default 'all'
                check (vertical in ('epi', 'agri', 'trade', 'markets', 'packaging', 'startups', 'all')),
  is_active   boolean not null default true,
  created_at  timestamptz default now(),
  updated_at  timestamptz default now()
);

comment on table public.profiles is
  'One row per analyst. Role controls platform access level; vertical scopes data visibility.';

-- Auto-create profile on new user signup
create or replace function public.handle_new_user()
returns trigger
language plpgsql
security definer set search_path = public
as $$
begin
  insert into public.profiles (id, email, full_name, role, vertical)
  values (
    new.id,
    new.email,
    new.raw_user_meta_data->>'full_name',
    coalesce(new.raw_user_meta_data->>'role', 'analyst'),
    coalesce(new.raw_user_meta_data->>'vertical', 'all')
  )
  on conflict (id) do nothing;
  return new;
end;
$$;

drop trigger if exists on_auth_user_created on auth.users;
create trigger on_auth_user_created
  after insert on auth.users
  for each row execute procedure public.handle_new_user();

-- Auto-update updated_at on profiles
create or replace function public.touch_updated_at()
returns trigger
language plpgsql
as $$
begin new.updated_at = now(); return new; end;
$$;

create trigger profiles_updated_at
  before update on public.profiles
  for each row execute procedure public.touch_updated_at();

-- ─── 2. ANALYST SESSIONS ──────────────────────────────────────────────────────
-- Logs every login event: which role was selected, from which IP, etc.
create table if not exists public.analyst_sessions (
  id            uuid default gen_random_uuid() primary key,
  user_id       uuid references public.profiles(id) on delete cascade not null,
  role_at_login text not null
                  check (role_at_login in ('analyst', 'senior', 'head')),
  vertical      text,
  user_agent    text,
  ip_address    text,
  login_at      timestamptz default now(),
  logout_at     timestamptz,
  session_token text unique   -- opaque reference; set by application layer
);

comment on table public.analyst_sessions is
  'Audit log of login events. role_at_login captures the role selected on the login page.';

-- ─── 3. REPORTS ───────────────────────────────────────────────────────────────
create table if not exists public.reports (
  id               uuid default gen_random_uuid() primary key,
  title            text not null,
  abstract         text,
  vertical         text not null
                     check (vertical in ('epi', 'agri', 'trade', 'markets', 'packaging', 'startups')),
  stage            text not null default 'draft'
                     check (stage in ('draft', 'peer_review', 'editorial', 'approved', 'published')),
  priority         text default 'med'
                     check (priority in ('high', 'med', 'low')),
  author_id        uuid references public.profiles(id),
  author_name      text,
  factsheet_slug   text,
  next_update_date date,
  version          text,
  created_at       timestamptz default now(),
  updated_at       timestamptz default now()
);

create trigger reports_updated_at
  before update on public.reports
  for each row execute procedure public.touch_updated_at();

-- ─── 4. WORKFLOW EVENTS ───────────────────────────────────────────────────────
-- Immutable audit trail: one row per stage transition.
create table if not exists public.workflow_events (
  id          uuid default gen_random_uuid() primary key,
  report_id   uuid references public.reports(id) on delete cascade not null,
  from_stage  text,
  to_stage    text not null,
  actor_id    uuid references public.profiles(id),
  actor_name  text,
  note        text,
  created_at  timestamptz default now()
);

-- ─── 5. DATA SOURCES ─────────────────────────────────────────────────────────
create table if not exists public.data_sources (
  id            uuid default gen_random_uuid() primary key,
  vertical      text not null,
  name          text not null,
  status        text default 'live'
                  check (status in ('live', 'stale', 'error')),
  tier          text default 'T2'
                  check (tier in ('T1', 'T2', 'T3')),
  last_fetched  timestamptz default now(),
  latest_value  text,
  created_at    timestamptz default now()
);

-- ─── 6. MODEL UPLOADS ────────────────────────────────────────────────────────
-- Tracks Excel / PowerPoint / Word files uploaded via /admin/upload.
create table if not exists public.model_uploads (
  id              uuid default gen_random_uuid() primary key,
  report_id       uuid references public.reports(id) on delete set null,
  vertical        text not null,
  file_name       text not null,
  file_path       text not null,   -- path in Supabase Storage bucket 'model-uploads'
  file_size       bigint,
  file_type       text             -- xlsx | pptx | docx
                    check (file_type in ('xlsx', 'pptx', 'docx')),
  model_title     text,
  model_type      text,
  version         text,
  sources_used    text,
  reviewer_notes  text,
  visibility      text default 'internal'
                    check (visibility in ('internal', 'summary', 'full')),
  status          text default 'pending'
                    check (status in ('pending', 'review', 'attached', 'rejected')),
  uploaded_by     uuid references public.profiles(id),
  uploader_name   text,
  platform_tabs   jsonb,           -- which (platform, tab) pairs were parsed from this file
  rows_ingested   integer default 0,
  created_at      timestamptz default now()
);

comment on column public.model_uploads.platform_tabs is
  'JSON array of {platform, tab, rows} objects parsed from the uploaded file.';

-- ─── 7. FACTSHEETS ───────────────────────────────────────────────────────────
create table if not exists public.factsheets (
  id               uuid primary key default gen_random_uuid(),
  slug             text unique not null,
  title            text not null,
  sub              text,
  abstract         text,                   -- HTML; first para free, rest paywalled
  vertical         text not null
                     check (vertical in ('epi', 'agri', 'trade', 'markets', 'packaging', 'startups')),
  taxonomy_node    text,
  status           text not null default 'pipeline'
                     check (status in ('published', 'updating', 'pipeline', 'gap')),
  cadence          text,
  geography        text,
  analyst          text,
  analyst_title    text,
  version          text,
  published_at     timestamptz,
  next_update_date date,
  metrics          jsonb,                  -- [{val, label, note}]
  methodology      jsonb,                  -- [{icon, title, body}]
  sources          jsonb,                  -- [{name, type, freq, live}]
  related          jsonb,                  -- [{slug, title, status}]
  public_visible   boolean not null default true,
  report_id        uuid references public.reports(id),
  created_at       timestamptz default now(),
  updated_at       timestamptz default now()
);

create trigger factsheets_updated_at
  before update on public.factsheets
  for each row execute procedure public.touch_updated_at();

-- Auto-sync: publish / revert factsheet status when linked report stage changes
create or replace function public.sync_factsheet_on_publish()
returns trigger
language plpgsql
as $$
begin
  if new.stage = 'published' and old.stage <> 'published' then
    update public.factsheets
    set status = 'published', published_at = now(), updated_at = now()
    where report_id = new.id;
  elsif new.stage in ('peer_review', 'editorial', 'approved') and old.stage = 'published' then
    update public.factsheets
    set status = 'updating', updated_at = now()
    where report_id = new.id;
  end if;
  return new;
end;
$$;

create trigger reports_stage_to_factsheet
  after update of stage on public.reports
  for each row execute procedure public.sync_factsheet_on_publish();

create index if not exists factsheets_slug_idx      on public.factsheets(slug);
create index if not exists factsheets_vertical_idx  on public.factsheets(vertical, status);
create index if not exists factsheets_report_idx    on public.factsheets(report_id);

-- ─── 8. NOTIFY SUBSCRIPTIONS ─────────────────────────────────────────────────
create table if not exists public.notify_subscriptions (
  id         uuid primary key default gen_random_uuid(),
  email      text not null,
  slug       text,       -- null = all factsheets
  vertical   text,       -- null = all verticals
  created_at timestamptz default now(),
  unique(email, slug)
);

-- ═══════════════════════════════════════════════════════════════════════════
-- ROW LEVEL SECURITY
-- ═══════════════════════════════════════════════════════════════════════════

alter table public.profiles             enable row level security;
alter table public.analyst_sessions     enable row level security;
alter table public.reports              enable row level security;
alter table public.workflow_events      enable row level security;
alter table public.data_sources         enable row level security;
alter table public.model_uploads        enable row level security;
alter table public.factsheets           enable row level security;
alter table public.notify_subscriptions enable row level security;

-- profiles: users see own row; head sees all
create policy "profiles_own_select" on public.profiles for select
  using (
    auth.uid() = id
    or exists (
      select 1 from public.profiles p
      where p.id = auth.uid() and p.role = 'head'
    )
  );
create policy "profiles_own_update" on public.profiles for update
  using (auth.uid() = id);

-- analyst_sessions: users see own sessions; head sees all
create policy "sessions_own_select" on public.analyst_sessions for select
  using (
    user_id = auth.uid()
    or exists (
      select 1 from public.profiles p
      where p.id = auth.uid() and p.role = 'head'
    )
  );
create policy "sessions_own_insert" on public.analyst_sessions for insert
  with check (user_id = auth.uid());
create policy "sessions_own_update" on public.analyst_sessions for update
  using (user_id = auth.uid());

-- reports: vertical-scoped
create policy "reports_select" on public.reports for select
  using (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid()
        and (p.vertical = 'all' or p.vertical = reports.vertical)
    )
  );
create policy "reports_insert" on public.reports for insert
  with check (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid()
        and (p.vertical = 'all' or p.vertical = vertical)
    )
  );
create policy "reports_update" on public.reports for update
  using (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid()
        and (p.vertical = 'all' or p.vertical = reports.vertical)
    )
  );

-- workflow_events
create policy "workflow_select" on public.workflow_events for select
  using (
    exists (
      select 1 from public.reports r
      join public.profiles p on p.id = auth.uid()
      where r.id = workflow_events.report_id
        and (p.vertical = 'all' or p.vertical = r.vertical)
    )
  );
create policy "workflow_insert" on public.workflow_events for insert
  with check (auth.uid() is not null);

-- data_sources
create policy "sources_select" on public.data_sources for select
  using (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid()
        and (p.vertical = 'all' or p.vertical = data_sources.vertical)
    )
  );

-- model_uploads
create policy "uploads_select" on public.model_uploads for select
  using (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid()
        and (p.vertical = 'all' or p.vertical = model_uploads.vertical)
    )
  );
create policy "uploads_insert" on public.model_uploads for insert
  with check (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid()
        and (p.vertical = 'all' or p.vertical = vertical)
    )
  );

-- factsheets: public can read visible ones; auth users see all
create policy "factsheets_public_select" on public.factsheets for select
  using (public_visible = true);
create policy "factsheets_auth_select" on public.factsheets for select
  using (auth.uid() is not null);
create policy "factsheets_insert" on public.factsheets for insert
  with check (auth.uid() is not null);
create policy "factsheets_update" on public.factsheets for update
  using (auth.uid() is not null);
create policy "factsheets_delete" on public.factsheets for delete
  using (
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid() and p.role = 'head'
    )
  );

-- notify_subscriptions: open insert; auth-only read
create policy "notify_insert" on public.notify_subscriptions for insert
  with check (true);
create policy "notify_select" on public.notify_subscriptions for select
  using (auth.uid() is not null);

-- ═══════════════════════════════════════════════════════════════════════════
-- STORAGE BUCKET
-- Run these two inserts once in the Supabase SQL Editor:
-- ═══════════════════════════════════════════════════════════════════════════
insert into storage.buckets (id, name, public)
  values ('model-uploads', 'model-uploads', false)
  on conflict do nothing;

create policy "storage_upload" on storage.objects for insert
  with check (
    bucket_id = 'model-uploads'
    and auth.uid() is not null
  );
create policy "storage_select" on storage.objects for select
  using (
    bucket_id = 'model-uploads'
    and auth.uid() is not null
  );

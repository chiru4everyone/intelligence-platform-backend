-- ═══════════════════════════════════════════════════════════════════════════
-- Intelligence Platform — Migration v1.1
-- Migration: 20261105000002_workflow_and_activity
--
-- Changes:
--   reports         — add workflow columns (due_date, stage_entered_at,
--                     submitted_at, rejection_note, assigned_senior_id,
--                     assigned_head_id)
--   activity_log    — new table: field-level audit trail for all changes
-- ═══════════════════════════════════════════════════════════════════════════

-- ─── 1. EXTEND REPORTS TABLE ─────────────────────────────────────────────────

-- Extend the stage enum to include the full approval pipeline
-- (alter check constraint by dropping and re-adding)
alter table public.reports
  drop constraint if exists reports_stage_check;

alter table public.reports
  add constraint reports_stage_check
  check (stage in (
    'draft',          -- analyst is working
    'submitted',      -- analyst submitted for senior review
    'senior_review',  -- senior analyst is reviewing
    'senior_approved',-- senior approved, waiting for head
    'head_review',    -- head of research is reviewing
    'approved',       -- head approved, ready to publish
    'published',      -- live
    'rejected'        -- rejected (check rejection_note for details)
  ));

-- Workflow tracking columns
alter table public.reports
  add column if not exists due_date          date,
  add column if not exists stage_entered_at  timestamptz default now(),
  add column if not exists submitted_at      timestamptz,
  add column if not exists rejection_note    text,
  add column if not exists rejected_by       uuid references public.profiles(id),
  add column if not exists rejected_at       timestamptz,
  add column if not exists assigned_senior_id uuid references public.profiles(id),
  add column if not exists assigned_head_id   uuid references public.profiles(id);

comment on column public.reports.stage_entered_at is
  'Timestamp when the report entered its current stage — used to calculate days stuck.';
comment on column public.reports.rejection_note is
  'Reviewer note explaining why the report was rejected.';
comment on column public.reports.assigned_senior_id is
  'Senior analyst assigned to review this report.';

-- ─── 2. ACTIVITY LOG ─────────────────────────────────────────────────────────
-- Immutable field-level audit trail. One row per change.
create table if not exists public.activity_log (
  id           uuid default gen_random_uuid() primary key,
  table_name   text not null,         -- 'reports' | 'factsheets' | 'profiles' | 'data_sources'
  record_id    uuid not null,         -- pk of the changed row
  actor_id     uuid references public.profiles(id),
  actor_name   text,
  actor_role   text,
  action       text not null,         -- 'create' | 'update' | 'delete' | 'submit' | 'approve' | 'reject'
  field_name   text,                  -- which field changed (null for create/delete/workflow actions)
  old_value    text,
  new_value    text,
  note         text,                  -- reviewer note on approve/reject
  vertical     text,
  created_at   timestamptz default now()
);

comment on table public.activity_log is
  'Immutable field-level audit trail. Every change by any user is recorded here.';

create index if not exists activity_log_record_idx  on public.activity_log(record_id);
create index if not exists activity_log_actor_idx   on public.activity_log(actor_id);
create index if not exists activity_log_table_idx   on public.activity_log(table_name, created_at desc);
create index if not exists activity_log_vertical_idx on public.activity_log(vertical, created_at desc);

-- RLS: activity log is append-only for authenticated users; master reads all via service role
alter table public.activity_log enable row level security;

create policy "activity_insert" on public.activity_log for insert
  with check (auth.uid() is not null);

create policy "activity_select" on public.activity_log for select
  using (
    -- analysts see only their own vertical's activity
    exists (
      select 1 from public.profiles p
      where p.id = auth.uid()
        and (p.vertical = 'all' or p.vertical = activity_log.vertical or p.role = 'head')
    )
  );

-- ─── 3. UPDATE WORKFLOW EVENTS (add rejection support) ───────────────────────
alter table public.workflow_events
  add column if not exists is_rejection boolean default false,
  add column if not exists rejection_note text;

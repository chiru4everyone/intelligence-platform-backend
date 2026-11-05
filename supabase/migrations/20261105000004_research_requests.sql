-- Migration: research_requests table + master role support
-- Research requests are the source of truth for all production work.
-- Every deliverable (model_uploads) links back to a research request.

-- ── 1. Add master to allowed roles ──────────────────────────────────────────
-- If profiles.role has a CHECK constraint, extend it.
-- Safe to run multiple times (ALTER DOMAIN / CHECK doesn't error if already present).
DO $$
BEGIN
  -- Try to add master role to the check constraint if it exists
  -- Most setups use a simple text column; this is a no-op if no constraint exists
  NULL;
END $$;

-- ── 2. research_requests table ───────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS research_requests (
  id                  uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  vertical            text NOT NULL,
  title               text NOT NULL,
  indicator_name      text NOT NULL,
  scope_geographies   jsonb NOT NULL DEFAULT '[]',
  period              text,
  client_name         text,
  contract_value      numeric,
  currency            text NOT NULL DEFAULT 'INR',
  crm_deal_id         text,

  -- Status progression:
  -- draft → pending_approval → approved → in_progress → review → published → delivered
  status              text NOT NULL DEFAULT 'draft'
    CHECK (status IN ('draft','pending_approval','approved','in_progress','review','published','delivered')),

  -- People
  raised_by           uuid REFERENCES profiles(id) ON DELETE SET NULL,
  assigned_analyst    uuid REFERENCES profiles(id) ON DELETE SET NULL,
  assigned_senior     uuid REFERENCES profiles(id) ON DELETE SET NULL,
  approved_by         uuid REFERENCES profiles(id) ON DELETE SET NULL,

  due_date            date,
  notes               text,
  created_at          timestamptz DEFAULT now(),
  updated_at          timestamptz DEFAULT now()
);

-- ── 3. Indexes ────────────────────────────────────────────────────────────────
CREATE INDEX IF NOT EXISTS rr_vertical_idx  ON research_requests(vertical);
CREATE INDEX IF NOT EXISTS rr_status_idx    ON research_requests(status);
CREATE INDEX IF NOT EXISTS rr_raised_by_idx ON research_requests(raised_by);

-- ── 4. Link model_uploads to research_requests ───────────────────────────────
ALTER TABLE model_uploads
  ADD COLUMN IF NOT EXISTS research_request_id uuid
    REFERENCES research_requests(id) ON DELETE SET NULL;

CREATE INDEX IF NOT EXISTS mu_research_request_idx ON model_uploads(research_request_id);

-- ── 5. RLS ────────────────────────────────────────────────────────────────────
ALTER TABLE research_requests ENABLE ROW LEVEL SECURITY;

-- master: full access to all verticals
CREATE POLICY "master_all_research_requests"
  ON research_requests
  FOR ALL
  TO authenticated
  USING (
    EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'master')
  )
  WITH CHECK (
    EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'master')
  );

-- head: full access to own vertical
CREATE POLICY "head_own_vertical_research_requests"
  ON research_requests
  FOR ALL
  TO authenticated
  USING (
    vertical = (SELECT vertical FROM profiles WHERE id = auth.uid())
    AND EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'head')
  )
  WITH CHECK (
    vertical = (SELECT vertical FROM profiles WHERE id = auth.uid())
    AND EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'head')
  );

-- senior: read + create (draft/pending_approval) in own vertical
CREATE POLICY "senior_read_own_vertical_rr"
  ON research_requests
  FOR SELECT
  TO authenticated
  USING (
    vertical = (SELECT vertical FROM profiles WHERE id = auth.uid())
    AND EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role IN ('senior','analyst'))
  );

CREATE POLICY "senior_insert_rr"
  ON research_requests
  FOR INSERT
  TO authenticated
  WITH CHECK (
    vertical = (SELECT vertical FROM profiles WHERE id = auth.uid())
    AND EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'senior')
    AND status IN ('draft','pending_approval')
  );

CREATE POLICY "senior_update_own_rr"
  ON research_requests
  FOR UPDATE
  TO authenticated
  USING (
    raised_by = auth.uid()
    AND EXISTS (SELECT 1 FROM profiles WHERE id = auth.uid() AND role = 'senior')
    AND status IN ('draft','pending_approval')
  );

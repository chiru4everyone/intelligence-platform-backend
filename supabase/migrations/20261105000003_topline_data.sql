-- Migration: topline_data table
-- Stores structured rows ingested from uploaded CSV/JSON data files.
-- Each row is one metric value for a geography + period.

CREATE TABLE IF NOT EXISTS topline_data (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  vertical      text NOT NULL,
  upload_id     uuid REFERENCES model_uploads(id) ON DELETE CASCADE,
  report_id     uuid REFERENCES reports(id) ON DELETE SET NULL,
  metric        text NOT NULL,
  geography     text,
  period        text,
  value         numeric,
  unit          text,
  delta         text,
  dir           text CHECK (dir IN ('up','down','flat','')),
  asof          date,
  created_at    timestamptz DEFAULT now()
);

CREATE INDEX IF NOT EXISTS topline_data_vertical_idx ON topline_data(vertical);
CREATE INDEX IF NOT EXISTS topline_data_upload_idx   ON topline_data(upload_id);

-- RLS: authenticated users can read their vertical's topline data
ALTER TABLE topline_data ENABLE ROW LEVEL SECURITY;

CREATE POLICY "read_own_vertical_topline"
  ON topline_data FOR SELECT
  TO authenticated
  USING (
    vertical = (SELECT vertical FROM profiles WHERE id = auth.uid())
    OR (SELECT vertical FROM profiles WHERE id = auth.uid()) = 'all'
  );

CREATE POLICY "senior_head_insert_topline"
  ON topline_data FOR INSERT
  TO authenticated
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM profiles
      WHERE id = auth.uid() AND role IN ('senior','head')
    )
  );

CREATE POLICY "senior_head_delete_topline"
  ON topline_data FOR DELETE
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM profiles
      WHERE id = auth.uid() AND role IN ('senior','head')
    )
  );

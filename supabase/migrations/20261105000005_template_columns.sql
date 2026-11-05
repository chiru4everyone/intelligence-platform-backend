-- Migration: add template path columns to research_requests
-- These store the Supabase Storage paths of generated template files.

ALTER TABLE research_requests
  ADD COLUMN IF NOT EXISTS template_report_path  text,
  ADD COLUMN IF NOT EXISTS template_model_path   text,
  ADD COLUMN IF NOT EXISTS template_topline_path text,
  ADD COLUMN IF NOT EXISTS template_deck_path    text;

-- Storage bucket for templates (run this in Supabase Dashboard → Storage → New bucket)
-- Name: templates
-- Public: false (private — signed URLs only)
-- RLS policies below apply once the bucket exists.

-- ── RLS policies for templates bucket (run AFTER creating the bucket) ────────
-- Allow authenticated users to read templates for their vertical
-- (Supabase Storage RLS uses storage.objects table)

-- Policy: head/master/senior can read templates
CREATE POLICY "auth_read_templates"
  ON storage.objects FOR SELECT
  TO authenticated
  USING (bucket_id = 'templates');

-- Policy: head/master can upload/upsert templates
CREATE POLICY "head_master_upload_templates"
  ON storage.objects FOR INSERT
  TO authenticated
  WITH CHECK (
    bucket_id = 'templates'
    AND EXISTS (
      SELECT 1 FROM profiles
      WHERE id = auth.uid() AND role IN ('head', 'master')
    )
  );

CREATE POLICY "head_master_update_templates"
  ON storage.objects FOR UPDATE
  TO authenticated
  USING (
    bucket_id = 'templates'
    AND EXISTS (
      SELECT 1 FROM profiles
      WHERE id = auth.uid() AND role IN ('head', 'master')
    )
  );

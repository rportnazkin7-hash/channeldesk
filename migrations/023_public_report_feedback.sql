-- Ответ рекламодателя по рекламному посту из публичного отчёта.

CREATE TABLE IF NOT EXISTS cd_public_report_feedback (
  id serial PRIMARY KEY,
  report_id integer NOT NULL REFERENCES cd_public_reports(id) ON DELETE CASCADE,
  workspace_id integer NOT NULL REFERENCES cd_workspaces(id) ON DELETE CASCADE,
  advertiser_id integer NOT NULL REFERENCES cd_advertisers(id) ON DELETE CASCADE,
  booking_id integer NOT NULL REFERENCES cd_ad_bookings(id) ON DELETE CASCADE,
  post_id integer REFERENCES cd_posts(id) ON DELETE SET NULL,
  decision varchar(24) NOT NULL CHECK (decision IN ('approved','changes_requested')),
  comment text NOT NULL DEFAULT '',
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cd_public_report_feedback_report
  ON cd_public_report_feedback(report_id,created_at DESC);

INSERT INTO schema_migrations(version) VALUES('023_public_report_feedback') ON CONFLICT(version) DO NOTHING;

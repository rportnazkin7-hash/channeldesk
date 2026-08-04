-- Публичные read-only отчёты для рекламодателей.

CREATE TABLE IF NOT EXISTS cd_public_reports (
  id serial PRIMARY KEY,
  workspace_id integer NOT NULL REFERENCES cd_workspaces(id) ON DELETE CASCADE,
  advertiser_id integer NOT NULL REFERENCES cd_advertisers(id) ON DELETE CASCADE,
  token_hash varchar(128) NOT NULL UNIQUE,
  expires_at timestamptz NOT NULL,
  last_accessed_at timestamptz,
  is_active boolean NOT NULL DEFAULT true,
  created_by integer REFERENCES cd_users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cd_public_reports_lookup ON cd_public_reports(token_hash, is_active, expires_at);

INSERT INTO schema_migrations(version) VALUES('020_public_advertiser_reports') ON CONFLICT(version) DO NOTHING;

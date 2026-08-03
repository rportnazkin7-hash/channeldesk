-- Этап C: медиакиты. Презентация канала для рекламодателей.
-- Выполняется одним statement за раз (ограничение psycopg3 в migrate.py).

CREATE TABLE IF NOT EXISTS cd_media_kits (
  id serial PRIMARY KEY,
  workspace_id integer NOT NULL REFERENCES cd_workspaces(id) ON DELETE CASCADE,
  name varchar(160) NOT NULL,
  channel_id integer REFERENCES cd_channels(id) ON DELETE SET NULL,
  description text NOT NULL DEFAULT '',
  audience jsonb NOT NULL DEFAULT '{}'::jsonb,
  stats jsonb NOT NULL DEFAULT '{}'::jsonb,
  pricing jsonb NOT NULL DEFAULT '[]'::jsonb,
  contacts jsonb NOT NULL DEFAULT '{}'::jsonb,
  is_active boolean NOT NULL DEFAULT true,
  created_by integer REFERENCES cd_users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cd_media_kits_workspace ON cd_media_kits(workspace_id, is_active);

INSERT INTO schema_migrations(version) VALUES('009_media_kits') ON CONFLICT(version) DO NOTHING;

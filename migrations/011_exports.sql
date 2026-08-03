-- Этап C: экспорт файлов через бота. Очередь заданий на экспорт.
-- Выполняется одним statement за раз (ограничение psycopg3 в migrate.py).

CREATE TABLE IF NOT EXISTS cd_exports (
  id serial PRIMARY KEY,
  workspace_id integer NOT NULL REFERENCES cd_workspaces(id) ON DELETE CASCADE,
  user_id integer NOT NULL REFERENCES cd_users(id) ON DELETE CASCADE,
  telegram_id bigint NOT NULL,
  kind varchar(16) NOT NULL CHECK (kind IN ('posts','bookings','finance')),
  format varchar(8) NOT NULL CHECK (format IN ('csv','xlsx','pdf')),
  status varchar(16) NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','processing','done','failed')),
  error_text text,
  created_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);
CREATE INDEX IF NOT EXISTS idx_cd_exports_pending ON cd_exports(status, created_at) WHERE status='pending';

INSERT INTO schema_migrations(version) VALUES('011_exports') ON CONFLICT(version) DO NOTHING;

-- Очередь удаления опубликованных сообщений из Telegram.

CREATE TABLE IF NOT EXISTS cd_telegram_delete_jobs (
  id serial PRIMARY KEY,
  workspace_id integer NOT NULL REFERENCES cd_workspaces(id) ON DELETE CASCADE,
  post_id integer NOT NULL REFERENCES cd_posts(id) ON DELETE CASCADE,
  channel_id integer NOT NULL REFERENCES cd_channels(id) ON DELETE CASCADE,
  telegram_chat_id bigint NOT NULL,
  telegram_message_id integer NOT NULL,
  status varchar(16) NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','processing','done','failed')),
  error_text text,
  requested_by integer REFERENCES cd_users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  completed_at timestamptz
);
CREATE INDEX IF NOT EXISTS idx_cd_telegram_delete_jobs_pending
  ON cd_telegram_delete_jobs(status, created_at) WHERE status IN ('pending','processing');
CREATE UNIQUE INDEX IF NOT EXISTS idx_cd_telegram_delete_jobs_post_active
  ON cd_telegram_delete_jobs(post_id) WHERE status IN ('pending','processing');

INSERT INTO schema_migrations(version) VALUES('021_telegram_delete_jobs') ON CONFLICT(version) DO NOTHING;

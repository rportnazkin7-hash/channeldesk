-- Аналитика только из Telegram Bot API.
-- Сохраняем доступные автоматические данные: подписчики, новые посты и реакции.

CREATE TABLE IF NOT EXISTS cd_channel_post_metrics (
  id serial PRIMARY KEY,
  workspace_id integer NOT NULL REFERENCES cd_workspaces(id) ON DELETE CASCADE,
  channel_id integer NOT NULL REFERENCES cd_channels(id) ON DELETE CASCADE,
  telegram_message_id integer NOT NULL,
  published_at timestamptz,
  reactions_count integer NOT NULL DEFAULT 0 CHECK (reactions_count >= 0),
  captured_at timestamptz NOT NULL DEFAULT now(),
  raw jsonb NOT NULL DEFAULT '{}'::jsonb,
  UNIQUE(channel_id, telegram_message_id)
);
CREATE INDEX IF NOT EXISTS idx_cd_channel_post_metrics_period
  ON cd_channel_post_metrics(workspace_id, channel_id, published_at DESC);

INSERT INTO schema_migrations(version) VALUES('019_bot_api_analytics') ON CONFLICT(version) DO NOTHING;

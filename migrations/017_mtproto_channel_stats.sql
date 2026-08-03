-- Расширенная статистика собственных каналов через Telegram MTProto.
-- Доступна только каналам, где пользовательская Telegram-сессия имеет права
-- просмотра статистики (обычно администратор канала достаточного размера).

ALTER TABLE cd_channel_metrics DROP CONSTRAINT IF EXISTS cd_channel_metrics_source_check;
ALTER TABLE cd_channel_metrics ADD CONSTRAINT cd_channel_metrics_source_check
  CHECK (source IN ('manual','bot_api','mtproto'));

CREATE TABLE IF NOT EXISTS cd_channel_stats_snapshots (
  id serial PRIMARY KEY,
  workspace_id integer NOT NULL REFERENCES cd_workspaces(id) ON DELETE CASCADE,
  channel_id integer NOT NULL REFERENCES cd_channels(id) ON DELETE CASCADE,
  captured_at timestamptz NOT NULL DEFAULT now(),
  period_start date,
  period_end date,
  followers_current bigint NOT NULL DEFAULT 0 CHECK (followers_current >= 0),
  followers_previous bigint NOT NULL DEFAULT 0 CHECK (followers_previous >= 0),
  views_per_post numeric(14,2) NOT NULL DEFAULT 0 CHECK (views_per_post >= 0),
  shares_per_post numeric(14,2) NOT NULL DEFAULT 0 CHECK (shares_per_post >= 0),
  reactions_per_post numeric(14,2) NOT NULL DEFAULT 0 CHECK (reactions_per_post >= 0),
  views_per_story numeric(14,2) NOT NULL DEFAULT 0 CHECK (views_per_story >= 0),
  shares_per_story numeric(14,2) NOT NULL DEFAULT 0 CHECK (shares_per_story >= 0),
  reactions_per_story numeric(14,2) NOT NULL DEFAULT 0 CHECK (reactions_per_story >= 0),
  enabled_notifications numeric(8,4) NOT NULL DEFAULT 0 CHECK (enabled_notifications >= 0),
  raw jsonb NOT NULL DEFAULT '{}'::jsonb,
  error_text text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cd_channel_stats_snapshots_period
  ON cd_channel_stats_snapshots(workspace_id, channel_id, captured_at DESC);

INSERT INTO schema_migrations(version) VALUES('017_mtproto_channel_stats') ON CONFLICT(version) DO NOTHING;

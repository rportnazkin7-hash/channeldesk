-- Этап C: ручная аналитика каналов и собственные ссылки.
-- Bot API не отдаёт полную нативную статистику, поэтому первый слой хранит
-- доступные/введённые вручную дневные показатели.

CREATE TABLE IF NOT EXISTS cd_channel_metrics (
  id serial PRIMARY KEY,
  workspace_id integer NOT NULL REFERENCES cd_workspaces(id) ON DELETE CASCADE,
  channel_id integer NOT NULL REFERENCES cd_channels(id) ON DELETE CASCADE,
  metric_date date NOT NULL,
  subscribers integer NOT NULL DEFAULT 0 CHECK (subscribers >= 0),
  views integer NOT NULL DEFAULT 0 CHECK (views >= 0),
  reach integer NOT NULL DEFAULT 0 CHECK (reach >= 0),
  reactions integer NOT NULL DEFAULT 0 CHECK (reactions >= 0),
  forwards integer NOT NULL DEFAULT 0 CHECK (forwards >= 0),
  posts_count integer NOT NULL DEFAULT 0 CHECK (posts_count >= 0),
  source varchar(16) NOT NULL DEFAULT 'manual' CHECK (source IN ('manual','bot_api')),
  notes text NOT NULL DEFAULT '',
  created_by integer REFERENCES cd_users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(workspace_id, channel_id, metric_date)
);
CREATE INDEX IF NOT EXISTS idx_cd_channel_metrics_period
  ON cd_channel_metrics(workspace_id, channel_id, metric_date DESC);

CREATE TABLE IF NOT EXISTS cd_channel_links (
  id serial PRIMARY KEY,
  workspace_id integer NOT NULL REFERENCES cd_workspaces(id) ON DELETE CASCADE,
  channel_id integer NOT NULL REFERENCES cd_channels(id) ON DELETE CASCADE,
  name varchar(160) NOT NULL,
  url text NOT NULL,
  clicks integer NOT NULL DEFAULT 0 CHECK (clicks >= 0),
  conversions integer NOT NULL DEFAULT 0 CHECK (conversions >= 0),
  notes text NOT NULL DEFAULT '',
  is_active boolean NOT NULL DEFAULT true,
  created_by integer REFERENCES cd_users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cd_channel_links_workspace ON cd_channel_links(workspace_id, channel_id, is_active);

INSERT INTO schema_migrations(version) VALUES('016_channel_analytics') ON CONFLICT(version) DO NOTHING;

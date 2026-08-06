-- Release feedback: bug reports from Bot and Mini App.
CREATE TABLE IF NOT EXISTS cd_bug_reports (
  id serial PRIMARY KEY,
  workspace_id integer REFERENCES cd_workspaces(id) ON DELETE SET NULL,
  user_id integer REFERENCES cd_users(id) ON DELETE SET NULL,
  telegram_id bigint,
  username varchar(255),
  first_name varchar(255),
  description text NOT NULL,
  screen varchar(160) NOT NULL DEFAULT '',
  severity varchar(16) NOT NULL DEFAULT 'normal'
    CHECK (severity IN ('low','normal','high','critical')),
  source varchar(32) NOT NULL DEFAULT 'mini_app',
  app_version varchar(32) NOT NULL DEFAULT '',
  context jsonb NOT NULL DEFAULT '{}'::jsonb,
  message_id bigint,
  chat_id bigint,
  attachment_file_id text,
  attachment_type varchar(32),
  attachment_name varchar(255),
  status varchar(16) NOT NULL DEFAULT 'new'
    CHECK (status IN ('new','in_progress','fixed','closed')),
  resolution text NOT NULL DEFAULT '',
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  resolved_at timestamptz
);
CREATE INDEX IF NOT EXISTS idx_cd_bug_reports_workspace ON cd_bug_reports(workspace_id,status,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cd_bug_reports_created ON cd_bug_reports(created_at DESC);

INSERT INTO schema_migrations(version) VALUES('029_bug_reports') ON CONFLICT(version) DO NOTHING;

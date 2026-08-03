-- Этап B: публикации. Контент, версии, комментарии, согласование, шаблоны,
-- а также журнал попыток публикации для надёжного publisher.
-- ВАЖНО: выполняется одним statement за раз (ограничение psycopg3 в migrate.py).

CREATE TABLE IF NOT EXISTS cd_posts (
  id serial PRIMARY KEY,
  workspace_id integer NOT NULL REFERENCES cd_workspaces(id) ON DELETE CASCADE,
  channel_id integer REFERENCES cd_channels(id) ON DELETE SET NULL,
  title varchar(255) NOT NULL DEFAULT '',
  text text NOT NULL DEFAULT '',
  status varchar(24) NOT NULL DEFAULT 'draft'
    CHECK (status IN ('idea','draft','in_progress','review','changes_requested','approved',
                      'scheduled','publishing','published','failed','cancelled')),
  scheduled_at timestamptz,
  publish_key varchar(80) UNIQUE,
  telegram_message_id bigint,
  approval_required boolean NOT NULL DEFAULT true,
  created_by integer REFERENCES cd_users(id) ON DELETE SET NULL,
  approved_by integer REFERENCES cd_users(id) ON DELETE SET NULL,
  attempt_count integer NOT NULL DEFAULT 0,
  last_error text,
  published_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cd_posts_workspace ON cd_posts(workspace_id, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_cd_posts_status ON cd_posts(status) WHERE status IN ('scheduled','publishing');
CREATE INDEX IF NOT EXISTS idx_cd_posts_channel ON cd_posts(channel_id) WHERE channel_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS cd_post_versions (
  id serial PRIMARY KEY,
  post_id integer NOT NULL REFERENCES cd_posts(id) ON DELETE CASCADE,
  title varchar(255) NOT NULL DEFAULT '',
  text text NOT NULL DEFAULT '',
  created_by integer REFERENCES cd_users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cd_post_versions_post ON cd_post_versions(post_id, created_at);

CREATE TABLE IF NOT EXISTS cd_post_comments (
  id serial PRIMARY KEY,
  post_id integer NOT NULL REFERENCES cd_posts(id) ON DELETE CASCADE,
  user_id integer REFERENCES cd_users(id) ON DELETE SET NULL,
  text text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cd_post_comments_post ON cd_post_comments(post_id, created_at);

CREATE TABLE IF NOT EXISTS cd_content_assets (
  id serial PRIMARY KEY,
  workspace_id integer NOT NULL REFERENCES cd_workspaces(id) ON DELETE CASCADE,
  post_id integer REFERENCES cd_posts(id) ON DELETE SET NULL,
  file_name varchar(255) NOT NULL,
  file_type varchar(64) NOT NULL DEFAULT 'file',
  file_url text NOT NULL,
  size_bytes bigint,
  uploaded_by integer REFERENCES cd_users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cd_content_assets_workspace ON cd_content_assets(workspace_id, created_at DESC);

CREATE TABLE IF NOT EXISTS cd_post_templates (
  id serial PRIMARY KEY,
  workspace_id integer NOT NULL REFERENCES cd_workspaces(id) ON DELETE CASCADE,
  name varchar(160) NOT NULL,
  title varchar(255) NOT NULL DEFAULT '',
  text text NOT NULL DEFAULT '',
  created_by integer REFERENCES cd_users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cd_post_templates_workspace ON cd_post_templates(workspace_id);

CREATE TABLE IF NOT EXISTS cd_publish_attempts (
  id bigserial PRIMARY KEY,
  post_id integer NOT NULL REFERENCES cd_posts(id) ON DELETE CASCADE,
  attempted_at timestamptz NOT NULL DEFAULT now(),
  success boolean NOT NULL,
  error_text text,
  telegram_message_id bigint
);
CREATE INDEX IF NOT EXISTS idx_cd_publish_attempts_post ON cd_publish_attempts(post_id, attempted_at DESC);

INSERT INTO schema_migrations(version) VALUES('004_posts') ON CONFLICT(version) DO NOTHING;

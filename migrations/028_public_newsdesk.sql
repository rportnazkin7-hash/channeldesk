-- Public ChannelDesk Newsdesk: reader submissions become editor drafts.
CREATE TABLE IF NOT EXISTS cd_public_news_pages (
  id serial PRIMARY KEY,
  workspace_id integer NOT NULL REFERENCES cd_workspaces(id) ON DELETE CASCADE,
  channel_id integer REFERENCES cd_channels(id) ON DELETE SET NULL,
  token_hash varchar(128) NOT NULL UNIQUE,
  title varchar(160) NOT NULL DEFAULT 'Предложить новость',
  description text NOT NULL DEFAULT '',
  is_active boolean NOT NULL DEFAULT true,
  created_by integer REFERENCES cd_users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cd_public_news_pages_workspace ON cd_public_news_pages(workspace_id,is_active);

CREATE TABLE IF NOT EXISTS cd_public_news_requests (
  id serial PRIMARY KEY,
  page_id integer NOT NULL REFERENCES cd_public_news_pages(id) ON DELETE CASCADE,
  workspace_id integer NOT NULL REFERENCES cd_workspaces(id) ON DELETE CASCADE,
  channel_id integer REFERENCES cd_channels(id) ON DELETE SET NULL,
  post_id integer REFERENCES cd_posts(id) ON DELETE SET NULL,
  contact_name varchar(160) NOT NULL DEFAULT '',
  contact_telegram varchar(160) NOT NULL DEFAULT '',
  contact_email varchar(255) NOT NULL DEFAULT '',
  source_url text NOT NULL DEFAULT '',
  is_anonymous boolean NOT NULL DEFAULT false,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cd_public_news_requests_workspace ON cd_public_news_requests(workspace_id,created_at DESC);
CREATE INDEX IF NOT EXISTS idx_cd_public_news_requests_post ON cd_public_news_requests(post_id);

INSERT INTO schema_migrations(version) VALUES('028_public_newsdesk') ON CONFLICT(version) DO NOTHING;

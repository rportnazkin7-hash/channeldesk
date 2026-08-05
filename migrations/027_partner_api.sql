-- Public partner API: API keys, idempotent draft creation and webhook settings.
ALTER TABLE cd_posts ADD COLUMN IF NOT EXISTS source varchar(64) NOT NULL DEFAULT 'manual';
ALTER TABLE cd_posts ADD COLUMN IF NOT EXISTS source_url text;
ALTER TABLE cd_posts ADD COLUMN IF NOT EXISTS external_id varchar(255);
CREATE INDEX IF NOT EXISTS idx_cd_posts_source_external ON cd_posts(workspace_id,source,external_id);

CREATE TABLE IF NOT EXISTS cd_api_keys (
  id serial PRIMARY KEY,
  workspace_id integer NOT NULL REFERENCES cd_workspaces(id) ON DELETE CASCADE,
  name varchar(160) NOT NULL,
  key_prefix varchar(32) NOT NULL,
  key_hash varchar(128) NOT NULL UNIQUE,
  scopes jsonb NOT NULL DEFAULT '["drafts:create","posts:read","channels:read"]'::jsonb,
  expires_at timestamptz,
  last_used_at timestamptz,
  revoked_at timestamptz,
  created_by integer REFERENCES cd_users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cd_api_keys_workspace ON cd_api_keys(workspace_id,revoked_at,created_at DESC);

CREATE TABLE IF NOT EXISTS cd_api_webhooks (
  id serial PRIMARY KEY,
  workspace_id integer NOT NULL REFERENCES cd_workspaces(id) ON DELETE CASCADE,
  name varchar(160) NOT NULL,
  url text NOT NULL,
  secret text NOT NULL,
  events jsonb NOT NULL DEFAULT '["post.created"]'::jsonb,
  is_active boolean NOT NULL DEFAULT true,
  last_delivered_at timestamptz,
  last_error text,
  created_by integer REFERENCES cd_users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cd_api_webhooks_workspace ON cd_api_webhooks(workspace_id,is_active);

CREATE TABLE IF NOT EXISTS cd_api_idempotency_keys (
  id bigserial PRIMARY KEY,
  api_key_id integer NOT NULL REFERENCES cd_api_keys(id) ON DELETE CASCADE,
  idempotency_key varchar(255) NOT NULL,
  request_hash varchar(128) NOT NULL,
  response_json jsonb NOT NULL,
  status_code integer NOT NULL DEFAULT 201,
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(api_key_id,idempotency_key)
);
CREATE INDEX IF NOT EXISTS idx_cd_api_idempotency_created ON cd_api_idempotency_keys(created_at);

INSERT INTO schema_migrations(version) VALUES('027_partner_api') ON CONFLICT(version) DO NOTHING;

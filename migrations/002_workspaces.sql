CREATE TABLE IF NOT EXISTS cd_users (
 id serial PRIMARY KEY, telegram_id bigint NOT NULL UNIQUE, username varchar(255), first_name varchar(255), last_name varchar(255),
 is_blocked boolean NOT NULL DEFAULT false, last_seen_at timestamptz, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS cd_workspaces (
 id serial PRIMARY KEY, name varchar(160) NOT NULL, slug varchar(100) NOT NULL UNIQUE, owner_user_id integer NOT NULL REFERENCES cd_users(id),
 plan varchar(32) NOT NULL DEFAULT 'agency', timezone varchar(64) NOT NULL DEFAULT 'Europe/Moscow', currency varchar(8) NOT NULL DEFAULT 'RUB',
 logo_url text, settings jsonb NOT NULL DEFAULT '{}'::jsonb, is_active boolean NOT NULL DEFAULT true,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS cd_workspace_members (
 id serial PRIMARY KEY, workspace_id integer NOT NULL REFERENCES cd_workspaces(id) ON DELETE CASCADE, user_id integer NOT NULL REFERENCES cd_users(id) ON DELETE CASCADE,
 role varchar(32) NOT NULL DEFAULT 'viewer' CHECK(role IN ('owner','admin','editor','author','designer','ad_manager','analyst','viewer')),
 status varchar(24) NOT NULL DEFAULT 'active', channel_scope jsonb NOT NULL DEFAULT '[]'::jsonb, invited_by integer REFERENCES cd_users(id),
 joined_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(), UNIQUE(workspace_id,user_id)
);
CREATE TABLE IF NOT EXISTS cd_invites (
 id serial PRIMARY KEY, workspace_id integer NOT NULL REFERENCES cd_workspaces(id) ON DELETE CASCADE, token_hash varchar(128) NOT NULL UNIQUE,
 role varchar(32) NOT NULL DEFAULT 'viewer', channel_scope jsonb NOT NULL DEFAULT '[]'::jsonb, max_uses integer, used_count integer NOT NULL DEFAULT 0,
 expires_at timestamptz, created_by integer NOT NULL REFERENCES cd_users(id), is_active boolean NOT NULL DEFAULT true, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS cd_channels (
 id serial PRIMARY KEY, workspace_id integer NOT NULL REFERENCES cd_workspaces(id) ON DELETE CASCADE, telegram_chat_id bigint NOT NULL UNIQUE,
 title varchar(255) NOT NULL, username varchar(255), description text, timezone varchar(64) NOT NULL DEFAULT 'Europe/Moscow',
 bot_permissions jsonb NOT NULL DEFAULT '{}'::jsonb, signature text, approval_required boolean NOT NULL DEFAULT true,
 is_connected boolean NOT NULL DEFAULT false, is_active boolean NOT NULL DEFAULT true, connected_by integer REFERENCES cd_users(id), connected_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS cd_audit_log (
 id bigserial PRIMARY KEY, workspace_id integer NOT NULL REFERENCES cd_workspaces(id) ON DELETE CASCADE, user_id integer REFERENCES cd_users(id) ON DELETE SET NULL,
 action varchar(96) NOT NULL, entity_type varchar(64) NOT NULL, entity_id bigint, details jsonb NOT NULL DEFAULT '{}'::jsonb, created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cd_members_user ON cd_workspace_members(user_id,status);
CREATE INDEX IF NOT EXISTS idx_cd_channels_workspace ON cd_channels(workspace_id,is_active);
CREATE INDEX IF NOT EXISTS idx_cd_audit_workspace ON cd_audit_log(workspace_id,created_at DESC);
INSERT INTO schema_migrations(version) VALUES('002_workspaces') ON CONFLICT(version) DO NOTHING;

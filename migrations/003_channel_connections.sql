CREATE TABLE IF NOT EXISTS cd_channel_connections (
 id serial PRIMARY KEY,
 telegram_chat_id bigint NOT NULL UNIQUE,
 title varchar(255) NOT NULL,
 username varchar(255),
 actor_telegram_id bigint NOT NULL,
 bot_permissions jsonb NOT NULL DEFAULT '{}'::jsonb,
 status varchar(24) NOT NULL DEFAULT 'pending',
 connected_channel_id integer REFERENCES cd_channels(id) ON DELETE SET NULL,
 observed_at timestamptz NOT NULL DEFAULT now(),
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cd_channel_connections_actor ON cd_channel_connections(actor_telegram_id,status,updated_at DESC);
INSERT INTO schema_migrations(version) VALUES('003_channel_connections') ON CONFLICT(version) DO NOTHING;

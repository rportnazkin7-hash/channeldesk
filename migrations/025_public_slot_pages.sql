-- Публичная витрина свободных рекламных слотов одного канала.

CREATE TABLE IF NOT EXISTS cd_public_slot_pages (
  id serial PRIMARY KEY,
  workspace_id integer NOT NULL REFERENCES cd_workspaces(id) ON DELETE CASCADE,
  channel_id integer NOT NULL REFERENCES cd_channels(id) ON DELETE CASCADE,
  token_hash varchar(128) NOT NULL UNIQUE,
  title varchar(160) NOT NULL DEFAULT 'Рекламные размещения',
  description text NOT NULL DEFAULT '',
  default_cost numeric(12,2) NOT NULL DEFAULT 0 CHECK (default_cost >= 0),
  currency varchar(8) NOT NULL DEFAULT 'RUB',
  is_active boolean NOT NULL DEFAULT true,
  created_by integer REFERENCES cd_users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cd_public_slot_pages_channel ON cd_public_slot_pages(workspace_id,channel_id,is_active);

CREATE TABLE IF NOT EXISTS cd_public_slot_requests (
  id serial PRIMARY KEY,
  page_id integer NOT NULL REFERENCES cd_public_slot_pages(id) ON DELETE CASCADE,
  workspace_id integer NOT NULL REFERENCES cd_workspaces(id) ON DELETE CASCADE,
  channel_id integer NOT NULL REFERENCES cd_channels(id) ON DELETE CASCADE,
  booking_id integer REFERENCES cd_ad_bookings(id) ON DELETE SET NULL,
  contact_name varchar(160) NOT NULL,
  contact_telegram varchar(160) NOT NULL DEFAULT '',
  contact_email varchar(255) NOT NULL DEFAULT '',
  target_url text NOT NULL DEFAULT '',
  format varchar(32) NOT NULL DEFAULT 'post',
  comment text NOT NULL DEFAULT '',
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cd_public_slot_requests_workspace ON cd_public_slot_requests(workspace_id,created_at DESC);

INSERT INTO schema_migrations(version) VALUES('025_public_slot_pages') ON CONFLICT(version) DO NOTHING;

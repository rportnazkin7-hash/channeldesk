-- Этап C: рекламное агентство. Рекламодатели, бронирования, финансы.
-- Выполняется одним statement за раз (ограничение psycopg3 в migrate.py).

CREATE TABLE IF NOT EXISTS cd_advertisers (
  id serial PRIMARY KEY,
  workspace_id integer NOT NULL REFERENCES cd_workspaces(id) ON DELETE CASCADE,
  name varchar(160) NOT NULL,
  contact jsonb NOT NULL DEFAULT '{}'::jsonb,
  notes text NOT NULL DEFAULT '',
  is_active boolean NOT NULL DEFAULT true,
  created_by integer REFERENCES cd_users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cd_advertisers_workspace ON cd_advertisers(workspace_id, is_active);

CREATE TABLE IF NOT EXISTS cd_ad_bookings (
  id serial PRIMARY KEY,
  workspace_id integer NOT NULL REFERENCES cd_workspaces(id) ON DELETE CASCADE,
  advertiser_id integer NOT NULL REFERENCES cd_advertisers(id) ON DELETE CASCADE,
  channel_id integer REFERENCES cd_channels(id) ON DELETE SET NULL,
  post_id integer REFERENCES cd_posts(id) ON DELETE SET NULL,
  format varchar(32) NOT NULL DEFAULT 'post'
    CHECK (format IN ('post','mention','repost','other')),
  cost numeric(12,2) NOT NULL DEFAULT 0,
  currency varchar(8) NOT NULL DEFAULT 'RUB',
  status varchar(24) NOT NULL DEFAULT 'requested'
    CHECK (status IN ('requested','confirmed','in_progress','done','cancelled')),
  payment_status varchar(24) NOT NULL DEFAULT 'unpaid'
    CHECK (payment_status IN ('unpaid','partially_paid','paid')),
  publish_at timestamptz,
  delete_at timestamptz,
  erid text,
  requisites jsonb NOT NULL DEFAULT '{}'::jsonb,
  materials_url text,
  report_url text,
  created_by integer REFERENCES cd_users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cd_ad_bookings_workspace ON cd_ad_bookings(workspace_id, publish_at);
CREATE INDEX IF NOT EXISTS idx_cd_ad_bookings_adv ON cd_ad_bookings(advertiser_id);

CREATE TABLE IF NOT EXISTS cd_finance_transactions (
  id serial PRIMARY KEY,
  workspace_id integer NOT NULL REFERENCES cd_workspaces(id) ON DELETE CASCADE,
  booking_id integer REFERENCES cd_ad_bookings(id) ON DELETE SET NULL,
  type varchar(16) NOT NULL CHECK (type IN ('income','expense')),
  amount numeric(12,2) NOT NULL CHECK (amount >= 0),
  currency varchar(8) NOT NULL DEFAULT 'RUB',
  category varchar(32) NOT NULL DEFAULT 'other',
  description text NOT NULL DEFAULT '',
  occurred_at timestamptz NOT NULL DEFAULT now(),
  created_by integer REFERENCES cd_users(id) ON DELETE SET NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_cd_finance_workspace ON cd_finance_transactions(workspace_id, occurred_at);

INSERT INTO schema_migrations(version) VALUES('007_ads') ON CONFLICT(version) DO NOTHING;

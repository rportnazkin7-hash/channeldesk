-- Ежедневный ChannelDesk Pulse в Telegram.

CREATE TABLE IF NOT EXISTS cd_pulse_deliveries (
  id serial PRIMARY KEY,
  workspace_id integer NOT NULL REFERENCES cd_workspaces(id) ON DELETE CASCADE,
  pulse_date date NOT NULL,
  status varchar(16) NOT NULL DEFAULT 'sending'
    CHECK (status IN ('sending','sent','failed')),
  error_text text,
  sent_at timestamptz,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE(workspace_id,pulse_date)
);
CREATE INDEX IF NOT EXISTS idx_cd_pulse_deliveries_date ON cd_pulse_deliveries(pulse_date,status);

INSERT INTO schema_migrations(version) VALUES('024_daily_pulse') ON CONFLICT(version) DO NOTHING;

-- Автоматический трекинг переходов по ссылкам кампаний.

ALTER TABLE cd_channel_links ADD COLUMN IF NOT EXISTS booking_id integer REFERENCES cd_ad_bookings(id) ON DELETE SET NULL;
ALTER TABLE cd_channel_links ADD COLUMN IF NOT EXISTS tracking_token_hash varchar(128);
CREATE UNIQUE INDEX IF NOT EXISTS idx_cd_channel_links_tracking_token
  ON cd_channel_links(tracking_token_hash) WHERE tracking_token_hash IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_cd_channel_links_booking ON cd_channel_links(booking_id);

INSERT INTO schema_migrations(version) VALUES('022_tracking_links') ON CONFLICT(version) DO NOTHING;

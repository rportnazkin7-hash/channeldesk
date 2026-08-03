-- Этап C: пометка «ERID не требуется» для броней от обычных Telegram-каналов.
-- Выполняется одним statement за раз (ограничение psycopg3 в migrate.py).

ALTER TABLE cd_ad_bookings ADD COLUMN IF NOT EXISTS erid_required boolean NOT NULL DEFAULT true;

INSERT INTO schema_migrations(version) VALUES('008_ads_erid') ON CONFLICT(version) DO NOTHING;

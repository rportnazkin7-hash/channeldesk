-- Этап C: жизненный цикл размещений. Новые статусы active/overdue + авто-отмена.
-- Выполняется одним statement за раз (ограничение psycopg3 в migrate.py).

ALTER TABLE cd_ad_bookings DROP CONSTRAINT IF EXISTS cd_ad_bookings_status_check;
ALTER TABLE cd_ad_bookings ADD CONSTRAINT cd_ad_bookings_status_check
  CHECK (status IN ('requested','confirmed','active','done','cancelled','overdue'));

-- Индексы для быстрых автоматических переходов статусов
CREATE INDEX IF NOT EXISTS idx_cd_bookings_lifecycle ON cd_ad_bookings(status, publish_at, delete_at)
  WHERE status IN ('requested','confirmed','active','overdue');

INSERT INTO schema_migrations(version) VALUES('013_booking_lifecycle') ON CONFLICT(version) DO NOTHING;

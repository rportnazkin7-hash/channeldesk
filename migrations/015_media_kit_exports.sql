-- Этап C: экспорт медиакитов в PDF через бота.
-- Старые типы экспортов сохраняются.

ALTER TABLE cd_exports DROP CONSTRAINT IF EXISTS cd_exports_kind_check;
ALTER TABLE cd_exports ADD CONSTRAINT cd_exports_kind_check
  CHECK (kind IN ('posts','bookings','finance','media_kits'));

INSERT INTO schema_migrations(version) VALUES('015_media_kit_exports') ON CONFLICT(version) DO NOTHING;

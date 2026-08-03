-- Этап C (фикс): расширить CHECK-ограничение статуса экспорта.
-- Код бота использует 'processing', но constraint из 011 разрешал только
-- ('pending','done','failed') — из-за этого задания не обрабатывались.
-- Выполняется одним statement за раз (ограничение psycopg3 в migrate.py).

ALTER TABLE cd_exports DROP CONSTRAINT IF EXISTS cd_exports_status_check;
ALTER TABLE cd_exports ADD CONSTRAINT cd_exports_status_check
  CHECK (status IN ('pending','processing','done','failed'));

INSERT INTO schema_migrations(version) VALUES('012_exports_status') ON CONFLICT(version) DO NOTHING;

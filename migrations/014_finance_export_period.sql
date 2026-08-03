-- Статистика: экспорт финансов за выбранный месяц.
-- Пустые значения сохраняют совместимость со старыми заданиями (полная история).

ALTER TABLE cd_exports ADD COLUMN IF NOT EXISTS period_year integer;
ALTER TABLE cd_exports ADD COLUMN IF NOT EXISTS period_month integer;

INSERT INTO schema_migrations(version) VALUES('014_finance_export_period') ON CONFLICT(version) DO NOTHING;

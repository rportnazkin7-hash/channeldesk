-- Бесплатная интеграция TGStat: текущие показатели канала.
-- Историческая динамика зависит от тарифа TGStat и не вызывается автоматически.

ALTER TABLE cd_channel_metrics DROP CONSTRAINT IF EXISTS cd_channel_metrics_source_check;
ALTER TABLE cd_channel_metrics ADD CONSTRAINT cd_channel_metrics_source_check
  CHECK (source IN ('manual','bot_api','mtproto','tgstat'));

ALTER TABLE cd_channel_stats_snapshots ADD COLUMN IF NOT EXISTS source varchar(16) NOT NULL DEFAULT 'mtproto';
ALTER TABLE cd_channel_stats_snapshots DROP CONSTRAINT IF EXISTS cd_channel_stats_snapshots_source_check;
ALTER TABLE cd_channel_stats_snapshots ADD CONSTRAINT cd_channel_stats_snapshots_source_check
  CHECK (source IN ('mtproto','tgstat'));

INSERT INTO schema_migrations(version) VALUES('018_tgstat_source') ON CONFLICT(version) DO NOTHING;

-- Этап B (продолжение): inline-кнопки в постах и индекс календаря по датам.
-- Выполняется одним statement за раз (ограничение psycopg3 в migrate.py).

ALTER TABLE cd_posts ADD COLUMN IF NOT EXISTS buttons jsonb NOT NULL DEFAULT '[]'::jsonb;

CREATE INDEX IF NOT EXISTS idx_cd_posts_scheduled ON cd_posts(scheduled_at) WHERE status='scheduled';

INSERT INTO schema_migrations(version) VALUES('005_posts_ext') ON CONFLICT(version) DO NOTHING;

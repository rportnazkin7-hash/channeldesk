-- Уведомления владельцу о заявках с публичной витрины.

ALTER TABLE cd_public_slot_requests ADD COLUMN IF NOT EXISTS notified_at timestamptz;
CREATE INDEX IF NOT EXISTS idx_cd_public_slot_requests_unnotified
  ON cd_public_slot_requests(created_at) WHERE notified_at IS NULL;

INSERT INTO schema_migrations(version) VALUES('026_slot_request_notifications') ON CONFLICT(version) DO NOTHING;

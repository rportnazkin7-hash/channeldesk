#!/usr/bin/env bash
set -Eeuo pipefail

: "${DATABASE_URL:?DATABASE_URL is required}"

OUT_DIR="${BACKUP_DIR:-./backups}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
mkdir -p "$OUT_DIR"
FILE="$OUT_DIR/channeldesk-$STAMP.dump"

pg_dump \
  --format=custom \
  --no-owner \
  --no-privileges \
  --file="$FILE" \
  "$DATABASE_URL"

sha256sum "$FILE" > "$FILE.sha256"
printf 'Backup created: %s\nChecksum: %s\n' "$FILE" "$FILE.sha256"

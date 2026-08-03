from __future__ import annotations
import logging
from pathlib import Path

import psycopg

from bot.db import db_url

logger = logging.getLogger('channeldesk.migrate')

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / 'migrations'


def apply_pending_migrations() -> int:
    """Идемпотентно применяет неприменённые миграции при старте бота.

    Каждый файл выполняется независимо: падение одного не блокирует остальные.
    """
    files = sorted(MIGRATIONS_DIR.glob('*.sql'))
    applied = 0
    with psycopg.connect(db_url()) as conn:
        for path in files:
            version = path.stem
            try:
                with conn.cursor() as cur:
                    cur.execute("""CREATE TABLE IF NOT EXISTS schema_migrations(
                        version varchar(64) PRIMARY KEY, applied_at timestamptz NOT NULL DEFAULT now())""")
                    cur.execute('SELECT 1 FROM schema_migrations WHERE version=%s', (version,))
                    if cur.fetchone():
                        continue
                    statements = [s.strip() for s in path.read_text(encoding='utf-8').split(';') if s.strip()]
                    for statement in statements:
                        cur.execute(statement)
                    cur.execute("INSERT INTO schema_migrations(version) VALUES(%s) ON CONFLICT (version) DO NOTHING",
                                (version,))
                conn.commit()
                applied += 1
                logger.info('migration applied: %s', version)
            except Exception as exc:  # noqa: BLE001
                conn.rollback()
                logger.warning('migration %s failed, skipping: %s', version, exc)
    return applied

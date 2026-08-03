from __future__ import annotations
import os


def db_url() -> str:
    value = os.getenv('DATABASE_URL', '').strip()
    if not value:
        raise RuntimeError('DATABASE_URL is required')
    return value.replace('postgresql+psycopg://', 'postgresql://').replace('postgresql+asyncpg://', 'postgresql://')

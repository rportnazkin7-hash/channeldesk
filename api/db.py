from __future__ import annotations
import os
import psycopg
from fastapi import HTTPException

CONNECT_TIMEOUT = 6  # секунды; защита от зависания запросов к Supabase


def database_url() -> str:
    value = os.getenv('DATABASE_URL', '').strip()
    if not value:
        raise HTTPException(status_code=503, detail='DATABASE_URL is not configured')
    return value.replace('postgresql+psycopg://', 'postgresql://').replace('postgresql+asyncpg://', 'postgresql://')


def connect():
    try:
        return psycopg.connect(database_url(), row_factory=psycopg.rows.dict_row, connect_timeout=CONNECT_TIMEOUT)
    except psycopg.Error:
        raise HTTPException(status_code=503, detail='База данных недоступна. Проверьте DATABASE_URL и подключение Supabase.')

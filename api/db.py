from __future__ import annotations
import os
import psycopg
from fastapi import HTTPException


def database_url() -> str:
    value=os.getenv('DATABASE_URL','').strip()
    if not value:
        raise HTTPException(status_code=503,detail='DATABASE_URL is not configured')
    return value.replace('postgresql+psycopg://','postgresql://').replace('postgresql+asyncpg://','postgresql://')


def connect():
    return psycopg.connect(database_url(),row_factory=psycopg.rows.dict_row)

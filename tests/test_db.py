import pytest
from fastapi import HTTPException

from api.db import connect, database_url


def test_database_url_not_configured(monkeypatch):
    monkeypatch.delenv('DATABASE_URL', raising=False)
    with pytest.raises(HTTPException) as exc:
        database_url()
    assert exc.value.status_code == 503


def test_database_url_normalizes_dialects(monkeypatch):
    monkeypatch.setenv('DATABASE_URL', 'postgresql+psycopg://user:pass@host:5432/db')
    assert database_url() == 'postgresql://user:pass@host:5432/db'
    monkeypatch.setenv('DATABASE_URL', 'postgresql+asyncpg://u:p@h/x')
    assert database_url() == 'postgresql://u:p@h/x'


def test_connect_unreachable_returns_503(monkeypatch):
    # Порт 1 на localhost — гарантированный отказ соединения, быстрый, без внешних зависимостей
    monkeypatch.setenv('DATABASE_URL', 'postgresql://user:pass@127.0.0.1:1/nonexistent')
    with pytest.raises(HTTPException) as exc:
        connect()
    assert exc.value.status_code == 503

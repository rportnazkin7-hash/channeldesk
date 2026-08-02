import hmac
import hashlib
import json
import time
from urllib.parse import urlencode

import pytest
from fastapi import HTTPException

from api.auth import validate_init_data


def make_init_data(token: str, user: dict, age_seconds: int = 60) -> str:
    pairs = {'auth_date': str(int(time.time()) - age_seconds), 'user': json.dumps(user)}
    check = '\n'.join(f'{k}={v}' for k, v in sorted(pairs.items()))
    secret = hmac.new(b'WebAppData', token.encode(), hashlib.sha256).digest()
    pairs['hash'] = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
    return urlencode(pairs)


def test_valid_init_data_returns_user(monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', 'test-token')
    user = {'id': 42, 'username': 'ivan', 'first_name': 'Иван'}
    result = validate_init_data(make_init_data('test-token', user))
    assert result['id'] == 42
    assert result['username'] == 'ivan'


def test_tampered_hash_rejected(monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', 'test-token')
    raw = make_init_data('test-token', {'id': 42})
    raw = raw[:-4] + '0000'  # портим hash
    with pytest.raises(HTTPException) as exc:
        validate_init_data(raw)
    assert exc.value.status_code == 401


def test_wrong_token_rejected(monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', 'real-token')
    raw = make_init_data('other-token', {'id': 42})
    with pytest.raises(HTTPException) as exc:
        validate_init_data(raw)
    assert exc.value.status_code == 401


def test_expired_session_rejected(monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', 'test-token')
    raw = make_init_data('test-token', {'id': 42}, age_seconds=90000)  # > 86400
    with pytest.raises(HTTPException) as exc:
        validate_init_data(raw)
    assert exc.value.status_code == 401


def test_missing_hash_rejected(monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', 'test-token')
    with pytest.raises(HTTPException) as exc:
        validate_init_data('auth_date=123&user={}')
    assert exc.value.status_code == 401


def test_empty_init_data_rejected(monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', 'test-token')
    with pytest.raises(HTTPException) as exc:
        validate_init_data('')
    assert exc.value.status_code == 401

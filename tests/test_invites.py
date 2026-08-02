from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from api.index import app
from tests.conftest import patch_db

client = TestClient(app)
DEV_KEY = 'dev-key-test'
USER_ROW = {'id': 1, 'telegram_id': 123456789, 'username': 'developer', 'first_name': 'Developer',
            'last_name': None, 'is_blocked': False}


def auth_headers():
    return {'X-Dev-Api-Key': DEV_KEY}

MEMBER_ROW = {'id': 2, 'workspace_id': 3, 'user_id': 1, 'role': 'admin', 'status': 'active', 'channel_scope': []}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv('DEV_API_KEY', DEV_KEY)
    monkeypatch.setenv('BOT_TOKEN', 'test-token')


def invite_row(**overrides):
    row = {
        'invite_id': 7, 'invite_role': 'editor', 'invite_scope': [1, 2], 'max_uses': None, 'used_count': 0,
        'expires_at': datetime.now(timezone.utc) + timedelta(days=7),
        'workspace_id': 3, 'workspace_name': 'Агентство', 'slug': 'agentstvo-abc',
        'timezone': 'Europe/Moscow', 'currency': 'RUB',
    }
    row.update(overrides)
    return row


def test_create_invite_returns_token(monkeypatch):
    created = {'id': 7, 'role': 'editor', 'channel_scope': [1, 2], 'max_uses': None, 'expires_at': None}
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ROW, created])
    monkeypatch.setattr('api.workspaces.connect', lambda: conn)
    r = client.post('/api/workspaces/3/invites', json={'role': 'editor'}, headers=auth_headers())
    assert r.status_code == 201
    body = r.json()
    assert body['role'] == 'editor'
    assert len(body['token']) >= 20
    assert body['channel_scope'] == [1, 2]


def test_accept_invite_success(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, invite_row(), None,
                                  {'id': 9, 'role': 'editor', 'channel_scope': [1, 2]}])
    monkeypatch.setattr('api.workspaces.connect', lambda: conn)
    r = client.post('/api/invites/accept', json={'token': 'some-secret-token'}, headers=auth_headers())
    assert r.status_code == 200
    body = r.json()
    assert body['workspace_id'] == 3
    assert body['workspace_name'] == 'Агентство'
    assert body['role'] == 'editor'
    assert body['channel_scope'] == [1, 2]
    # приглашение инкрементировано и записан audit log
    calls = [call for cur in conn.cursors for call in cur.calls]
    assert any('used_count=used_count+1' in sql for sql, _ in calls)
    assert any(params and 'member.joined' in params for _, params in calls)


def test_accept_invite_unknown_token(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, None])
    monkeypatch.setattr('api.workspaces.connect', lambda: conn)
    r = client.post('/api/invites/accept', json={'token': 'no-such-token'}, headers=auth_headers())
    assert r.status_code == 404


def test_accept_invite_expired(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, invite_row(expires_at=datetime.now(timezone.utc) - timedelta(days=1))])
    monkeypatch.setattr('api.workspaces.connect', lambda: conn)
    r = client.post('/api/invites/accept', json={'token': 'expired-token'}, headers=auth_headers())
    assert r.status_code == 410


def test_accept_invite_exhausted(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, invite_row(max_uses=2, used_count=2)])
    monkeypatch.setattr('api.workspaces.connect', lambda: conn)
    r = client.post('/api/invites/accept', json={'token': 'used-up-token'}, headers=auth_headers())
    assert r.status_code == 410


def test_accept_invite_already_member(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, invite_row(), {'id': 5, 'status': 'active', 'role': 'viewer'}])
    monkeypatch.setattr('api.workspaces.connect', lambda: conn)
    r = client.post('/api/invites/accept', json={'token': 'member-token'}, headers=auth_headers())
    assert r.status_code == 409

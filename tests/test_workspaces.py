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


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv('DEV_API_KEY', DEV_KEY)
    monkeypatch.setenv('BOT_TOKEN', 'test-token')


def test_health():
    r = client.get('/api/health')
    assert r.status_code == 200
    assert r.json()['ok'] is True


def test_workspaces_requires_auth():
    # Без dev-ключа и без initData -> 401 (dev-key не передан в заголовке)
    r = client.get('/api/workspaces')
    assert r.status_code == 401


def test_create_workspace(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, {'id': 3, 'name': 'Моё агентство', 'slug': 'moe-abc',
                                             'timezone': 'Europe/Moscow', 'currency': 'RUB'}])
    monkeypatch.setattr('api.workspaces.connect', lambda: conn)
    r = client.post('/api/workspaces', json={'name': 'Моё агентство'}, headers=auth_headers())
    assert r.status_code == 201
    body = r.json()
    assert body['name'] == 'Моё агентство'
    assert body['role'] == 'owner'


def test_list_workspaces(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, [{'id': 3, 'name': 'Агентство', 'role': 'owner',
                                              'channel_scope': []}]])
    monkeypatch.setattr('api.workspaces.connect', lambda: conn)
    r = client.get('/api/workspaces', headers=auth_headers())
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]['role'] == 'owner'


def test_members(monkeypatch):
    member_row = {'id': 2, 'workspace_id': 3, 'user_id': 1, 'role': 'admin', 'status': 'active', 'channel_scope': []}
    conn = patch_db(monkeypatch, [USER_ROW, member_row,
                                  [{'id': 1, 'role': 'owner', 'status': 'active',
                                    'channel_scope': [], 'telegram_id': 123456789,
                                    'username': 'dev', 'first_name': 'Dev', 'last_name': None}]])
    monkeypatch.setattr('api.workspaces.connect', lambda: conn)
    r = client.get('/api/workspaces/3/members', headers=auth_headers())
    assert r.status_code == 200
    assert r.json()[0]['role'] == 'owner'


def test_audit_viewer_denied(monkeypatch):
    member = {'id': 2, 'workspace_id': 3, 'user_id': 1, 'role': 'viewer', 'status': 'active', 'channel_scope': []}
    conn = patch_db(monkeypatch, [USER_ROW])
    monkeypatch.setattr('api.workspaces.connect', lambda: conn)
    monkeypatch.setattr('api.permissions.connect', lambda: FakeConnWithMember(member))
    r = client.get('/api/workspaces/3/audit', headers=auth_headers())
    assert r.status_code == 403


class FakeConnWithMember:
    def __init__(self, member):
        self.member = member

    def cursor(self):
        from tests.conftest import FakeCursor
        return FakeCursor([self.member])

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

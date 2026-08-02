import pytest
from fastapi.testclient import TestClient

from api.index import app
from tests.conftest import patch_db

client = TestClient(app)
DEV_KEY = 'dev-key-test'
USER_ROW = {'id': 1, 'telegram_id': 123456789, 'username': 'developer', 'first_name': 'Developer',
            'last_name': None, 'is_blocked': False}
PENDING_ROW = {'id': 4, 'telegram_chat_id': -100123, 'title': 'Тестовый канал', 'username': 'test_channel',
               'bot_permissions': {'can_post_messages': True, 'can_edit_messages': True,
                                   'can_delete_messages': True, 'can_manage_chat': False},
               'observed_at': None}
CHANNEL_ROW = {'id': 11, 'workspace_id': 3, 'telegram_chat_id': -100123, 'title': 'Тестовый канал',
               'username': 'test_channel', 'is_connected': True, 'bot_permissions': {}}


def auth_headers():
    return {'X-Dev-Api-Key': DEV_KEY}

MEMBER_ROW = {'id': 2, 'workspace_id': 3, 'user_id': 1, 'role': 'admin', 'status': 'active', 'channel_scope': []}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv('DEV_API_KEY', DEV_KEY)
    monkeypatch.setenv('BOT_TOKEN', 'test-token')


def test_pending_connections(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, [PENDING_ROW]])
    monkeypatch.setattr('api.channels.connect', lambda: conn)
    r = client.get('/api/channel-connections/pending', headers=auth_headers())
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]['title'] == 'Тестовый канал'


def test_connect_success_with_live_admin(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ROW, PENDING_ROW, None, CHANNEL_ROW])
    monkeypatch.setattr('api.channels.connect', lambda: conn)
    monkeypatch.setattr('api.channels.verify_bot_permissions', lambda chat_id: {
        'is_admin': True, 'can_post_messages': True,
        'permissions': {'can_post_messages': True, 'can_edit_messages': True,
                        'can_delete_messages': True, 'can_manage_chat': False}})
    r = client.post('/api/workspaces/3/channels/connect', json={'connection_id': 4}, headers=auth_headers())
    assert r.status_code == 201
    assert r.json()['id'] == 11


def test_connect_blocked_when_bot_not_admin(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ROW, PENDING_ROW])
    monkeypatch.setattr('api.channels.connect', lambda: conn)
    monkeypatch.setattr('api.channels.verify_bot_permissions', lambda chat_id: {
        'is_admin': False, 'can_post_messages': False, 'permissions': {}})
    r = client.post('/api/workspaces/3/channels/connect', json={'connection_id': 4}, headers=auth_headers())
    assert r.status_code == 422
    assert 'администратором' in r.json()['detail']


def test_connect_blocked_when_no_post_rights_live(monkeypatch):
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ROW, PENDING_ROW])
    monkeypatch.setattr('api.channels.connect', lambda: conn)
    monkeypatch.setattr('api.channels.verify_bot_permissions', lambda chat_id: {
        'is_admin': True, 'can_post_messages': False,
        'permissions': {'can_post_messages': False, 'can_edit_messages': True,
                        'can_delete_messages': True, 'can_manage_chat': False}})
    r = client.post('/api/workspaces/3/channels/connect', json={'connection_id': 4}, headers=auth_headers())
    assert r.status_code == 422


def test_connect_fallback_dev_no_post_rights(monkeypatch):
    row = dict(PENDING_ROW)
    row['bot_permissions'] = {'can_post_messages': False}
    conn = patch_db(monkeypatch, [USER_ROW, MEMBER_ROW, row])
    monkeypatch.setattr('api.channels.connect', lambda: conn)
    monkeypatch.setattr('api.channels.verify_bot_permissions', lambda chat_id: None)
    r = client.post('/api/workspaces/3/channels/connect', json={'connection_id': 4}, headers=auth_headers())
    assert r.status_code == 422
    assert 'публикации' in r.json()['detail']


def test_connect_requires_admin_role(monkeypatch):
    # user с ролью viewer в workspace: membership вернёт row с ролью viewer
    member = {'id': 2, 'workspace_id': 3, 'user_id': 1, 'role': 'viewer', 'status': 'active', 'channel_scope': []}
    conn = patch_db(monkeypatch, [USER_ROW])
    monkeypatch.setattr('api.channels.connect', lambda: conn)
    monkeypatch.setattr('api.permissions.connect', lambda: FakeConnWithMember(member))
    r = client.post('/api/workspaces/3/channels/connect', json={'connection_id': 4}, headers=auth_headers())
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

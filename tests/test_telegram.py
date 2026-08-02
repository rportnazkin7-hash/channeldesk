import pytest

import api.telegram as tg


@pytest.fixture(autouse=True)
def reset_cache():
    tg._bot_id = None
    yield
    tg._bot_id = None


def test_no_token_returns_none(monkeypatch):
    monkeypatch.delenv('BOT_TOKEN', raising=False)
    assert tg.verify_bot_permissions(-100123) is None


def test_admin_with_post_rights(monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', 'test-token')

    def fake(method, params):
        if method == 'getMe':
            return {'ok': True, 'result': {'id': 111}}
        return {'ok': True, 'result': {'status': 'administrator', 'can_post_messages': True,
                                       'can_edit_messages': True, 'can_delete_messages': False,
                                       'can_manage_chat': True}}

    monkeypatch.setattr(tg, '_get_json', fake)
    res = tg.verify_bot_permissions(-100123)
    assert res is not None
    assert res['is_admin'] is True
    assert res['can_post_messages'] is True
    assert res['permissions']['can_delete_messages'] is False


def test_bot_not_in_chat(monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', 'test-token')

    def fake(method, params):
        if method == 'getMe':
            return {'ok': True, 'result': {'id': 111}}
        return {'ok': True, 'result': {'status': 'left'}}

    monkeypatch.setattr(tg, '_get_json', fake)
    res = tg.verify_bot_permissions(-100123)
    assert res['is_admin'] is False
    assert res['can_post_messages'] is False


def test_network_error_returns_none(monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', 'test-token')
    monkeypatch.setattr(tg, '_get_json', lambda method, params: None)
    assert tg.verify_bot_permissions(-100123) is None


def test_bot_id_cached(monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', 'test-token')
    calls = []

    def fake(method, params):
        calls.append(method)
        return {'ok': True, 'result': {'id': 111}}

    monkeypatch.setattr(tg, '_get_json', fake)
    assert tg.get_bot_id() == 111
    assert tg.get_bot_id() == 111
    assert calls.count('getMe') == 1

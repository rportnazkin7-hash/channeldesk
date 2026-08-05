import asyncio
from types import SimpleNamespace

from bot.access import access_state, is_subscribed_member


class FakeBot:
    def __init__(self, member=None, error=None):
        self.member = member
        self.error = error

    async def get_chat_member(self, **_kwargs):
        if self.error:
            raise self.error
        return self.member


def test_member_statuses_are_subscribed():
    assert is_subscribed_member(SimpleNamespace(status='member')) is True
    assert is_subscribed_member(SimpleNamespace(status='administrator')) is True
    assert is_subscribed_member(SimpleNamespace(status='creator')) is True
    assert is_subscribed_member(SimpleNamespace(status='restricted', is_member=True)) is True
    assert is_subscribed_member(SimpleNamespace(status='restricted', is_member=False)) is False
    assert is_subscribed_member(SimpleNamespace(status='left')) is False


def test_unsubscribed_user_is_blocked(monkeypatch):
    monkeypatch.setenv('ADMIN_IDS', '999')
    monkeypatch.setenv('ZBT_ENABLED', 'true')
    state = asyncio.run(access_state(FakeBot(SimpleNamespace(status='left')), 42))
    assert state == {'admin': False, 'subscribed': False, 'allowed': False, 'closed': False}


def test_subscribed_user_sees_zbt(monkeypatch):
    monkeypatch.setenv('ADMIN_IDS', '999')
    monkeypatch.setenv('ZBT_ENABLED', 'true')
    state = asyncio.run(access_state(FakeBot(SimpleNamespace(status='member')), 42))
    assert state == {'admin': False, 'subscribed': True, 'allowed': False, 'closed': True}


def test_admin_bypasses_subscription_and_zbt(monkeypatch):
    monkeypatch.setenv('ADMIN_IDS', '42')
    monkeypatch.setenv('ZBT_ENABLED', 'true')
    state = asyncio.run(access_state(FakeBot(error=RuntimeError('must not check')), 42))
    assert state == {'admin': True, 'subscribed': True, 'allowed': True, 'closed': False}

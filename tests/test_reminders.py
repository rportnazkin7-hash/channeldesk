import pytest

from bot import publisher


class FakeCursor:
    def __init__(self, script):
        self.script = script
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchone(self):
        return self.script.pop(0) if self.script else None

    def fetchall(self):
        return self.script.pop(0) if self.script else []

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeConn:
    def __init__(self, script=None):
        self.script = list(script or [])
        self.cursors = []

    def cursor(self):
        c = FakeCursor(self.script)
        self.cursors.append(c)
        return c

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


TASK = {'id': 1, 'title': 'Подготовить пост', 'description': 'Текст для канала',
        'assignee_id': None, 'due_at': None}
USER = {'id': 5, 'telegram_id': 777777}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', 'test-token')
    monkeypatch.setenv('ADMIN_IDS', '111,222')


def test_send_task_reminders(monkeypatch):
    sent = []

    def fake_telegram(token, method, params):
        sent.append(params['chat_id'])
        return {'ok': True, 'result': {}}

    conn = FakeConn([[TASK], TASK, USER])
    monkeypatch.setattr('bot.publisher._telegram_request', fake_telegram)

    count = publisher._send_task_reminders('test-token', conn)

    assert count >= 2  # админам 111 и 222 + назначенному (777777 входит как assignee)
    assert 111 in sent and 222 in sent
    # пометка reminded=true
    sql = ' '.join(call[0] for cur in conn.cursors for call in cur.calls)
    assert 'reminded=true' in sql


def test_send_task_reminders_no_tasks(monkeypatch):
    sent = []

    def fake_telegram(token, method, params):
        sent.append(params)
        return {'ok': True, 'result': {}}

    conn = FakeConn([[]])
    monkeypatch.setattr('bot.publisher._telegram_request', fake_telegram)
    count = publisher._send_task_reminders('test-token', conn)
    assert count == 0
    assert sent == []

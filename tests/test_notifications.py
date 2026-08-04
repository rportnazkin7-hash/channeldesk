from bot import publisher


class FakeCursor:
    def __init__(self, script):
        self.script = list(script)
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
    def __init__(self, script):
        self.script = script

    def cursor(self):
        return FakeCursor(self.script)


def test_notify_booking_transition(monkeypatch):
    sent = []
    monkeypatch.setattr('bot.publisher._telegram_request', lambda token, method, params: sent.append((method, params)) or {'ok': True})
    conn = FakeConn([
        {'id': 5, 'status': 'overdue', 'publish_at': None, 'advertiser_name': 'Реклама', 'channel_title': 'Новости'},
        [{'telegram_id': 123}],
    ])
    publisher._notify_booking_transition('token', conn, {'id': 5, 'workspace_id': 3, 'status': 'overdue'})
    assert sent[0][0] == 'sendMessage'
    assert sent[0][1]['chat_id'] == 123
    assert 'просрочено' in sent[0][1]['text']

from bot import publisher


class FakeCursor:
    def __init__(self, script):
        self.script = list(script)
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def fetchall(self):
        return self.script.pop(0) if self.script else []

    def fetchone(self):
        return self.script.pop(0) if self.script else None

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


class FakeConn:
    def __init__(self, script):
        self.script = script
        self.cursors = []

    def cursor(self):
        cur = FakeCursor(self.script)
        self.cursors.append(cur)
        return cur


JOB = {'id': 7, 'workspace_id': 3, 'post_id': 17, 'telegram_chat_id': -100123, 'telegram_message_id': 555}


def test_process_delete_job(monkeypatch):
    sent = []
    monkeypatch.setattr('bot.publisher._telegram_request', lambda token, method, params: sent.append((method, params)) or {'ok': True})
    conn = FakeConn([[JOB], JOB])
    assert publisher._process_delete_jobs('token', conn) == 1
    assert sent == [('deleteMessage', {'chat_id': -100123, 'message_id': 555})]
    sql = ' '.join(call[0] for cur in conn.cursors for call in cur.calls)
    assert "status='done'" in sql
    assert "status='cancelled'" in sql

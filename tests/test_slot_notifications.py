from datetime import datetime, timezone

from bot import slot_notifications


class FakeCursor:
    def __init__(self, script): self.script = script; self.calls = []
    def execute(self, sql, params=None): self.calls.append((sql, params))
    def fetchall(self): return self.script.pop(0) if self.script else []
    def __enter__(self): return self
    def __exit__(self, *args): return False


class FakeConn:
    def __init__(self, script): self.script = script; self.cursors = []
    def cursor(self):
        cur = FakeCursor(self.script); self.cursors.append(cur); return cur


def test_render_slot_request():
    text = slot_notifications._render({
        'id': 4, 'channel_title': 'Новости', 'contact_name': 'Реклама',
        'publish_at': datetime(2026, 8, 10, 12, tzinfo=timezone.utc),
        'delete_at': datetime(2026, 8, 12, 12, tzinfo=timezone.utc),
        'cost': 15000, 'currency': 'RUB', 'contact_telegram': '@client',
        'target_url': 'https://example.com', 'comment': 'Нужен пост',
    })
    assert 'Новая заявка' in text
    assert '@client' in text
    assert '15 000' in text or '15000' in text


def test_send_slot_request_notification(monkeypatch):
    sent = []
    monkeypatch.setenv('BOT_TOKEN', 'bot')
    request = {'id': 4, 'workspace_id': 3, 'contact_name': 'Реклама', 'contact_telegram': '@client',
               'contact_email': '', 'target_url': '', 'comment': '', 'publish_at': None, 'delete_at': None,
               'cost': 1000, 'currency': 'RUB', 'format': 'post', 'channel_title': 'Новости'}
    conn = FakeConn([[request], [{'telegram_id': 123}]])
    result = slot_notifications.send_slot_request_notifications(conn, lambda token, method, params: sent.append(params) or {'ok': True})
    assert result == 1
    assert sent[0]['chat_id'] == 123
    sql = ' '.join(call[0] for cur in conn.cursors for call in cur.calls)
    assert 'notified_at=now()' in sql

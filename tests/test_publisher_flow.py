"""End-to-end тест publisher: полный цикл claim -> sendMessage -> запись результата.

Регрессия: run_once был async def, но вызывался через asyncio.to_thread —
тело корутины никогда не выполнялось, посты вечно висели в scheduled без ошибок.
"""
import asyncio
import json

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
        self.committed = False
        self.closed = False

    def cursor(self):
        c = FakeCursor(self.script)
        self.cursors.append(c)
        return c

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


CANDIDATE = {'id': 1, 'workspace_id': 3, 'channel_id': 5, 'text': 'hello <b>world</b>',
             'buttons': [[{'text': 'Открыть', 'url': 'https://x.ru'}]],
             'publish_key': 'key123', 'attempt_count': 0, 'telegram_message_id': None}
CLAIMED = dict(CANDIDATE)
CHANNEL = {'id': 5, 'telegram_chat_id': -100123, 'title': 'Тестовый канал'}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', 'test-token')
    monkeypatch.setenv('DATABASE_URL', 'postgresql://u:p@localhost/db')
    monkeypatch.setenv('ADMIN_IDS', '1,2')


def test_run_once_must_be_sync():
    """Прямая регрессия: run_once не должен быть корутиной (иначе to_thread её не выполнит)."""
    assert not asyncio.iscoroutinefunction(publisher.run_once)


def test_full_publish_cycle(monkeypatch):
    sent = []

    def fake_telegram(token, method, params):
        sent.append((method, params))
        return {'ok': True, 'result': {'message_id': 777}}

    conn = FakeConn([  # _claim_posts: SELECT -> список, UPDATE RETURNING -> claimed
        [CANDIDATE], CLAIMED,
        # _load_channel: SELECT -> канал
        CHANNEL,
    ])
    monkeypatch.setattr('bot.publisher.psycopg.connect', lambda *a, **k: conn)
    monkeypatch.setattr('bot.publisher._telegram_request', fake_telegram)

    # вызываем так же, как loop(): asyncio.to_thread(run_once)
    published = asyncio.run(asyncio.to_thread(publisher.run_once))

    assert published == 1
    assert len(sent) == 1
    method, params = sent[0]
    assert method == 'sendMessage'
    assert params['chat_id'] == -100123
    assert params['text'] == 'hello <b>world</b>'
    assert params['parse_mode'] == 'HTML'
    # inline-кнопки передаются как JSON reply_markup
    import json as _json
    assert params['reply_markup'] == _json.dumps({'inline_keyboard': [[{'text': 'Открыть', 'url': 'https://x.ru'}]]})

    # записан успех: статус published + журнал попытки
    sql = ' '.join(call[0] for cur in conn.cursors for call in cur.calls)
    assert "status='published'" in sql
    assert 'telegram_message_id=%s' in sql
    assert 'cd_publish_attempts' in sql
    assert conn.committed is True
    assert conn.closed is True


def test_publish_cycle_without_candidates(monkeypatch):
    conn = FakeConn([[]])
    monkeypatch.setattr('bot.publisher.psycopg.connect', lambda *a, **k: conn)
    published = publisher.run_once()
    assert published == 0
    assert conn.committed is True


def test_final_error_records_and_notifies(monkeypatch):
    notified = []

    def fake_telegram(token, method, params):
        if method == 'sendMessage':
            raise RuntimeError('HTTP 400: cannot parse entities')
        return {'ok': True, 'result': {}}

    def fake_notify(token, post_id, title, error_text):
        notified.append((post_id, error_text))

    conn = FakeConn([[CANDIDATE], CLAIMED, CHANNEL])
    monkeypatch.setattr('bot.publisher.psycopg.connect', lambda *a, **k: conn)
    monkeypatch.setattr('bot.publisher._telegram_request', fake_telegram)
    monkeypatch.setattr('bot.publisher._notify_owner', fake_notify)

    published = publisher.run_once()
    assert published == 1  # пост обработан (с ошибкой, но цикл завершился)
    sql = ' '.join(call[0] for cur in conn.cursors for call in cur.calls)
    assert "status='failed'" in sql
    assert 'cd_publish_attempts' in sql
    assert len(notified) == 1
    assert 'HTTP 400' in notified[0][1]


def test_publish_with_single_photo(monkeypatch):
    sent = []

    def fake_telegram(token, method, params):
        sent.append((method, params))
        return {'ok': True, 'result': {'message_id': 888}}

    asset = {'id': 1, 'file_name': 'pic.png', 'file_type': 'image/png',
             'file_url': 'https://x.supabase.co/storage/v1/object/public/channeldesk-assets/3/abc.png',
             'size_bytes': 1000}
    conn = FakeConn([[CANDIDATE], CLAIMED, CHANNEL, [asset]])
    monkeypatch.setattr('bot.publisher.psycopg.connect', lambda *a, **k: conn)
    monkeypatch.setattr('bot.publisher._telegram_request', fake_telegram)

    publisher.run_once()
    assert len(sent) == 1
    method, params = sent[0]
    assert method == 'sendPhoto'
    assert params['photo'] == asset['file_url']
    assert params['caption'] == 'hello <b>world</b>'
    assert 'reply_markup' in params  # кнопки при одиночном медиа


def test_publish_with_media_group(monkeypatch):
    sent = []

    def fake_telegram(token, method, params):
        sent.append((method, params))
        return {'ok': True, 'result': [{'message_id': 1}, {'message_id': 2}]}

    assets = [
        {'id': 1, 'file_name': 'a.png', 'file_type': 'image/png', 'file_url': 'https://x/a.png', 'size_bytes': 1},
        {'id': 2, 'file_name': 'b.mp4', 'file_type': 'video/mp4', 'file_url': 'https://x/b.mp4', 'size_bytes': 1},
        {'id': 3, 'file_name': 'c.pdf', 'file_type': 'application/pdf', 'file_url': 'https://x/c.pdf', 'size_bytes': 1},
    ]
    conn = FakeConn([[CANDIDATE], CLAIMED, CHANNEL, assets])
    monkeypatch.setattr('bot.publisher.psycopg.connect', lambda *a, **k: conn)
    monkeypatch.setattr('bot.publisher._telegram_request', fake_telegram)

    publisher.run_once()
    assert len(sent) == 1
    method, params = sent[0]
    assert method == 'sendMediaGroup'
    media = json.loads(params['media'])
    assert [m['type'] for m in media] == ['photo', 'video', 'document']
    assert media[0]['caption'] == 'hello <b>world</b>'  # caption только на первом
    assert 'caption' not in media[1]

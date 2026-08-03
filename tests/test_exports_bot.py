import pytest

from bot import exports


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


POST_ROW = {'id': 1, 'title': 'Пост', 'text': 'текст', 'status': 'published', 'scheduled_at': None,
            'published_at': None, 'last_error': None, 'channel_title': 'Канал'}
JOB = {'id': 1, 'workspace_id': 3, 'telegram_id': 777, 'kind': 'posts', 'format': 'csv'}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', 'test-token')


def test_generate_csv_bytes():
    data, filename, mime = exports._generate_file(FakeConn([[POST_ROW]]), 'posts', 'csv', 3)
    assert filename == 'posts.csv'
    assert 'Пост' in data.decode('utf-8')
    assert mime.startswith('text/csv')


def test_generate_xlsx_bytes():
    data, filename, mime = exports._generate_file(FakeConn([[POST_ROW]]), 'posts', 'xlsx', 3)
    assert filename == 'posts.xlsx'
    assert data[:2] == b'PK'  # zip-магия xlsx
    assert 'spreadsheetml' in mime


def test_generate_pdf_bytes():
    data, filename, mime = exports._generate_file(FakeConn([[POST_ROW]]), 'posts', 'pdf', 3)
    assert filename == 'posts.pdf'
    assert data[:4] == b'%PDF'
    assert mime == 'application/pdf'


def test_process_pending_exports_sends_document(monkeypatch):
    sent = []

    def fake_send_document(token, chat_id, filename, data, caption):
        sent.append((chat_id, filename, data))

    monkeypatch.setattr('bot.exports._send_document', fake_send_document)
    # порядок: claim fetchone -> JOB; _load_rows fetchall -> [POST_ROW]; второй claim fetchone -> None
    conn = FakeConn([JOB, [POST_ROW], None])
    count = exports.process_pending_exports('test-token', conn)
    assert count == 1
    assert sent[0][0] == 777
    assert sent[0][1] == 'posts.csv'
    assert 'Пост' in sent[0][2].decode('utf-8')
    # помечен done
    sql = ' '.join(call[0] for cur in conn.cursors for call in cur.calls)
    assert "status='done'" in sql


def test_send_document_multipart(monkeypatch):
    """Проверяем, что _send_document шлёт multipart с файлом и получает ok."""
    received = {}

    class FakeResp:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self):
            return b'{"ok": true, "result": {"message_id": 1}}'

    def fake_urlopen(req, timeout):
        received['url'] = req.full_url
        received['content_type'] = req.headers['Content-type']
        received['body'] = req.data
        return FakeResp()

    monkeypatch.setattr('bot.exports.urlopen', fake_urlopen)
    exports._send_document('TOKEN', 777, 'posts.csv', b'\xef\xbb\xbfID;', 'caption')
    assert received['url'].startswith('https://api.telegram.org/botTOKEN/sendDocument')
    assert 'multipart/form-data; boundary=' in received['content_type']
    assert b'posts.csv' in received['body']
    assert b'ID;' in received['body']

import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1]))


class FakeCursor:
    """Примитивный курсор: execute записывает вызов, fetch* берёт из общего скрипта."""

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
    """Фейковое соединение psycopg: курсоры делят общий скрипт результатов."""

    def __init__(self, script=None):
        self.script = list(script or [])
        self.committed = False
        self.cursors = []

    def cursor(self):
        cursor = FakeCursor(self.script)
        self.cursors.append(cursor)
        return cursor

    def commit(self):
        self.committed = True

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def patch_db(monkeypatch, script):
    """Подменяет connect во всех модулях API одним FakeConn, чтобы скрипт выполнялся последовательно."""
    conn = FakeConn(script)
    monkeypatch.setattr('api.auth.connect', lambda: conn)
    monkeypatch.setattr('api.permissions.connect', lambda: conn)
    return conn

import pytest

from bot import publisher


class FakeCur:
    def __init__(self):
        self.calls = []

    def execute(self, sql, params=None):
        self.calls.append((sql, params))

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeConn:
    def __init__(self):
        self.cursors = []

    def cursor(self):
        c = FakeCur()
        self.cursors.append(c)
        return c


def test_lifecycle_transitions(monkeypatch):
    monkeypatch.setenv('BOT_TOKEN', 't')
    conn = FakeConn()
    publisher._update_booking_statuses(conn)
    sqls = [c[0] for cur in conn.cursors for c in cur.calls]
    assert any("status='active'" in s and "payment_status IN ('paid','partially_paid')" in s for s in sqls)
    assert any("status='overdue'" in s and "payment_status='unpaid'" in s for s in sqls)
    assert any("status='done'" in s and "delete_at" in s for s in sqls)
    assert any("status='cancelled'" in s and "status='overdue'" in s for s in sqls)

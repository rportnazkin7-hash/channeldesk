from datetime import datetime, timezone
from types import SimpleNamespace

from bot import mtproto_analytics


def test_snapshot_maps_broadcast_stats():
    period = SimpleNamespace(
        min_date=int(datetime(2026, 8, 1, tzinfo=timezone.utc).timestamp()),
        max_date=int(datetime(2026, 8, 3, tzinfo=timezone.utc).timestamp()),
    )
    stats = SimpleNamespace(
        period=period,
        followers=SimpleNamespace(current=15000, previous=14900),
        views_per_post=SimpleNamespace(current=4200.5, previous=4100),
        shares_per_post=SimpleNamespace(current=12.4, previous=11),
        reactions_per_post=SimpleNamespace(current=88.2, previous=80),
        views_per_story=None,
        shares_per_story=None,
        reactions_per_story=None,
        enabled_notifications=SimpleNamespace(current=35.5, previous=34),
    )
    row = mtproto_analytics._snapshot(stats)
    assert row['period_start'].isoformat() == '2026-08-01'
    assert row['period_end'].isoformat() == '2026-08-03'
    assert row['followers_current'] == 15000
    assert row['followers_previous'] == 14900
    assert row['views_per_post'] == 4200.5
    assert row['reactions_per_post'] == 88.2


def test_sync_is_safe_noop_without_session(monkeypatch):
    for name in ('MT_PROTO_API_ID', 'MT_PROTO_API_HASH', 'MT_PROTO_SESSION_STRING'):
        monkeypatch.delenv(name, raising=False)
    result = mtproto_analytics.run_sync_if_due(force=True)
    assert result == {'enabled': False, 'ran': False, 'ok': 0, 'errors': []}

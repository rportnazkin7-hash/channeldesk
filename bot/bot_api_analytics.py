from __future__ import annotations

"""Автоматический сбор доступных метрик через Telegram Bot API.

Bot API не отдаёт полную статистику просмотров канала. Поэтому здесь храним
только то, что Telegram присылает/разрешает получить боту: число подписчиков,
новые channel_post и счётчики анонимных реакций.
"""

import json
import logging
import os
import time
from datetime import date, datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import psycopg

from bot.db import db_url

logger = logging.getLogger('channeldesk.bot_api_analytics')
TELEGRAM_API = 'https://api.telegram.org'
DEFAULT_MEMBER_SYNC_INTERVAL = 6 * 60 * 60
LAST_MEMBER_SYNC_AT = 0.0


def _telegram_request(token: str, method: str, params: dict) -> dict:
    query = urlencode({str(key): str(value) for key, value in params.items()})
    try:
        with urlopen(Request(f'{TELEGRAM_API}/bot{token}/{method}?{query}'), timeout=15) as response:
            payload = json.loads(response.read().decode('utf-8'))
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f'Telegram API: {exc}') from exc
    if not payload.get('ok'):
        raise RuntimeError(f"Telegram API: {payload.get('description', 'unknown error')}")
    return payload


def _interval() -> int:
    try:
        return max(900, int(os.getenv('BOT_ANALYTICS_SYNC_INTERVAL', str(DEFAULT_MEMBER_SYNC_INTERVAL))))
    except ValueError:
        return DEFAULT_MEMBER_SYNC_INTERVAL


def _metric_date(value: datetime | None = None) -> date:
    current = value or datetime.now(timezone.utc)
    if current.tzinfo is None:
        current = current.replace(tzinfo=timezone.utc)
    return current.astimezone(timezone.utc).date()


def _reaction_total(reactions) -> int:
    return sum(int(getattr(item, 'total_count', 0) or 0) for item in (reactions or []))


def _upsert_daily(cur, workspace_id: int, channel_id: int, metric_date: date,
                  subscribers: int | None = None, reactions: int | None = None,
                  posts_count: int | None = None) -> None:
    cur.execute("""SELECT COALESCE(SUM(reactions_count),0) AS reactions,
    COUNT(*) AS posts FROM cd_channel_post_metrics
    WHERE workspace_id=%s AND channel_id=%s AND published_at::date=%s""",
                (workspace_id, channel_id, metric_date))
    totals = cur.fetchone() or {'reactions': 0, 'posts': 0}
    reactions_value = int(reactions if reactions is not None else totals.get('reactions') or 0)
    posts_value = int(posts_count if posts_count is not None else totals.get('posts') or 0)
    if subscribers is None:
        cur.execute("""INSERT INTO cd_channel_metrics(
            workspace_id,channel_id,metric_date,reactions,posts_count,source,notes)
        VALUES(%s,%s,%s,%s,%s,'bot_api','Сбор Bot API')
        ON CONFLICT(workspace_id,channel_id,metric_date) DO UPDATE SET
            reactions=excluded.reactions,posts_count=excluded.posts_count,
            source='bot_api',notes=excluded.notes,updated_at=now()""",
                    (workspace_id, channel_id, metric_date, reactions_value, posts_value))
    else:
        cur.execute("""INSERT INTO cd_channel_metrics(
            workspace_id,channel_id,metric_date,subscribers,reactions,posts_count,source,notes)
        VALUES(%s,%s,%s,%s,%s,%s,'bot_api','Сбор Bot API')
        ON CONFLICT(workspace_id,channel_id,metric_date) DO UPDATE SET
            subscribers=excluded.subscribers,reactions=excluded.reactions,
            posts_count=excluded.posts_count,source='bot_api',notes=excluded.notes,updated_at=now()""",
                    (workspace_id, channel_id, metric_date, subscribers, reactions_value, posts_value))


def save_channel_post(message) -> None:
    """Сохраняет новый/изменённый channel_post, который прислал Bot API."""
    with psycopg.connect(db_url(), row_factory=psycopg.rows.dict_row) as conn, conn.cursor() as cur:
        cur.execute("""SELECT id,workspace_id FROM cd_channels
        WHERE telegram_chat_id=%s AND is_active=true""", (message.chat.id,))
        channel = cur.fetchone()
        if not channel:
            return
        published_at = getattr(message, 'date', None)
        reactions = _reaction_total(getattr(getattr(message, 'reactions', None), 'reactions', None))
        raw = {'message_id': message.message_id, 'chat_id': message.chat.id,
               'has_protected_content': bool(getattr(message, 'has_protected_content', False))}
        cur.execute("""INSERT INTO cd_channel_post_metrics(
            workspace_id,channel_id,telegram_message_id,published_at,reactions_count,raw)
        VALUES(%s,%s,%s,%s,%s,%s::jsonb)
        ON CONFLICT(channel_id,telegram_message_id) DO UPDATE SET
            published_at=COALESCE(excluded.published_at,cd_channel_post_metrics.published_at),
            reactions_count=GREATEST(cd_channel_post_metrics.reactions_count,excluded.reactions_count),
            captured_at=now(),raw=excluded.raw""",
                    (channel['workspace_id'], channel['id'], message.message_id, published_at,
                     reactions, json.dumps(raw)))
        _upsert_daily(cur, channel['workspace_id'], channel['id'], _metric_date(published_at))
        conn.commit()


def save_reaction_update(update) -> None:
    """Обновляет количество анонимных реакций на channel_post."""
    with psycopg.connect(db_url(), row_factory=psycopg.rows.dict_row) as conn, conn.cursor() as cur:
        cur.execute("""SELECT id,workspace_id FROM cd_channels
        WHERE telegram_chat_id=%s AND is_active=true""", (update.chat.id,))
        channel = cur.fetchone()
        if not channel:
            return
        total = _reaction_total(update.reactions)
        cur.execute("""UPDATE cd_channel_post_metrics SET reactions_count=%s,captured_at=now()
        WHERE channel_id=%s AND telegram_message_id=%s""", (total, channel['id'], update.message_id))
        if cur.rowcount == 0:
            cur.execute("""INSERT INTO cd_channel_post_metrics(
                workspace_id,channel_id,telegram_message_id,reactions_count,raw)
            VALUES(%s,%s,%s,%s,%s::jsonb)
            ON CONFLICT(channel_id,telegram_message_id) DO UPDATE SET reactions_count=excluded.reactions_count,captured_at=now()""",
                        (channel['workspace_id'], channel['id'], update.message_id, total, '{}'))
        _upsert_daily(cur, channel['workspace_id'], channel['id'], date.today())
        conn.commit()


def sync_member_counts(token: str, conn) -> dict:
    """Раз в несколько часов получает число подписчиков через getChatMemberCount."""
    global LAST_MEMBER_SYNC_AT
    now = time.time()
    if LAST_MEMBER_SYNC_AT and now - LAST_MEMBER_SYNC_AT < _interval():
        return {'ran': False, 'ok': 0, 'errors': []}
    LAST_MEMBER_SYNC_AT = now
    with conn.cursor() as cur:
        cur.execute("""SELECT id,workspace_id,telegram_chat_id FROM cd_channels
        WHERE is_active=true ORDER BY workspace_id,id""")
        channels = cur.fetchall() or []
    ok = 0
    errors: list[str] = []
    for channel in channels:
        try:
            payload = _telegram_request(token, 'getChatMemberCount', {'chat_id': channel['telegram_chat_id']})
            with conn.cursor() as cur:
                _upsert_daily(cur, channel['workspace_id'], channel['id'], date.today(),
                              subscribers=int(payload['result']))
            ok += 1
        except Exception as exc:  # noqa: BLE001
            message = f"channel {channel['id']}: {str(exc)[:180]}"
            errors.append(message)
            logger.warning('Bot API analytics failed: %s', message)
    return {'ran': True, 'ok': ok, 'errors': errors}

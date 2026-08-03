from __future__ import annotations

"""Сбор расширенной статистики каналов через Telegram MTProto.

Работает только для каналов, где пользовательская Telegram-сессия может
просматривать статистику. Bot API и BOT_TOKEN для этого не используются.
Синхронизация вызывается из publisher-цикла, но выполняется не чаще интервала.
"""

import asyncio
import json
import logging
import os
import time
from datetime import date, datetime, timezone
from typing import Any

import psycopg

from bot.db import db_url

logger = logging.getLogger('channeldesk.mtproto_analytics')
DEFAULT_INTERVAL = 6 * 60 * 60
LAST_SYNC_AT = 0.0
LAST_SYNC_OK = 0
LAST_SYNC_ERRORS: list[str] = []


def _config() -> tuple[int, str, str] | None:
    raw_id = os.getenv('MT_PROTO_API_ID', '').strip()
    api_hash = os.getenv('MT_PROTO_API_HASH', '').strip()
    session = os.getenv('MT_PROTO_SESSION_STRING', '').strip()
    if not raw_id or not api_hash or not session:
        return None
    try:
        return int(raw_id), api_hash, session
    except ValueError:
        logger.error('MT_PROTO_API_ID must be an integer')
        return None


def _interval() -> int:
    try:
        return max(900, int(os.getenv('MT_PROTO_SYNC_INTERVAL', str(DEFAULT_INTERVAL))))
    except ValueError:
        return DEFAULT_INTERVAL


def _number(value: Any) -> float:
    try:
        return float(getattr(value, 'current', value) or 0)
    except (TypeError, ValueError):
        return 0.0


def _epoch_date(value: Any) -> date | None:
    try:
        if value is None:
            return None
        return datetime.fromtimestamp(int(value), timezone.utc).date()
    except (TypeError, ValueError, OSError):
        return None


def _jsonable(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    to_dict = getattr(value, 'to_dict', None)
    if callable(to_dict):
        try:
            return _jsonable(to_dict())
        except Exception:  # noqa: BLE001
            pass
    return str(value)


def _snapshot(stats: Any) -> dict[str, Any]:
    period = getattr(stats, 'period', None)
    followers_obj = getattr(stats, 'followers', None)
    followers = _number(followers_obj)
    followers_previous = float(getattr(followers_obj, 'previous', 0) or 0)
    return {
        'period_start': _epoch_date(getattr(period, 'min_date', None)),
        'period_end': _epoch_date(getattr(period, 'max_date', None)),
        'followers_current': int(round(followers)),
        'followers_previous': int(round(followers_previous)),
        'views_per_post': _number(getattr(stats, 'views_per_post', None)),
        'shares_per_post': _number(getattr(stats, 'shares_per_post', None)),
        'reactions_per_post': _number(getattr(stats, 'reactions_per_post', None)),
        'views_per_story': _number(getattr(stats, 'views_per_story', None)),
        'shares_per_story': _number(getattr(stats, 'shares_per_story', None)),
        'reactions_per_story': _number(getattr(stats, 'reactions_per_story', None)),
        'enabled_notifications': _number(getattr(stats, 'enabled_notifications', None)),
        'raw': _jsonable(stats),
    }


async def _collect(channels: list[dict], api_id: int, api_hash: str, session: str) -> tuple[list[dict], list[str]]:
    try:
        from telethon import TelegramClient
        from telethon.sessions import StringSession
        from telethon.tl.functions.channels import GetFullChannelRequest
        from telethon.tl.functions.stats import GetBroadcastStatsRequest
    except ImportError as exc:
        return [], [f'Telethon не установлен: {exc}']

    client = TelegramClient(StringSession(session), api_id, api_hash)
    snapshots: list[dict] = []
    errors: list[str] = []
    await client.connect()
    try:
        if not await client.is_user_authorized():
            return [], ['MT_PROTO_SESSION_STRING не авторизован']
        for channel in channels:
            username = (channel.get('username') or '').strip()
            if not username:
                errors.append(f"{channel.get('title') or channel['id']}: нет username")
                continue
            if not username.startswith('@'):
                username = '@' + username
            try:
                entity = await client.get_entity(username)
                full = await client(GetFullChannelRequest(entity))
                if not getattr(full.full_chat, 'can_view_stats', False):
                    raise RuntimeError('Telegram не разрешил просмотр статистики для этой сессии')
                stats = await client(GetBroadcastStatsRequest(entity))
                snapshots.append({**channel, **_snapshot(stats)})
            except Exception as exc:  # noqa: BLE001
                message = f"{channel.get('title') or channel['id']}: {str(exc)[:240]}"
                errors.append(message)
                logger.warning('MTProto stats failed: %s', message)
    finally:
        await client.disconnect()
    return snapshots, errors


def _load_channels() -> list[dict]:
    with psycopg.connect(db_url(), row_factory=psycopg.rows.dict_row) as conn, conn.cursor() as cur:
        cur.execute("""SELECT id,workspace_id,telegram_chat_id,title,username
        FROM cd_channels WHERE is_active=true ORDER BY workspace_id,id""")
        return cur.fetchall() or []


def _store_snapshots(snapshots: list[dict]) -> None:
    if not snapshots:
        return
    with psycopg.connect(db_url(), row_factory=psycopg.rows.dict_row) as conn, conn.cursor() as cur:
        for item in snapshots:
            period_end = item.get('period_end') or date.today()
            cur.execute("""INSERT INTO cd_channel_stats_snapshots(
                workspace_id,channel_id,period_start,period_end,followers_current,followers_previous,
                views_per_post,shares_per_post,reactions_per_post,views_per_story,shares_per_story,
                reactions_per_story,enabled_notifications,raw)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s::jsonb)""",
                        (item['workspace_id'], item['id'], item.get('period_start'), period_end,
                         item['followers_current'], item['followers_previous'], item['views_per_post'],
                         item['shares_per_post'], item['reactions_per_post'], item['views_per_story'],
                         item['shares_per_story'], item['reactions_per_story'],
                         item['enabled_notifications'], json.dumps(item['raw'], ensure_ascii=False)))
            # Каноническая дневная строка аналитики: MTProto-метрики заменяют
            # ручные нули за тот же день и помечаются источником.
            cur.execute("""INSERT INTO cd_channel_metrics(
                workspace_id,channel_id,metric_date,subscribers,views,reach,reactions,forwards,source,notes)
            VALUES(%s,%s,%s,%s,%s,%s,%s,%s,'mtproto',%s)
            ON CONFLICT(workspace_id,channel_id,metric_date) DO UPDATE SET
                subscribers=excluded.subscribers,views=excluded.views,reach=excluded.reach,
                reactions=excluded.reactions,forwards=excluded.forwards,source='mtproto',
                notes=excluded.notes,updated_at=now()""",
                        (item['workspace_id'], item['id'], period_end, item['followers_current'],
                         int(round(item['views_per_post'])), int(round(item['views_per_post'])),
                         int(round(item['reactions_per_post'])), int(round(item['shares_per_post'])),
                         'Синхронизация Telegram MTProto'))
        conn.commit()


def run_sync_if_due(force: bool = False) -> dict[str, Any]:
    """Синхронизирует каналы не чаще заданного интервала.

    Возвращает диагностический словарь; отсутствие настроек — штатный no-op,
    чтобы обычный publisher продолжал работать без MTProto.
    """
    global LAST_SYNC_AT, LAST_SYNC_OK, LAST_SYNC_ERRORS
    config = _config()
    if config is None:
        return {'enabled': False, 'ran': False, 'ok': 0, 'errors': []}
    now = time.time()
    if not force and LAST_SYNC_AT and now - LAST_SYNC_AT < _interval():
        return {'enabled': True, 'ran': False, 'ok': LAST_SYNC_OK, 'errors': LAST_SYNC_ERRORS}
    LAST_SYNC_AT = now
    try:
        channels = _load_channels()
        if not channels:
            LAST_SYNC_OK, LAST_SYNC_ERRORS = 0, []
            return {'enabled': True, 'ran': True, 'ok': 0, 'errors': []}
        snapshots, errors = asyncio.run(_collect(channels, *config))
        _store_snapshots(snapshots)
        LAST_SYNC_OK, LAST_SYNC_ERRORS = len(snapshots), errors
        return {'enabled': True, 'ran': True, 'ok': len(snapshots), 'errors': errors}
    except Exception as exc:  # noqa: BLE001
        message = str(exc)[:300]
        LAST_SYNC_ERRORS = [message]
        logger.exception('MTProto analytics sync failed')
        return {'enabled': True, 'ran': True, 'ok': 0, 'errors': [message]}

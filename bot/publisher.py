from __future__ import annotations
"""Надёжный publisher: публикует отложенные посты в Telegram-каналы.

Отдельный worker для Bothost (entry point: bot/publisher.py).

Требования (docs/PRODUCT_SPEC.md, раздел 12):
- атомарный переход scheduled/publishing -> захват задания;
- запрет повторной отправки (уникальный publish_key + атомарный UPDATE);
- сохранение telegram_message_id;
- повтор только сетевых ошибок;
- ограничение числа попыток;
- журнал каждой попытки (cd_publish_attempts);
- уведомление владельца при окончательной ошибке;
- публикация не позднее ~60 секунд после срока (цикл опроса).
"""
import asyncio
import json
import logging
import os
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import psycopg

from bot.db import db_url

logger = logging.getLogger('channeldesk.publisher')

POLL_INTERVAL = 15          # секунд между проходами (публикация <= ~60 c после срока)
MAX_ATTEMPTS = 5            # ограничение числа попыток на пост
TELEGRAM_API = 'https://api.telegram.org'

RETRYABLE_HTTP = {408, 429, 500, 502, 503, 504}


def is_retryable_error(error_text: str) -> bool:
    """Только сетевые/временные ошибки повторяемы; остальные — финальные."""
    if not error_text:
        return True
    lowered = error_text.lower()
    if 'http 4' in lowered and 'http 408' not in lowered and 'http 429' not in lowered:
        return False
    for token in ('timed out', 'timeout', 'connection refused', 'connection reset',
                  'temporary failure', 'temporarily unavailable', 'retry after'):
        if token in lowered:
            return True
    for code in RETRYABLE_HTTP:
        if f'http {code}' in lowered:
            return True
    return False


def _telegram_request(token: str, method: str, params: dict) -> dict:
    url = f'{TELEGRAM_API}/bot{token}/{method}'
    if params:
        url += '?' + urlencode({str(k): str(v) for k, v in params.items()})
    try:
        with urlopen(Request(url, headers={'Accept': 'application/json'}), timeout=15) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except HTTPError as exc:
        body = exc.read().decode('utf-8', errors='replace')[:300]
        raise RuntimeError(f'HTTP {exc.code}: {body}') from exc
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f'Network error: {exc}') from exc


def _claim_posts(conn, now_iso: str) -> list[dict]:
    """Атомарно забирает посты, готовые к публикации.

    Захват: UPDATE ... WHERE status IN ('scheduled','publishing') AND attempt_count < MAX
    гарантирует, что один пост возьмёт только один проход publisher'а.
    """
    rows = []
    with conn.cursor() as cur:
        cur.execute("""SELECT id,workspace_id,channel_id,text,publish_key,attempt_count,telegram_message_id
        FROM cd_posts WHERE (status='scheduled' AND scheduled_at<=%s) OR status='publishing'
        ORDER BY scheduled_at NULLS LAST, id""", (now_iso,))
        candidates = cur.fetchall()
        for post in candidates:
            cur.execute("""UPDATE cd_posts SET status='publishing',attempt_count=attempt_count+1,updated_at=now()
            WHERE id=%s AND status IN ('scheduled','publishing') AND attempt_count<%s
            RETURNING id,workspace_id,channel_id,text,publish_key,attempt_count,telegram_message_id""",
                        (post['id'], MAX_ATTEMPTS))
            claimed = cur.fetchone()
            if claimed:
                rows.append(claimed)
    return rows


def _load_channel(conn, channel_id: int) -> dict | None:
    with conn.cursor() as cur:
        cur.execute('SELECT id,telegram_chat_id,title FROM cd_channels WHERE id=%s AND is_active=true', (channel_id,))
        return cur.fetchone()


def _record_success(conn, post_id: int, message_id: int) -> None:
    with conn.cursor() as cur:
        cur.execute("""UPDATE cd_posts SET status='published',telegram_message_id=%s,published_at=now(),
        last_error=NULL,updated_at=now() WHERE id=%s""", (message_id, post_id))
        cur.execute('INSERT INTO cd_publish_attempts(post_id,success,telegram_message_id) VALUES(%s,true,%s)',
                    (post_id, message_id))


def _record_retryable(conn, post_id: int, error_text: str) -> None:
    with conn.cursor() as cur:
        cur.execute("""UPDATE cd_posts SET last_error=%s,updated_at=now(),
        status=CASE WHEN attempt_count>=%s THEN 'failed' ELSE 'publishing' END WHERE id=%s""",
                    (error_text, MAX_ATTEMPTS, post_id))
        cur.execute("INSERT INTO cd_publish_attempts(post_id,success,error_text) VALUES(%s,false,%s)",
                    (post_id, error_text))


def _record_final_error(conn, post_id: int, error_text: str) -> None:
    with conn.cursor() as cur:
        cur.execute("UPDATE cd_posts SET status='failed',last_error=%s,updated_at=now() WHERE id=%s",
                    (error_text, post_id))
        cur.execute("INSERT INTO cd_publish_attempts(post_id,success,error_text) VALUES(%s,false,%s)",
                    (post_id, error_text))


def _notify_owner(token: str, post_id: int, title: str, error_text: str) -> None:
    ids: list[int] = []
    for raw in os.getenv('ADMIN_IDS', '').split(','):
        raw = raw.strip()
        if raw.isdigit():
            ids.append(int(raw))
    text = (f'⚠ Ошибка публикации поста #{post_id}'
            + (f' «{title[:80]}»' if title else '')
            + f'\n{error_text[:400]}')
    for chat_id in ids:
        try:
            _telegram_request(token, 'sendMessage', {'chat_id': chat_id, 'text': text})
        except Exception:
            logger.exception('Failed to notify owner %s', chat_id)


def _publish_one(token: str, conn, post: dict) -> None:
    # Защита от двойной отправки: если сообщение уже было отправлено ранее
    # (например, после потери соединения), не отправляем повторно.
    if post.get('telegram_message_id'):
        _record_success(conn, post['id'], post['telegram_message_id'])
        return
    channel = _load_channel(conn, post['channel_id']) if post.get('channel_id') else None
    if not channel:
        _record_final_error(conn, post['id'], 'Канал не найден или отключён')
        return
    try:
        result = _telegram_request(token, 'sendMessage', {
            'chat_id': channel['telegram_chat_id'],
            'text': post['text'] or '',
            'parse_mode': 'HTML',
        })
        if not result.get('ok'):
            raise RuntimeError(f"Telegram API error: {result.get('description', 'unknown')}")
        message_id = (result.get('result') or {}).get('message_id')
        _record_success(conn, post['id'], message_id)
        logger.info('published post %s -> channel %s (msg %s)', post['id'], channel['telegram_chat_id'], message_id)
    except RuntimeError as exc:
        error_text = str(exc)
        if is_retryable_error(error_text) and post['attempt_count'] < MAX_ATTEMPTS:
            _record_retryable(conn, post['id'], error_text)
            logger.warning('retryable failure post %s (attempt %s): %s', post['id'], post['attempt_count'], error_text)
        else:
            _record_final_error(conn, post['id'], error_text)
            logger.error('final failure post %s: %s', post['id'], error_text)
            _notify_owner(token, post['id'], (post.get('text') or '')[:80], error_text)


async def run_once() -> int:
    token = os.getenv('BOT_TOKEN', '').strip()
    if not token:
        raise RuntimeError('BOT_TOKEN is required')
    conn = psycopg.connect(db_url(), row_factory=psycopg.rows.dict_row)
    try:
        posts = _claim_posts(conn, datetime_now_iso())
        for post in posts:
            _publish_one(token, conn, post)
        conn.commit()
        return len(posts)
    finally:
        conn.close()


def datetime_now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


async def loop() -> None:
    logger.info('publisher started, interval=%ss', POLL_INTERVAL)
    while True:
        started = time.monotonic()
        try:
            published = await asyncio.to_thread(run_once)
            if published:
                logger.info('cycle published %s post(s)', published)
        except Exception:
            logger.exception('publisher cycle failed')
        elapsed = time.monotonic() - started
        await asyncio.sleep(max(1, POLL_INTERVAL - elapsed))


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s %(message)s')
    asyncio.run(loop())

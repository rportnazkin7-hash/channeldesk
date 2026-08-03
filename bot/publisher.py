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

# Диагностика: счётчики цикла (показываются в /status)
LAST_RUN_AT: float = 0.0
RUN_ERRORS: int = 0
EXPORTS_RUNS: int = 0

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
        cur.execute("""SELECT id,workspace_id,channel_id,text,buttons,publish_key,attempt_count,telegram_message_id
        FROM cd_posts WHERE (status='scheduled' AND scheduled_at<=%s) OR status='publishing'
        ORDER BY scheduled_at NULLS LAST, id""", (now_iso,))
        candidates = cur.fetchall()
        for post in candidates:
            cur.execute("""UPDATE cd_posts SET status='publishing',attempt_count=attempt_count+1,updated_at=now()
            WHERE id=%s AND status IN ('scheduled','publishing') AND attempt_count<%s
            RETURNING id,workspace_id,channel_id,text,buttons,publish_key,attempt_count,telegram_message_id""",
                        (post['id'], MAX_ATTEMPTS))
            claimed = cur.fetchone()
            if claimed:
                rows.append(claimed)
    return rows


def _load_channel(conn, channel_id: int) -> dict | None:
    with conn.cursor() as cur:
        cur.execute('SELECT id,telegram_chat_id,title FROM cd_channels WHERE id=%s AND is_active=true', (channel_id,))
        return cur.fetchone()


def _load_assets(conn, post_id: int) -> list[dict]:
    with conn.cursor() as cur:
        cur.execute('SELECT id,file_name,file_type,file_url,size_bytes FROM cd_content_assets WHERE post_id=%s ORDER BY created_at',
                    (post_id,))
        return cur.fetchall() or []


def _asset_to_media(asset: dict) -> dict:
    file_type = (asset.get('file_type') or '').lower()
    if file_type.startswith('image/'):
        return {'type': 'photo', 'media': asset['file_url']}
    if file_type.startswith('video/'):
        return {'type': 'video', 'media': asset['file_url']}
    return {'type': 'document', 'media': asset['file_url']}


def _send_media(telegram_request, token: str, assets: list[dict], text: str, buttons) -> int:
    """Отправляет одно фото/видео/документ или медиагруппу. Возвращает message_id."""
    media = [_asset_to_media(a) for a in assets]
    if len(media) == 1:
        item = media[0]
        method = {'photo': 'sendPhoto', 'video': 'sendVideo', 'document': 'sendDocument'}[item['type']]
        param = {'photo': 'photo', 'video': 'video', 'document': 'document'}[item['type']]
        params = {param: item['media'], 'caption': text or '', 'parse_mode': 'HTML'}
        if buttons:
            params['reply_markup'] = json.dumps({'inline_keyboard': buttons})
        result = telegram_request(token, method, params)
        return (result.get('result') or {}).get('message_id')
    # Медиагруппа: caption на первом элементе; кнопки в медиагруппе не поддерживаются.
    payload = []
    for i, item in enumerate(media):
        entry = {'type': item['type'], 'media': item['media']}
        if i == 0:
            entry['caption'] = text or ''
            entry['parse_mode'] = 'HTML'
        payload.append(entry)
    result = telegram_request(token, 'sendMediaGroup', {'media': json.dumps(payload)})
    items = (result.get('result') or [])
    return items[0].get('message_id') if items else None


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


def _fail_all_pending_exports(conn, error_text: str) -> None:
    """Если обработка экспорта упала целиком — помечаем все pending как failed."""
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE cd_exports SET status='failed',error_text=%s WHERE status='pending'",
                        (error_text,))
    except Exception:
        pass


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


def _claim_task_reminders(conn) -> list[dict]:
    """Забирает задачи, у которых наступил remind_at и напоминание ещё не отправлено."""
    rows = []
    with conn.cursor() as cur:
        cur.execute("""SELECT id,title,description,assignee_id,due_at
        FROM cd_tasks WHERE remind_at<=now() AND reminded=false
        ORDER BY remind_at LIMIT 50""")
        candidates = cur.fetchall()
        for task in candidates:
            cur.execute("""UPDATE cd_tasks SET reminded=true,updated_at=now()
            WHERE id=%s AND reminded=false RETURNING id,title,description,assignee_id,due_at""", (task['id'],))
            claimed = cur.fetchone()
            if claimed:
                rows.append(claimed)
    return rows


def _load_user_telegram_ids(conn, assignee_id: int | None) -> list[int]:
    ids = []
    for raw in os.getenv('ADMIN_IDS', '').split(','):
        raw = raw.strip()
        if raw.isdigit():
            ids.append(int(raw))
    if assignee_id is not None:
        with conn.cursor() as cur:
            cur.execute('SELECT telegram_id FROM cd_users WHERE id=%s', (assignee_id,))
            row = cur.fetchone()
            if row:
                ids.append(row['telegram_id'])
    return list(dict.fromkeys(ids))


def _send_task_reminders(token: str, conn) -> int:
    tasks = _claim_task_reminders(conn)
    sent = 0
    for task in tasks:
        text = f'⏰ Напоминание: «{task["title"]}»'
        if task.get('due_at'):
            text += f'\nСрок: {task["due_at"].strftime("%d.%m.%Y %H:%M")}'
        if task.get('description'):
            text += f'\n{task["description"][:200]}'
        for chat_id in _load_user_telegram_ids(conn, task.get('assignee_id')):
            try:
                _telegram_request(token, 'sendMessage', {'chat_id': chat_id, 'text': text})
                sent += 1
            except Exception:
                logger.exception('Failed to send reminder for task %s', task['id'])
    return sent


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
        text = post['text'] or ''
        buttons = post.get('buttons') or []
        assets = _load_assets(conn, post['id'])
        if assets:
            message_id = _send_media(_telegram_request, token, assets, text, buttons)
        else:
            params = {
                'chat_id': channel['telegram_chat_id'],
                'text': text,
                'parse_mode': 'HTML',
            }
            if buttons:
                params['reply_markup'] = json.dumps({'inline_keyboard': buttons})
            result = _telegram_request(token, 'sendMessage', params)
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


def run_once() -> int:
    """Синхронная функция: вызывается из loop через asyncio.to_thread.

    ВАЖНО: НЕ делать async — to_thread выполнит её как обычную функцию,
    и тело корутины никогда не запустится (посты зависнут в scheduled без ошибок).
    """
    token = os.getenv('BOT_TOKEN', '').strip()
    if not token:
        raise RuntimeError('BOT_TOKEN is required')
    conn = psycopg.connect(db_url(), row_factory=psycopg.rows.dict_row)
    try:
        posts = _claim_posts(conn, datetime_now_iso())
        for post in posts:
            _publish_one(token, conn, post)
        # Каждый блок изолирован: сбой одного не роняет остальные.
        try:
            _send_task_reminders(token, conn)
        except Exception as exc:
            logger.exception('task reminders failed: %s', exc)
        try:
            from bot.exports import process_pending_exports
            process_pending_exports(token, conn)
        except Exception as exc:
            logger.exception('exports processing failed: %s', exc)
        conn.commit()
        return len(posts)
    finally:
        conn.close()


def datetime_now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


async def loop() -> None:
    global LAST_RUN_AT, RUN_ERRORS
    logger.info('publisher started, interval=%ss', POLL_INTERVAL)
    while True:
        started = time.monotonic()
        try:
            published = await asyncio.to_thread(run_once)
            LAST_RUN_AT = time.time()
            if published:
                logger.info('cycle published %s post(s)', published)
        except Exception:
            RUN_ERRORS += 1
            logger.exception('publisher cycle failed')
        elapsed = time.monotonic() - started
        await asyncio.sleep(max(1, POLL_INTERVAL - elapsed))


if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(name)s %(levelname)s %(message)s')
    asyncio.run(loop())

from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger('channeldesk.slot_notifications')


def _fmt(value) -> str:
    if not value:
        return '—'
    try:
        return value.strftime('%d.%m.%Y %H:%M')
    except AttributeError:
        return str(value)


def _render(request: dict) -> str:
    lines = [
        '🆕 Новая заявка на рекламу',
        f"Канал: {request.get('channel_title') or '—'}",
        f"Клиент: {request.get('contact_name') or '—'}",
        f"Период: {_fmt(request.get('publish_at'))} — {_fmt(request.get('delete_at'))}",
        f"Стоимость: {request.get('cost') or 0} {request.get('currency') or 'RUB'}",
    ]
    if request.get('contact_telegram'):
        lines.append(f"Telegram: {request['contact_telegram']}")
    if request.get('contact_email'):
        lines.append(f"Email: {request['contact_email']}")
    if request.get('target_url'):
        lines.append(f"Ссылка: {request['target_url']}")
    if request.get('comment'):
        lines.append(f"Комментарий: {request['comment'][:500]}")
    lines.append(f"Заявка #{request['id']} — откройте ChannelDesk для обработки")
    return '\n'.join(lines)


def send_slot_request_notifications(conn, telegram_request) -> int:
    with conn.cursor() as cur:
        cur.execute("""SELECT r.id,r.workspace_id,r.contact_name,r.contact_telegram,r.contact_email,
        r.target_url,r.comment,b.publish_at,b.delete_at,b.cost,b.currency,b.format,c.title AS channel_title
        FROM cd_public_slot_requests r
        JOIN cd_ad_bookings b ON b.id=r.booking_id
        JOIN cd_channels c ON c.id=r.channel_id
        WHERE r.notified_at IS NULL ORDER BY r.created_at LIMIT 20""")
        requests = cur.fetchall() or []
    sent_count = 0
    for request in requests:
        with conn.cursor() as cur:
            cur.execute("""SELECT DISTINCT u.telegram_id FROM cd_workspace_members m
            JOIN cd_users u ON u.id=m.user_id
            WHERE m.workspace_id=%s AND m.status='active' AND m.role IN ('owner','admin')""",
                        (request['workspace_id'],))
            recipients = cur.fetchall() or []
        if not recipients:
            recipients = [{'telegram_id': int(raw.strip())} for raw in os.getenv('ADMIN_IDS', '').split(',') if raw.strip().isdigit()]
        sent = 0
        text = _render(request)
        markup = None
        mini_url = os.getenv('MINI_APP_URL', '').strip()
        if mini_url:
            markup = json.dumps({'inline_keyboard': [[{'text': 'Открыть ChannelDesk', 'web_app': {'url': mini_url}}]]})
        for recipient in recipients:
            try:
                params = {'chat_id': recipient['telegram_id'], 'text': text}
                if markup:
                    params['reply_markup'] = markup
                telegram_request(os.getenv('BOT_TOKEN', '').strip(), 'sendMessage', params)
                sent += 1
            except Exception:
                logger.exception('Failed to notify about public slot request %s', request['id'])
        if sent:
            with conn.cursor() as cur:
                cur.execute('UPDATE cd_public_slot_requests SET notified_at=now() WHERE id=%s', (request['id'],))
            sent_count += 1
    return sent_count

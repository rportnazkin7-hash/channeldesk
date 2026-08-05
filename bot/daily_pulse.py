from __future__ import annotations

"""Ежедневная сводка владельцам рабочих пространств в Telegram."""

import logging
import os
from datetime import date, datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger('channeldesk.daily_pulse')


def _enabled() -> bool:
    return os.getenv('PULSE_ENABLED', 'true').strip().lower() not in {'0', 'false', 'no', 'off'}


def _send_time() -> tuple[int, int]:
    try:
        hour = max(0, min(23, int(os.getenv('PULSE_HOUR', '9'))))
        minute = max(0, min(59, int(os.getenv('PULSE_MINUTE', '0'))))
        return hour, minute
    except ValueError:
        return 9, 0


def _zone(name: str):
    try:
        return ZoneInfo(name or 'Europe/Moscow')
    except ZoneInfoNotFoundError:
        return ZoneInfo('Europe/Moscow')


def _workspace_day(workspace: dict) -> tuple[date, datetime, datetime]:
    now_local = datetime.now(timezone.utc).astimezone(_zone(workspace.get('timezone')))
    today = now_local.date()
    start_local = datetime.combine(today, time.min, tzinfo=now_local.tzinfo)
    next_local = start_local + timedelta(days=1)
    return today, start_local.astimezone(timezone.utc), next_local.astimezone(timezone.utc)


def _due_now(workspace: dict) -> bool:
    now_local = datetime.now(timezone.utc).astimezone(_zone(workspace.get('timezone')))
    hour, minute = _send_time()
    return (now_local.hour, now_local.minute) >= (hour, minute)


def _claim(conn, workspace_id: int, pulse_date: date) -> bool:
    with conn.cursor() as cur:
        cur.execute("""INSERT INTO cd_pulse_deliveries(workspace_id,pulse_date,status)
        VALUES(%s,%s,'sending') ON CONFLICT(workspace_id,pulse_date) DO NOTHING""",
                    (workspace_id, pulse_date))
        cur.execute("""SELECT id,status,updated_at FROM cd_pulse_deliveries
        WHERE workspace_id=%s AND pulse_date=%s""", (workspace_id, pulse_date))
        row = cur.fetchone()
        if not row or row['status'] == 'sent':
            return False
        if row['status'] == 'sending' and row.get('updated_at'):
            updated = row['updated_at']
            if updated.tzinfo is None:
                updated = updated.replace(tzinfo=timezone.utc)
            if datetime.now(timezone.utc) - updated < timedelta(minutes=10):
                return False
        cur.execute("UPDATE cd_pulse_deliveries SET status='sending',updated_at=now() WHERE id=%s", (row['id'],))
        return True


def _load_recipients(cur, workspace_id: int) -> list[int]:
    cur.execute("""SELECT DISTINCT u.telegram_id FROM cd_workspace_members m
    JOIN cd_users u ON u.id=m.user_id
    WHERE m.workspace_id=%s AND m.status='active' AND m.role IN ('owner','admin')""", (workspace_id,))
    ids = [int(row['telegram_id']) for row in (cur.fetchall() or []) if row.get('telegram_id')]
    if ids:
        return ids
    return [int(raw.strip()) for raw in os.getenv('ADMIN_IDS', '').split(',') if raw.strip().isdigit()]


def _summary(cur, workspace: dict, start_utc: datetime, next_utc: datetime) -> dict:
    wid = workspace['id']
    cur.execute("""SELECT
      COUNT(*) FILTER (WHERE status='scheduled' AND scheduled_at >= %s AND scheduled_at < %s) AS scheduled,
      COUNT(*) FILTER (WHERE status='review') AS review,
      COUNT(*) FILTER (WHERE status='published' AND published_at >= %s AND published_at < %s) AS published,
      COUNT(*) FILTER (WHERE status='failed') AS failed
    FROM cd_posts WHERE workspace_id=%s""", (start_utc, next_utc, start_utc, next_utc, wid))
    posts = cur.fetchone() or {}
    cur.execute("""SELECT
      COUNT(*) FILTER (WHERE publish_at >= %s AND publish_at < %s) AS starts_today,
      COUNT(*) FILTER (WHERE payment_status='unpaid' AND status NOT IN ('cancelled','done')) AS unpaid,
      COUNT(*) FILTER (WHERE status='overdue') AS overdue
    FROM cd_ad_bookings WHERE workspace_id=%s""", (start_utc, next_utc, wid))
    bookings = cur.fetchone() or {}
    cur.execute("""SELECT
      COUNT(*) FILTER (WHERE status!='done' AND due_at >= %s AND due_at < %s) AS due_today,
      COUNT(*) FILTER (WHERE status!='done' AND due_at < %s) AS overdue
    FROM cd_tasks WHERE workspace_id=%s""", (start_utc, next_utc, start_utc, wid))
    tasks = cur.fetchone() or {}
    cur.execute("""SELECT COALESCE(SUM(amount),0) AS income
    FROM cd_finance_transactions WHERE workspace_id=%s
      AND type='income' AND occurred_at >= date_trunc('month', %s::timestamptz)""", (wid, start_utc))
    finance = cur.fetchone() or {}
    return {**posts, **bookings, **tasks, **finance}


def render_pulse(workspace: dict, pulse_date: date, summary: dict) -> str:
    def n(key: str) -> int:
        return int(summary.get(key) or 0)

    lines = [f"☀️ ChannelDesk Pulse — {workspace['name']}", f"{pulse_date.strftime('%d.%m.%Y')}", '', 'Сегодня:']
    lines.append(f"• публикаций по плану: {n('scheduled')}")
    lines.append(f"• новых размещений: {n('starts_today')}")
    lines.append(f"• постов опубликовано: {n('published')}")
    lines.append(f"• на согласовании: {n('review')}")
    lines.append(f"• задач на сегодня: {n('due_today')}")
    if n('unpaid'):
        lines.append(f"⚠ неоплаченных броней: {n('unpaid')}")
    if n('overdue'):
        lines.append(f"🚨 просроченных задач/броней: {n('overdue')}")
    if n('failed'):
        lines.append(f"❌ ошибок публикации: {n('failed')}")
    lines += ['', f"Доход с начала месяца: {float(summary.get('income') or 0):,.2f} ₽".replace(',', ' ')]
    return '\n'.join(lines)


def send_due_pulses(conn, telegram_request) -> int:
    if not _enabled():
        return 0
    sent = 0
    with conn.cursor() as cur:
        cur.execute("SELECT id,name,timezone FROM cd_workspaces WHERE is_active=true ORDER BY id")
        workspaces = cur.fetchall() or []
    for workspace in workspaces:
        if not _due_now(workspace):
            continue
        pulse_date, start_utc, next_utc = _workspace_day(workspace)
        if not _claim(conn, workspace['id'], pulse_date):
            continue
        try:
            with conn.cursor() as cur:
                summary = _summary(cur, workspace, start_utc, next_utc)
                recipients = _load_recipients(cur, workspace['id'])
            text = render_pulse(workspace, pulse_date, summary)
            for chat_id in recipients:
                telegram_request(os.getenv('BOT_TOKEN', '').strip(), 'sendMessage', {'chat_id': chat_id, 'text': text})
            with conn.cursor() as cur:
                cur.execute("""UPDATE cd_pulse_deliveries SET status='sent',sent_at=now(),updated_at=now()
                WHERE workspace_id=%s AND pulse_date=%s""", (workspace['id'], pulse_date))
            sent += 1
        except Exception as exc:  # noqa: BLE001
            with conn.cursor() as cur:
                cur.execute("""UPDATE cd_pulse_deliveries SET status='failed',error_text=%s,updated_at=now()
                WHERE workspace_id=%s AND pulse_date=%s""", (str(exc)[:500], workspace['id'], pulse_date))
            logger.exception('Daily pulse failed for workspace %s', workspace['id'])
    return sent

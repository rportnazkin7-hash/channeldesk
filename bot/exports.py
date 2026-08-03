from __future__ import annotations
"""Генерация файлов экспорта (CSV/XLSX/PDF) из БД и отправка через Telegram.

Используется publisher-циклом: находит pending-задания в cd_exports,
генерирует файл, отправляет документом в Telegram пользователю, помечает done.
Отправка — синхронный urllib multipart (надёжно в потоке asyncio.to_thread,
в отличие от aiogram Bot + asyncio.run внутри потока).
"""
import csv
import io
import json
import logging
import os
import uuid
from datetime import datetime
from pathlib import Path
from urllib.request import Request, urlopen

logger = logging.getLogger('channeldesk.exports')

FONTS_DIR = Path(__file__).resolve().parents[1] / 'assets' / 'fonts'
TELEGRAM_API = 'https://api.telegram.org'


def _fmt(dt) -> str:
    if not dt:
        return ''
    if isinstance(dt, datetime):
        return dt.strftime('%Y-%m-%d %H:%M')
    return str(dt)


def _send_document(token: str, chat_id: int, filename: str, data: bytes, caption: str) -> None:
    """Отправляет документ через Telegram Bot API (multipart/form-data, синхронно)."""
    boundary = '----channeldesk' + uuid.uuid4().hex
    body = io.BytesIO()
    for name, value in (('chat_id', str(chat_id)), ('caption', caption)):
        body.write(f'--{boundary}\r\n'.encode())
        body.write(f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        body.write(f'{value}\r\n'.encode())
    body.write(f'--{boundary}\r\n'.encode())
    body.write(f'Content-Disposition: form-data; name="document"; filename="{filename}"\r\n'.encode())
    body.write(b'Content-Type: application/octet-stream\r\n\r\n')
    body.write(data)
    body.write(f'\r\n--{boundary}--\r\n'.encode())
    req = Request(f'{TELEGRAM_API}/bot{token}/sendDocument', data=body.getvalue(), method='POST',
                  headers={'Content-Type': f'multipart/form-data; boundary={boundary}'})
    with urlopen(req, timeout=120) as resp:
        payload = json.loads(resp.read().decode('utf-8'))
    if not payload.get('ok'):
        raise RuntimeError(f"Telegram API error: {payload.get('description', 'unknown')}")


def _fmt(dt) -> str:
    if not dt:
        return ''
    if isinstance(dt, datetime):
        return dt.strftime('%Y-%m-%d %H:%M')
    return str(dt)


def _load_rows(conn, kind: str, workspace_id: int) -> list[dict]:
    with conn.cursor() as cur:
        if kind == 'posts':
            cur.execute("""SELECT p.*, c.title AS channel_title FROM cd_posts p
            LEFT JOIN cd_channels c ON c.id=p.channel_id
            WHERE p.workspace_id=%s ORDER BY p.updated_at DESC""", (workspace_id,))
        elif kind == 'bookings':
            cur.execute("""SELECT b.*, a.name AS advertiser_name, c.title AS channel_title
            FROM cd_ad_bookings b LEFT JOIN cd_advertisers a ON a.id=b.advertiser_id
            LEFT JOIN cd_channels c ON c.id=b.channel_id
            WHERE b.workspace_id=%s ORDER BY b.id DESC""", (workspace_id,))
        else:
            cur.execute("""SELECT * FROM cd_finance_transactions WHERE workspace_id=%s
            ORDER BY occurred_at DESC, id DESC""", (workspace_id,))
        return cur.fetchall() or []


def _csv_bytes(rows: list[dict], kind: str) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=';')
    if kind == 'posts':
        writer.writerow(['ID', 'Заголовок', 'Текст', 'Статус', 'Канал', 'Запланировано', 'Опубликовано', 'Ошибка'])
        for p in rows:
            writer.writerow([p['id'], p.get('title') or '', (p.get('text') or '')[:200], p.get('status') or '',
                             p.get('channel_title') or '', _fmt(p.get('scheduled_at')), _fmt(p.get('published_at')),
                             p.get('last_error') or ''])
    elif kind == 'bookings':
        writer.writerow(['ID', 'Рекламодатель', 'Канал', 'Формат', 'Стоимость', 'Валюта', 'Статус', 'Оплата',
                         'Публикация', 'ERID', 'ERID требуется'])
        for b in rows:
            writer.writerow([b['id'], b.get('advertiser_name') or '', b.get('channel_title') or '',
                             b.get('format') or '', b.get('cost'), b.get('currency') or '', b.get('status') or '',
                             b.get('payment_status') or '', _fmt(b.get('publish_at')), b.get('erid') or '',
                             'да' if b.get('erid_required', True) else 'нет'])
    else:
        writer.writerow(['ID', 'Тип', 'Сумма', 'Валюта', 'Категория', 'Описание', 'Дата'])
        for t in rows:
            writer.writerow([t['id'], 'Доход' if t.get('type') == 'income' else 'Расход', t.get('amount'),
                             t.get('currency') or '', t.get('category') or '', t.get('description') or '',
                             _fmt(t.get('occurred_at'))])
    return ('\ufeff' + buffer.getvalue()).encode('utf-8')


def _xlsx_bytes(rows: list[dict], kind: str) -> bytes:
    from openpyxl import Workbook
    wb = Workbook()
    ws = wb.active
    if kind == 'posts':
        ws.title = 'Публикации'
        ws.append(['ID', 'Заголовок', 'Текст', 'Статус', 'Канал', 'Запланировано', 'Опубликовано', 'Ошибка'])
        for p in rows:
            ws.append([p['id'], p.get('title') or '', (p.get('text') or '')[:200], p.get('status') or '',
                       p.get('channel_title') or '', _fmt(p.get('scheduled_at')), _fmt(p.get('published_at')),
                       p.get('last_error') or ''])
    elif kind == 'bookings':
        ws.title = 'Брони'
        ws.append(['ID', 'Рекламодатель', 'Канал', 'Формат', 'Стоимость', 'Валюта', 'Статус', 'Оплата',
                   'Публикация', 'ERID', 'ERID требуется'])
        for b in rows:
            ws.append([b['id'], b.get('advertiser_name') or '', b.get('channel_title') or '', b.get('format') or '',
                       float(b.get('cost') or 0), b.get('currency') or '', b.get('status') or '',
                       b.get('payment_status') or '', _fmt(b.get('publish_at')), b.get('erid') or '',
                       'да' if b.get('erid_required', True) else 'нет'])
    else:
        ws.title = 'Финансы'
        ws.append(['ID', 'Тип', 'Сумма', 'Валюта', 'Категория', 'Описание', 'Дата'])
        for t in rows:
            ws.append([t['id'], 'Доход' if t.get('type') == 'income' else 'Расход', float(t.get('amount') or 0),
                       t.get('currency') or '', t.get('category') or '', t.get('description') or '',
                       _fmt(t.get('occurred_at'))])
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


def _pdf_bytes(rows: list[dict]) -> bytes:
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_font('DejaVu', '', str(FONTS_DIR / 'DejaVuSans.ttf'))
    pdf.add_font('DejaVu', 'B', str(FONTS_DIR / 'DejaVuSans-Bold.ttf'))
    pdf.add_page()
    pdf.set_font('DejaVu', 'B', 14)
    pdf.cell(0, 10, 'ChannelDesk - Публикации', new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('DejaVu', 'B', 8)
    pdf.cell(10, 7, 'ID', border=1)
    pdf.cell(60, 7, 'Заголовок', border=1)
    pdf.cell(30, 7, 'Статус', border=1)
    pdf.cell(40, 7, 'Канал', border=1)
    pdf.cell(50, 7, 'Запланировано', border=1, new_x='LMARGIN', new_y='NEXT')
    pdf.set_font('DejaVu', '', 8)
    for p in rows:
        pdf.cell(10, 7, str(p['id']), border=1)
        pdf.cell(60, 7, (p.get('title') or '')[:40], border=1)
        pdf.cell(30, 7, (p.get('status') or ''), border=1)
        pdf.cell(40, 7, (p.get('channel_title') or '')[:25], border=1)
        pdf.cell(50, 7, _fmt(p.get('scheduled_at')), border=1, new_x='LMARGIN', new_y='NEXT')
    return pdf.output()


def _generate_file(conn, kind: str, fmt: str, workspace_id: int) -> tuple[bytes, str, str]:
    rows = _load_rows(conn, kind, workspace_id)
    filename = f'{kind}.{fmt}'
    if fmt == 'csv':
        return _csv_bytes(rows, kind), filename, 'text/csv; charset=utf-8'
    if fmt == 'xlsx':
        return _xlsx_bytes(rows, kind), filename, \
            'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    return _pdf_bytes(rows), filename, 'application/pdf'


def _claim_export(conn) -> dict | None:
    """Забирает одно pending-задание. Простой SELECT (publisher один, гонок нет)."""
    with conn.cursor() as cur:
        cur.execute("""SELECT id,workspace_id,telegram_id,kind,format FROM cd_exports
        WHERE status='pending' ORDER BY created_at LIMIT 1""")
        job = cur.fetchone()
        if job:
            cur.execute("UPDATE cd_exports SET status='processing' WHERE id=%s", (job['id'],))
    return job


def process_pending_exports(token: str, conn) -> int:
    """Обрабатывает до 5 pending-заданий экспорта: генерирует и отправляет файл."""
    processed = 0
    for _ in range(5):
        job = _claim_export(conn)
        conn.commit()  # фиксируем переход pending->processing
        if not job:
            break
        try:
            data, filename, mime = _generate_file(conn, job['kind'], job['format'], job['workspace_id'])
            _send_document(token, job['telegram_id'], filename, data,
                           f'ChannelDesk: экспорт «{job["kind"]}» ({job["format"]})')
            with conn.cursor() as cur:
                cur.execute("UPDATE cd_exports SET status='done',completed_at=now() WHERE id=%s", (job['id'],))
            processed += 1
            logger.info('export %s (%s.%s) sent to %s', job['id'], job['kind'], job['format'], job['telegram_id'])
        except Exception as exc:
            logger.exception('export %s failed', job['id'])
            with conn.cursor() as cur:
                cur.execute("UPDATE cd_exports SET status='failed',error_text=%s WHERE id=%s",
                            (str(exc)[:500], job['id']))
    return processed

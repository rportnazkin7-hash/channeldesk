from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass
from time import monotonic

import psycopg
from aiogram import F, Router
from aiogram.filters import BaseFilter
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from bot.db import db_url

logger = logging.getLogger('channeldesk.bug_reports')
router = Router()
PENDING_TTL = 15 * 60


@dataclass
class PendingBug:
    user_id: int
    started_at: float


_pending: dict[int, PendingBug] = {}


def bug_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='Отмена', callback_data='bug:cancel')
    ]])


async def start_bug_report(message: Message, user_id: int) -> None:
    _pending[user_id] = PendingBug(user_id=user_id, started_at=monotonic())
    await message.answer(
        '🐞 Опишите ошибку одним сообщением.\n\n'
        'Можно приложить скриншот, видео или переслать проблемное сообщение.\n\n'
        'Напишите, что произошло и что вы ожидали увидеть.',
        reply_markup=bug_cancel_keyboard(),
    )


def _media_info(message: Message) -> tuple[str | None, str | None, str | None]:
    if message.photo:
        return message.photo[-1].file_id, 'photo', f'photo_{message.photo[-1].file_unique_id}.jpg'
    if message.video:
        return message.video.file_id, 'video', getattr(message.video, 'file_name', None) or 'video.mp4'
    if message.document:
        return message.document.file_id, 'document', message.document.file_name or 'document'
    if message.animation:
        return message.animation.file_id, 'animation', getattr(message.animation, 'file_name', None) or 'animation.mp4'
    return None, None, None


def _store_bug(message: Message, description: str) -> dict:
    user = message.from_user
    with psycopg.connect(db_url(), row_factory=psycopg.rows.dict_row) as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO cd_users(telegram_id,username,first_name,last_name,last_seen_at)
        VALUES(%s,%s,%s,%s,now()) ON CONFLICT(telegram_id) DO UPDATE SET username=excluded.username,
        first_name=excluded.first_name,last_name=excluded.last_name,last_seen_at=now()
        RETURNING id""", (user.id, user.username, user.first_name, user.last_name))
        user_row = cur.fetchone()
        cur.execute("""SELECT m.workspace_id FROM cd_workspace_members m
        JOIN cd_workspaces w ON w.id=m.workspace_id
        WHERE m.user_id=%s AND m.status='active' AND w.is_active=true
        ORDER BY w.updated_at DESC LIMIT 1""", (user_row['id'],))
        workspace = cur.fetchone()
        file_id, file_type, file_name = _media_info(message)
        cur.execute("""INSERT INTO cd_bug_reports(
            workspace_id,user_id,telegram_id,username,first_name,description,source,app_version,
            message_id,chat_id,attachment_file_id,attachment_type,attachment_name)
        VALUES(%s,%s,%s,%s,%s,%s,'bot',%s,%s,%s,%s,%s,%s) RETURNING *""",
                    (workspace['workspace_id'] if workspace else None, user_row['id'], user.id,
                     user.username, user.first_name, description.strip() or 'Вложение без описания',
                     os.getenv('BOT_CODE_VERSION', 'bot-api-newsdesk-0.47.0'), message.message_id,
                     message.chat.id, file_id, file_type, file_name))
        return cur.fetchone()


async def _notify_admins(bot, report: dict, source_message: Message) -> None:
    admin_ids = [int(raw.strip()) for raw in os.getenv('ADMIN_IDS', '').split(',') if raw.strip().isdigit()]
    text = f"🐞 Новая ошибка #{report['id']}\n{report['description'][:900]}"
    if report.get('username'):
        text += f"\nАвтор: @{report['username']}"
    text += f"\nИсточник: бот\nПриоритет: {report.get('severity', 'normal')}"
    for chat_id in admin_ids:
        try:
            await bot.send_message(chat_id, text)
            if report.get('attachment_file_id'):
                await bot.copy_message(chat_id=chat_id, from_chat_id=source_message.chat.id,
                                       message_id=source_message.message_id)
        except Exception:
            logger.exception('failed to notify admin %s about bug %s', chat_id, report['id'])


class PendingBugFilter(BaseFilter):
    async def __call__(self, message: Message) -> bool:
        user = message.from_user
        if not user:
            return False
        item = _pending.get(user.id)
        if not item:
            return False
        if monotonic() - item.started_at > PENDING_TTL:
            _pending.pop(user.id, None)
            return False
        return True


@router.callback_query(F.data == 'bug:cancel')
async def cancel_bug_report(callback: CallbackQuery):
    _pending.pop(callback.from_user.id, None)
    await callback.answer('Отменено')
    if callback.message:
        await callback.message.edit_text('Создание сообщения об ошибке отменено.')


@router.message(PendingBugFilter())
async def receive_bug_report(message: Message):
    item = _pending.pop(message.from_user.id, None)
    if not item:
        return
    description = (message.text or message.caption or '').strip()
    try:
        report = await asyncio.to_thread(_store_bug, message, description)
        await _notify_admins(message.bot, report, message)
        await message.answer(f"✅ Ошибка #{report['id']} принята. Спасибо! Мы проверим её в ближайшее время.")
    except Exception:
        logger.exception('failed to save bug report')
        await message.answer('Не удалось сохранить отчёт. Попробуйте отправить его ещё раз.')

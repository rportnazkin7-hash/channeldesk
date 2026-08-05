from __future__ import annotations

import asyncio
import io
import json
import logging
import os
import re
import uuid
from dataclasses import dataclass
from html import escape
from pathlib import Path
from time import monotonic
from urllib.parse import quote
from urllib.request import Request, urlopen

import psycopg
from aiogram import Bot, F, Router
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, WebAppInfo

from bot.access import access_state
from bot.db import db_url

logger = logging.getLogger('channeldesk.forward_capture')
router = Router()

STORAGE_BUCKET = 'channeldesk-assets'
PENDING_TTL = 15 * 60


@dataclass
class MediaItem:
    file_id: str
    file_name: str
    file_type: str
    size_bytes: int | None = None


@dataclass
class PendingCapture:
    token: str
    user_id: int
    user_db_id: int
    messages: list[Message]
    workspace_id: int | None = None
    created_at: float = 0.0

    @property
    def message(self) -> Message:
        return self.messages[0]


@dataclass
class MediaGroupBatch:
    user_id: int
    messages: list[Message]
    generation: int = 0


_pending: dict[str, PendingCapture] = {}
_media_groups: dict[tuple[int, str], MediaGroupBatch] = {}
# Telegram присылает элементы альбома отдельными update; даём им время собраться.
_MEDIA_GROUP_WAIT = 1.5


def _clean_pending() -> None:
    now = monotonic()
    expired = [token for token, item in _pending.items() if now - item.created_at > PENDING_TTL]
    for token in expired:
        _pending.pop(token, None)


def _put_pending(user_id: int, user_db_id: int, messages: list[Message]) -> PendingCapture:
    _clean_pending()
    token = uuid.uuid4().hex[:12]
    item = PendingCapture(token=token, user_id=user_id, user_db_id=user_db_id,
                          messages=sorted(messages, key=lambda message: message.message_id),
                          created_at=monotonic())
    _pending[token] = item
    return item


def _get_pending(token: str, user_id: int) -> PendingCapture | None:
    _clean_pending()
    item = _pending.get(token)
    if not item or item.user_id != user_id:
        return None
    return item


def _remove_pending(token: str) -> None:
    _pending.pop(token, None)


def _plain_text(message: Message) -> str:
    return (getattr(message, 'text', None) or getattr(message, 'caption', None) or '').strip()


def _html_text(message: Message) -> str:
    """Берёт HTML Telegram, а при недоступности форматирования экранирует текст."""
    for attribute in ('html_text', 'html_caption'):
        try:
            value = getattr(message, attribute, None)
        except Exception:
            value = None
        if value:
            return str(value).strip()
    return escape(_plain_text(message), quote=False).replace('\n', '\n')


def _combined_plain_text(messages: list[Message]) -> str:
    return '\n'.join(text for text in (_plain_text(message) for message in messages) if text).strip()


def _combined_html_text(messages: list[Message]) -> str:
    return '\n'.join(text for text in (_html_text(message) for message in messages) if text).strip()


def _title(message: Message, media: list[MediaItem], plain_text: str | None = None) -> str:
    plain = plain_text if plain_text is not None else _plain_text(message)
    first_line = next((line.strip() for line in plain.splitlines() if line.strip()), '')
    # Первая строка удобнее всего работает как заголовок для быстрого черновика.
    title = re.sub(r'\s+', ' ', first_line).strip()
    if not title and media:
        title = Path(media[0].file_name).stem.replace('_', ' ').strip()
    return (title or 'Новый пост из Telegram')[:255]


def _buttons(message: Message) -> list[list[dict]]:
    keyboard = getattr(message, 'reply_markup', None)
    rows = getattr(keyboard, 'inline_keyboard', None) or []
    result: list[list[dict]] = []
    for row in rows:
        row_result: list[dict] = []
        for button in row:
            text = str(getattr(button, 'text', '') or '').strip()
            url = str(getattr(button, 'url', '') or '').strip()
            if text and re.match(r'^(https?://|tg://)', url, re.IGNORECASE):
                row_result.append({'text': text[:64], 'url': url[:2048]})
        if row_result:
            result.append(row_result)
    return result[:8]


def extract_media(message: Message) -> list[MediaItem]:
    """Извлекает самое качественное вложение из пересланного сообщения."""
    if getattr(message, 'photo', None):
        photo = message.photo[-1]
        return [MediaItem(photo.file_id, f'photo_{photo.file_unique_id}.jpg', 'image/jpeg', photo.file_size)]
    video = getattr(message, 'video', None)
    if video:
        return [MediaItem(video.file_id, getattr(video, 'file_name', None) or f'video_{video.file_unique_id}.mp4',
                          getattr(video, 'mime_type', None) or 'video/mp4', video.file_size)]
    document = getattr(message, 'document', None)
    if document:
        return [MediaItem(document.file_id, getattr(document, 'file_name', None) or f'document_{document.file_unique_id}',
                          getattr(document, 'mime_type', None) or 'application/octet-stream', document.file_size)]
    animation = getattr(message, 'animation', None)
    if animation:
        return [MediaItem(animation.file_id, getattr(animation, 'file_name', None) or f'animation_{animation.file_unique_id}.mp4',
                          getattr(animation, 'mime_type', None) or 'video/mp4', animation.file_size)]
    audio = getattr(message, 'audio', None)
    if audio:
        return [MediaItem(audio.file_id, getattr(audio, 'file_name', None) or f'audio_{audio.file_unique_id}.mp3',
                          getattr(audio, 'mime_type', None) or 'audio/mpeg', audio.file_size)]
    voice = getattr(message, 'voice', None)
    if voice:
        return [MediaItem(voice.file_id, f'voice_{voice.file_unique_id}.ogg', 'audio/ogg', voice.file_size)]
    return []


def _user_and_workspaces(telegram_id: int, user_data: dict | None) -> tuple[int, list[dict]]:
    with psycopg.connect(db_url(), row_factory=psycopg.rows.dict_row) as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO cd_users(telegram_id,username,first_name,last_name,last_seen_at)
        VALUES(%s,%s,%s,%s,now())
        ON CONFLICT(telegram_id) DO UPDATE SET username=excluded.username,
        first_name=excluded.first_name,last_name=excluded.last_name,last_seen_at=now(),updated_at=now()
        RETURNING id""", (telegram_id, (user_data or {}).get('username'), (user_data or {}).get('first_name'),
                            (user_data or {}).get('last_name')))
        user_id = cur.fetchone()['id']
        cur.execute("""SELECT w.id,w.name,m.role
        FROM cd_workspaces w
        JOIN cd_workspace_members m ON m.workspace_id=w.id AND m.user_id=%s AND m.status='active'
        WHERE w.is_active=true AND m.role IN ('owner','admin','editor','author')
        ORDER BY w.updated_at DESC""", (user_id,))
        return user_id, cur.fetchall() or []


def _workspace_channels(workspace_id: int) -> list[dict]:
    with psycopg.connect(db_url(), row_factory=psycopg.rows.dict_row) as conn, conn.cursor() as cur:
        cur.execute("""SELECT id,title,telegram_chat_id
        FROM cd_channels WHERE workspace_id=%s AND is_active=true ORDER BY title""", (workspace_id,))
        return cur.fetchall() or []


def _storage_upload(data: bytes, workspace_id: int, item: MediaItem) -> str | None:
    """Пытается сохранить файл в публичное Supabase Storage.

    Если на Bothost нет Storage-переменных или политика загрузки недоступна,
    вызывающий код сохранит Telegram file_id — publisher умеет отправлять его напрямую.
    """
    base = os.getenv('SUPABASE_URL', '').strip().rstrip('/')
    key = os.getenv('SUPABASE_ANON_KEY', '').strip()
    if not base or not key or not data:
        return None
    suffix = Path(item.file_name).suffix.lower()
    path = f'{workspace_id}/forwarded/{uuid.uuid4().hex}{suffix}'
    url = f'{base}/storage/v1/object/{STORAGE_BUCKET}/{quote(path, safe="/")}'
    request = Request(url, data=data, method='POST', headers={
        'Authorization': f'Bearer {key}',
        'apikey': key,
        'Content-Type': item.file_type or 'application/octet-stream',
        'x-upsert': 'false',
    })
    try:
        with urlopen(request, timeout=90) as response:
            if response.status not in {200, 201}:
                return None
        return f'{base}/storage/v1/object/public/{STORAGE_BUCKET}/{path}'
    except Exception as exc:  # noqa: BLE001
        logger.warning('storage upload failed for %s: %s', item.file_name, str(exc)[:180])
        return None


async def _materialize_media(bot: Bot, workspace_id: int, item: MediaItem) -> str:
    """Возвращает public URL, либо Telegram file_id как надёжный fallback."""
    try:
        telegram_file = await bot.get_file(item.file_id)
        if telegram_file.file_path:
            buffer = io.BytesIO()
            await bot.download_file(telegram_file.file_path, destination=buffer)
            uploaded = await asyncio.to_thread(_storage_upload, buffer.getvalue(), workspace_id, item)
            if uploaded:
                return uploaded
    except Exception as exc:  # noqa: BLE001
        logger.warning('could not download forwarded media %s: %s', item.file_name, str(exc)[:180])
    return item.file_id


def _insert_post(workspace_id: int, channel_id: int | None, user_id: int,
                 title: str, text: str, buttons: list[list[dict]],
                 assets: list[tuple[MediaItem, str]]) -> dict:
    with psycopg.connect(db_url(), row_factory=psycopg.rows.dict_row) as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO cd_posts(workspace_id,channel_id,title,text,status,approval_required,created_by,buttons)
        VALUES(%s,%s,%s,%s,'draft',true,%s,%s::jsonb) RETURNING *""",
                    (workspace_id, channel_id, title, text, user_id, json.dumps(buttons)))
        post = cur.fetchone()
        if text:
            cur.execute("""INSERT INTO cd_post_versions(post_id,title,text,created_by)
            VALUES(%s,%s,%s,%s)""", (post['id'], title, text, user_id))
        for item, file_url in assets:
            cur.execute("""INSERT INTO cd_content_assets(
                workspace_id,post_id,file_name,file_type,file_url,size_bytes,uploaded_by)
            VALUES(%s,%s,%s,%s,%s,%s,%s)""",
                        (workspace_id, post['id'], item.file_name, item.file_type,
                         file_url, item.size_bytes, user_id))
        cur.execute("""INSERT INTO cd_audit_log(workspace_id,user_id,action,entity_type,entity_id,details)
        VALUES(%s,%s,'post.forwarded','post',%s,%s::jsonb)""",
                    (workspace_id, user_id, post['id'], json.dumps({'source': 'telegram_forward'})))
        return post


def _workspace_keyboard(items: list[dict], token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=str(item['name'])[:48], callback_data=f'fc:w:{token}:{item["id"]}')
    ] for item in items])


def _channel_keyboard(items: list[dict], token: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=str(item['title'])[:48], callback_data=f'fc:c:{token}:{item["id"]}')
    ] for item in items] + [[InlineKeyboardButton(text='Без канала', callback_data=f'fc:c:{token}:0')]])


def _open_app_keyboard(post_id: int, workspace_id: int) -> InlineKeyboardMarkup | None:
    url = os.getenv('MINI_APP_URL', '').strip()
    if not url:
        return None
    separator = '&' if '?' in url else '?'
    target = f'{url}{separator}forward_post={post_id}&forward_workspace={workspace_id}'
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='Открыть черновик', web_app=WebAppInfo(url=target))
    ]])


async def _create_for_channel(bot: Bot, item: PendingCapture, channel_id: int | None) -> tuple[dict, str]:
    message = item.message
    media = [media_item for source in item.messages for media_item in extract_media(source)]
    plain_text = _combined_plain_text(item.messages)
    assets: list[tuple[MediaItem, str]] = []
    for media_item in media:
        file_url = await _materialize_media(bot, item.workspace_id or 0, media_item)
        assets.append((media_item, file_url))
    post = await asyncio.to_thread(
        _insert_post,
        item.workspace_id or 0,
        channel_id,
        item.user_db_id,
        _title(message, media, plain_text),
        _combined_html_text(item.messages),
        _buttons(message),
        assets,
    )
    channels = await asyncio.to_thread(_workspace_channels, item.workspace_id or 0)
    channel_title = next((c['title'] for c in channels if c['id'] == channel_id), 'Без канала') if channel_id else 'Без канала'
    return post, channel_title


async def _finish_capture(callback_or_message, bot: Bot, item: PendingCapture, channel_id: int | None) -> None:
    post, channel_title = await _create_for_channel(bot, item, channel_id)
    _remove_pending(item.token)
    media_count = sum(len(extract_media(message)) for message in item.messages)
    text = f'✅ Черновик #{post["id"]} создан\nКанал: {channel_title}\nСтатус: Черновик\n\nПост не публиковался автоматически.'
    if _combined_plain_text(item.messages):
        text += '\nТекст сохранён.'
    if media_count:
        text += f'\nВложений: {media_count}.'
    await callback_or_message.answer(text, reply_markup=_open_app_keyboard(post['id'], item.workspace_id or 0))


async def _capture_messages(messages: list[Message], bot: Bot) -> None:
    messages = sorted(messages, key=lambda message: message.message_id)
    message = messages[0]
    user_id = message.from_user.id
    state = await access_state(bot, user_id)
    if not state['allowed']:
        if state['closed']:
            await message.answer('🚧 Бот в разработке. Следите за обновлениями в канале @thechanneldesk.')
        else:
            await message.answer('Сначала подпишитесь на канал @thechanneldesk, затем повторите отправку.')
        return

    user_data = message.from_user.model_dump() if message.from_user else {}
    try:
        user_db_id, workspaces = await asyncio.to_thread(_user_and_workspaces, user_id, user_data)
    except Exception as exc:  # noqa: BLE001
        logger.exception('failed to load workspaces for forwarded message: %s', exc)
        await message.answer('Не удалось сохранить материал. Попробуйте ещё раз.')
        return
    if not workspaces:
        await message.answer('У вас пока нет рабочего пространства с правом создания постов. Сначала создайте его в Mini App.')
        return

    item = _put_pending(user_id, user_db_id, messages)
    if len(workspaces) > 1:
        await message.answer('Выберите рабочее пространство для черновика:', reply_markup=_workspace_keyboard(workspaces, item.token))
        return
    item.workspace_id = workspaces[0]['id']
    channels = await asyncio.to_thread(_workspace_channels, item.workspace_id)
    if len(channels) == 1:
        try:
            await _finish_capture(message, bot, item, channels[0]['id'])
        except Exception:
            _remove_pending(item.token)
            logger.exception('failed to create forwarded draft')
            await message.answer('Материал принят, но черновик не создался. Попробуйте повторить.')
        return
    await message.answer('В какой канал сохранить черновик?', reply_markup=_channel_keyboard(channels, item.token))


async def _flush_media_group(key: tuple[int, str], batch: MediaGroupBatch, generation: int) -> None:
    await asyncio.sleep(_MEDIA_GROUP_WAIT)
    current = _media_groups.get(key)
    if current is not batch or current.generation != generation:
        return
    _media_groups.pop(key, None)
    try:
        await _capture_messages(batch.messages, batch.messages[0].bot)
    except Exception:
        logger.exception('failed to capture forwarded media group')
        await batch.messages[0].answer('Не удалось сохранить альбом. Попробуйте переслать его ещё раз.')


@router.message(F.forward_origin)
async def capture_forwarded_message(message: Message):
    media_group_id = getattr(message, 'media_group_id', None)
    if not media_group_id:
        await _capture_messages([message], message.bot)
        return

    key = (message.from_user.id, str(media_group_id))
    batch = _media_groups.get(key)
    if batch is None:
        batch = MediaGroupBatch(user_id=message.from_user.id, messages=[])
        _media_groups[key] = batch
    batch.messages.append(message)
    batch.generation += 1
    generation = batch.generation
    asyncio.create_task(_flush_media_group(key, batch, generation))


@router.callback_query(F.data.startswith('fc:'))
async def forward_capture_callback(callback: CallbackQuery):
    parts = (callback.data or '').split(':')
    if len(parts) != 4:
        await callback.answer('Ссылка устарела.', show_alert=True)
        return
    _, action, token, raw_id = parts
    item = _get_pending(token, callback.from_user.id)
    if not item:
        await callback.answer('Материал устарел. Перешлите сообщение ещё раз.', show_alert=True)
        return
    await callback.answer()
    if action == 'w':
        try:
            item.workspace_id = int(raw_id)
            channels = await asyncio.to_thread(_workspace_channels, item.workspace_id)
            if callback.message:
                await callback.message.edit_text('В какой канал сохранить черновик?', reply_markup=_channel_keyboard(channels, token))
        except Exception:
            logger.exception('failed to select workspace for forwarded draft')
            if callback.message:
                await callback.message.answer('Не удалось загрузить каналы. Попробуйте переслать материал ещё раз.')
        return
    if action == 'c':
        if item.workspace_id is None:
            await callback.answer('Сначала выберите рабочее пространство.', show_alert=True)
            return
        channel_id = int(raw_id) if raw_id != '0' else None
        try:
            if callback.message:
                await callback.message.edit_text('⏳ Создаю черновик…')
                await _finish_capture(callback.message, callback.bot, item, channel_id)
        except Exception:
            _remove_pending(item.token)
            logger.exception('failed to create forwarded draft from callback')
            if callback.message:
                await callback.message.answer('Не удалось создать черновик. Перешлите материал ещё раз.')

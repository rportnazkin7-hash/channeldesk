from __future__ import annotations
import json
import os
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

TELEGRAM_API = 'https://api.telegram.org'
_bot_id: int | None = None


def _get_json(method: str, params: dict) -> dict | None:
    """Синхронный вызов Telegram Bot API. Возвращает None при любой ошибке."""
    token = os.getenv('BOT_TOKEN', '').strip()
    if not token:
        return None
    url = f'{TELEGRAM_API}/bot{token}/{method}'
    if params:
        url += '?' + urlencode({str(k): str(v) for k, v in params.items()})
    try:
        with urlopen(Request(url, headers={'Accept': 'application/json'}), timeout=6) as resp:
            return json.loads(resp.read().decode('utf-8'))
    except (HTTPError, URLError, TimeoutError, ValueError, OSError):
        return None


def get_bot_id() -> int | None:
    global _bot_id
    if _bot_id is not None:
        return _bot_id
    data = _get_json('getMe', {})
    result = (data or {}).get('result') or {}
    if result.get('id'):
        _bot_id = int(result['id'])
    return _bot_id


def verify_bot_permissions(chat_id: int) -> dict | None:
    """Live-проверка прав бота в канале через getChatMember.

    Возвращает None, если проверка недоступна (нет BOT_TOKEN, сетевой сбой,
    Telegram вернул ошибку) — в этом случае вызывающий код доверяет сохранённым
    правам (dev-режим). Иначе возвращает {'is_admin', 'can_post_messages', 'permissions'}.
    """
    bot_id = get_bot_id()
    if bot_id is None:
        return None
    data = _get_json('getChatMember', {'chat_id': chat_id, 'user_id': bot_id})
    if not data:
        return None
    result = data.get('result') or {}
    status = result.get('status')
    keys = ('can_post_messages', 'can_edit_messages', 'can_delete_messages', 'can_manage_chat')
    return {
        'is_admin': status in ('administrator', 'creator'),
        'can_post_messages': bool(result.get('can_post_messages', False)),
        'permissions': {k: bool(result.get(k, False)) for k in keys},
    }

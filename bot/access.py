from __future__ import annotations

import logging
import os

from aiogram import Bot

logger = logging.getLogger('channeldesk.access')

DEFAULT_REQUIRED_CHANNEL = '@thechanneldesk'
DEFAULT_REQUIRED_CHANNEL_URL = 'https://t.me/thechanneldesk'


def required_channel() -> str:
    return os.getenv('REQUIRED_CHANNEL', DEFAULT_REQUIRED_CHANNEL).strip() or DEFAULT_REQUIRED_CHANNEL


def required_channel_url() -> str:
    return os.getenv('REQUIRED_CHANNEL_URL', DEFAULT_REQUIRED_CHANNEL_URL).strip() or DEFAULT_REQUIRED_CHANNEL_URL


def admin_ids() -> set[int]:
    return {
        int(raw.strip())
        for raw in os.getenv('ADMIN_IDS', '').split(',')
        if raw.strip().isdigit()
    }


def is_admin(user_id: int) -> bool:
    return user_id in admin_ids()


def zbt_enabled() -> bool:
    """ЗБТ включён по умолчанию, чтобы закрытие не забыли при деплое."""
    raw = os.getenv('ZBT_ENABLED', 'true').strip().lower()
    return raw not in {'0', 'false', 'no', 'off'}


def is_subscribed_member(member) -> bool:
    """Проверяет статусы участника, которые означают подписку на канал."""
    status = getattr(member, 'status', '')
    status = getattr(status, 'value', status)
    if status in {'member', 'administrator', 'creator'}:
        return True
    # Ограниченный участник всё ещё подписан, если Telegram оставил is_member=true.
    return status == 'restricted' and bool(getattr(member, 'is_member', False))


async def subscription_status(bot: Bot, user_id: int) -> bool | None:
    """Возвращает True/False, а None — если Bot API не дал проверить подписку."""
    try:
        member = await bot.get_chat_member(chat_id=required_channel(), user_id=user_id)
    except Exception as exc:  # TelegramBadRequest/сетевые ошибки зависят от версии aiogram.
        logger.warning('required subscription check failed for %s: %s', user_id, str(exc)[:180])
        return None
    return is_subscribed_member(member)


async def access_state(bot: Bot, user_id: int) -> dict[str, bool | None]:
    """Возвращает состояние доступа пользователя в бот и Mini App."""
    if is_admin(user_id):
        return {'admin': True, 'subscribed': True, 'allowed': True, 'closed': False}

    subscribed = await subscription_status(bot, user_id)
    if subscribed is not True:
        return {'admin': False, 'subscribed': subscribed, 'allowed': False, 'closed': False}
    if zbt_enabled():
        return {'admin': False, 'subscribed': True, 'allowed': False, 'closed': True}
    return {'admin': False, 'subscribed': True, 'allowed': True, 'closed': False}

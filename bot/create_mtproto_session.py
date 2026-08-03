"""Одноразовая локальная генерация StringSession для MTProto-сборщика.

Запускать локально, не на Vercel и не в репозитории с коммитом:
  MT_PROTO_API_ID=... MT_PROTO_API_HASH=... python bot/create_mtproto_session.py

Скрипт попросит номер телефона, код Telegram и, если включён, пароль 2FA.
Полученную строку добавить в секрет MT_PROTO_SESSION_STRING на Bothost.
"""
from __future__ import annotations

import asyncio
import os

from telethon import TelegramClient
from telethon.sessions import StringSession


async def main() -> None:
    raw_id = os.getenv('MT_PROTO_API_ID', '').strip()
    api_hash = os.getenv('MT_PROTO_API_HASH', '').strip()
    if not raw_id or not api_hash:
        raise SystemExit('Нужны MT_PROTO_API_ID и MT_PROTO_API_HASH')
    client = TelegramClient(StringSession(), int(raw_id), api_hash)
    await client.start()
    print('\nMT_PROTO_SESSION_STRING=')
    print(client.session.save())
    await client.disconnect()


if __name__ == '__main__':
    asyncio.run(main())

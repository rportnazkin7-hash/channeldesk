from __future__ import annotations
import asyncio, os
from aiogram import Bot, Dispatcher, Router
from aiogram.filters import CommandStart
from aiogram.types import Message, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo

router=Router()
@router.message(CommandStart())
async def start(message: Message):
    url=os.getenv('MINI_APP_URL','').strip()
    keyboard=None
    if url:
        keyboard=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Открыть ChannelDesk',web_app=WebAppInfo(url=url))]])
    await message.answer('ChannelDesk — каналы, реклама и команда в одном рабочем пространстве.',reply_markup=keyboard)

async def main():
    token=os.getenv('BOT_TOKEN','').strip()
    if not token: raise RuntimeError('BOT_TOKEN is required')
    bot=Bot(token); dp=Dispatcher(); dp.include_router(router)
    await dp.start_polling(bot)

if __name__=='__main__': asyncio.run(main())

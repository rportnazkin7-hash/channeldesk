from __future__ import annotations
import asyncio,json,os
import psycopg
from aiogram import Bot,Dispatcher,Router
from aiogram.enums import ChatMemberStatus,ChatType
from aiogram.filters import CommandStart
from aiogram.types import ChatMemberUpdated,InlineKeyboardButton,InlineKeyboardMarkup,Message,WebAppInfo

router=Router()

def db_url()->str:
    value=os.getenv('DATABASE_URL','').strip()
    if not value: raise RuntimeError('DATABASE_URL is required')
    return value.replace('postgresql+psycopg://','postgresql://').replace('postgresql+asyncpg://','postgresql://')

def save_connection(event:ChatMemberUpdated,connected:bool)->None:
    member=event.new_chat_member
    permissions={
        'can_post_messages':bool(getattr(member,'can_post_messages',False)),
        'can_edit_messages':bool(getattr(member,'can_edit_messages',False)),
        'can_delete_messages':bool(getattr(member,'can_delete_messages',False)),
        'can_manage_chat':bool(getattr(member,'can_manage_chat',False)),
    }
    with psycopg.connect(db_url()) as conn,conn.cursor() as cur:
        if connected:
            cur.execute("""INSERT INTO cd_channel_connections(telegram_chat_id,title,username,actor_telegram_id,bot_permissions,status)
            VALUES(%s,%s,%s,%s,%s::jsonb,'pending') ON CONFLICT(telegram_chat_id) DO UPDATE SET title=excluded.title,
            username=excluded.username,actor_telegram_id=excluded.actor_telegram_id,bot_permissions=excluded.bot_permissions,
            status='pending',connected_channel_id=NULL,observed_at=now(),updated_at=now()""",
            (event.chat.id,event.chat.title or 'Без названия',event.chat.username,event.from_user.id,json.dumps(permissions)))
        else:
            cur.execute("UPDATE cd_channel_connections SET status='removed',updated_at=now() WHERE telegram_chat_id=%s",(event.chat.id,))
            cur.execute("UPDATE cd_channels SET is_connected=false,updated_at=now() WHERE telegram_chat_id=%s",(event.chat.id,))

@router.message(CommandStart())
async def start(message:Message):
    url=os.getenv('MINI_APP_URL','').strip(); keyboard=None
    if url: keyboard=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Открыть ChannelDesk',web_app=WebAppInfo(url=url))]])
    await message.answer('ChannelDesk — каналы, реклама и команда в одном рабочем пространстве.',reply_markup=keyboard)

@router.my_chat_member()
async def bot_membership_changed(event:ChatMemberUpdated):
    if event.chat.type not in {ChatType.CHANNEL,ChatType.SUPERGROUP}: return
    connected=event.new_chat_member.status in {ChatMemberStatus.ADMINISTRATOR,ChatMemberStatus.CREATOR}
    await asyncio.to_thread(save_connection,event,connected)
    if connected:
        try:
            await event.bot.send_message(event.from_user.id,f'Канал «{event.chat.title}» обнаружен. Откройте ChannelDesk и подключите его к рабочему пространству.')
        except Exception:
            pass

async def main():
    token=os.getenv('BOT_TOKEN','').strip()
    if not token: raise RuntimeError('BOT_TOKEN is required')
    bot=Bot(token);dp=Dispatcher();dp.include_router(router)
    await dp.start_polling(bot,allowed_updates=['message','my_chat_member'])

if __name__=='__main__': asyncio.run(main())

from __future__ import annotations
import asyncio,json,logging,os,time
import psycopg
from aiogram import Bot,Dispatcher,F,Router
from aiogram.enums import ChatMemberStatus,ChatType
from aiogram.filters import Command,CommandStart
from aiogram.types import CallbackQuery,ChatMemberUpdated,InlineKeyboardButton,InlineKeyboardMarkup,Message,MessageReactionCountUpdated,WebAppInfo
from bot.access import access_state,required_channel_url
from bot.db import db_url
from bot import migrate, publisher

logger=logging.getLogger('channeldesk.bot')
router=Router()
BOT_CODE_VERSION='bot-api-pulse'
_process_started=time.time()
_publisher_task=None

def extract_invite_token(text:str)->str|None:
    """Извлекает токен приглашения из '/start invite_<token>'."""
    parts=(text or '').strip().split(None,1)
    if len(parts)!=2: return None
    rest=parts[1].strip()
    prefix='invite_'
    if rest.startswith(prefix): return rest[len(prefix):] or None
    return None

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

SUBSCRIPTION_GATE_TEXT='Чтобы пользоваться ChannelDesk, сначала подпишитесь на наш канал. После подписки нажмите «Проверить подписку».'
SUBSCRIPTION_CHECK_ERROR='Не удалось проверить подписку через Telegram. Попробуйте ещё раз через несколько секунд.'
DEVELOPMENT_TEXT='🚧 Бот в разработке. Следите за обновлениями в нашем канале: https://t.me/thechanneldesk'


def subscription_keyboard()->InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Подписаться на канал',url=required_channel_url())],
        [InlineKeyboardButton(text='Проверить подписку',callback_data='check_required_subscription')],
    ])


def development_keyboard()->InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text='Канал ChannelDesk',url=required_channel_url())],
    ])


def mini_app_keyboard(url:str)->InlineKeyboardMarkup|None:
    if not url:
        return None
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text='Открыть ChannelDesk',web_app=WebAppInfo(url=url))
    ]])


async def send_entry_message(message:Message,invite_token:str|None=None,user_id:int|None=None):
    state=await access_state(message.bot,user_id if user_id is not None else message.from_user.id)
    if not state['allowed']:
        if state['closed']:
            await message.answer(DEVELOPMENT_TEXT,reply_markup=development_keyboard())
        elif state['subscribed'] is None:
            await message.answer(SUBSCRIPTION_CHECK_ERROR,reply_markup=subscription_keyboard())
        else:
            await message.answer(SUBSCRIPTION_GATE_TEXT,reply_markup=subscription_keyboard())
        return

    url=os.getenv('MINI_APP_URL','').strip()
    if invite_token and url:
        keyboard=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(
            text='Принять приглашение',web_app=WebAppInfo(url=f'{url}?startapp=invite_{invite_token}'))]])
        await message.answer('Вас пригласили в рабочее пространство ChannelDesk. Нажмите кнопку, чтобы принять приглашение.',reply_markup=keyboard)
        return
    await message.answer('ChannelDesk — каналы, реклама и команда в одном рабочем пространстве.',reply_markup=mini_app_keyboard(url))


@router.message(CommandStart(deep_link=True))
async def start_deep_link(message:Message):
    await send_entry_message(message,extract_invite_token(message.text or ''))

@router.message(Command('status'))
async def status_cmd(message:Message):
    admins={int(x) for x in os.getenv('ADMIN_IDS','').split(',') if x.strip().isdigit()}
    if message.from_user.id not in admins:
        await message.answer('Нет доступа.'); return
    alive=_publisher_task is not None and not _publisher_task.done()
    db=db_url().split('@')[-1] if '@' in db_url() else '?'
    import hashlib
    db_hash=hashlib.sha256(db_url().encode()).hexdigest()[:10]
    # диагностика экспорта: есть ли таблица и сколько заданий ждут
    export_info='n/a'
    recent=[]
    try:
        with psycopg.connect(db_url()) as conn, conn.cursor() as cur:
            cur.execute("""SELECT status, count(*) FROM cd_exports GROUP BY status""")
            counts = {r[0]: r[1] for r in cur.fetchall()}
            cur.execute("""SELECT kind, format, status, error_text FROM cd_exports
            ORDER BY created_at DESC LIMIT 5""")
            recent = cur.fetchall()
            export_info = ', '.join(f'{k}={v}' for k, v in counts.items()) or 'пусто'
    except Exception as exc:
        export_info=f'❌ таблицы нет: {str(exc)[:120]}'
    recent_txt = '\n'.join(f'  #{r[0]}.{r[1]} → {r[2]}' + (f' ({str(r[3])[:80]})' if r[3] else '') for r in recent) or '  (нет)'
    bot_analytics = publisher.BOT_ANALYTICS_LAST_RESULT
    bot_analytics_info = f"синхронизаций: {publisher.BOT_ANALYTICS_RUNS}, каналов: {bot_analytics.get('ok', 0)}, ошибок: {len(bot_analytics.get('errors', []))}" if bot_analytics else 'не запускалась'
    last_run = publisher.LAST_RUN_AT
    last_run_txt = f'{int(time.time()-last_run)} с назад' if last_run else 'никогда'
    # проверка библиотек, необходимых для экспорта
    libs = {}
    for lib in ('openpyxl', 'fpdf', 'aiogram', 'psycopg'):
        try:
            mod = __import__(lib)
            libs[lib] = getattr(mod, '__version__', '?')
        except Exception:
            libs[lib] = 'НЕТ'
    uptime = int(time.time() - _process_started)
    await message.answer(f'Publisher: {"✅ работает" if alive else "❌ не запущен"}\n'
                         f'Интервал: {publisher.POLL_INTERVAL} с\n'
                         f'БД: {db}\n'
                         f'БД-хэш: {db_hash}\n'
                         f'Цикл: последний {last_run_txt}, ошибок: {publisher.RUN_ERRORS}, экспорт-вызовов: {publisher.EXPORTS_RUNS}\n'
                         f'Bot API аналитика: {bot_analytics_info}, Pulse отправлено: {publisher.PULSES_RUNS}, заявок уведомлено: {publisher.SLOT_NOTIFICATIONS_RUNS}\n'
                         f'Процесс: PID {os.getpid()}, uptime {uptime} с\n'
                         f'Библиотеки: openpyxl {libs["openpyxl"]}, fpdf {libs["fpdf"]}, aiogram {libs["aiogram"]}\n'
                         f'Экспорты: {export_info}\n'
                         f'Последние:\n{recent_txt}\n'
                         f'Код: {BOT_CODE_VERSION}')

@router.message(CommandStart())
async def start(message:Message):
    await send_entry_message(message)


@router.callback_query(F.data=='check_required_subscription')
async def check_required_subscription(callback:CallbackQuery):
    state=await access_state(callback.bot,callback.from_user.id)
    if state['allowed']:
        await callback.answer('Подписка подтверждена ✅')
        if callback.message:
            await send_entry_message(callback.message,user_id=callback.from_user.id)
        return
    if state['closed']:
        await callback.answer('Подписка подтверждена. Бот пока в разработке.',show_alert=True)
        if callback.message:
            await callback.message.edit_text(DEVELOPMENT_TEXT,reply_markup=development_keyboard())
        return
    if state['subscribed'] is None:
        await callback.answer('Не удалось проверить подписку. Попробуйте ещё раз.',show_alert=True)
        return
    await callback.answer('Подписка пока не найдена. Сначала подпишитесь на канал.',show_alert=True)

@router.channel_post()
async def channel_post_received(message: Message):
    from bot.bot_api_analytics import save_channel_post
    await asyncio.to_thread(save_channel_post, message)

@router.edited_channel_post()
async def channel_post_edited(message: Message):
    from bot.bot_api_analytics import save_channel_post
    await asyncio.to_thread(save_channel_post, message)

@router.message_reaction_count()
async def channel_reactions_updated(update: MessageReactionCountUpdated):
    from bot.bot_api_analytics import save_reaction_update
    await asyncio.to_thread(save_reaction_update, update)

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
    # Автомиграция при старте: применяет неприменённые миграции (идемпотентно).
    try:
        await asyncio.to_thread(migrate.apply_pending_migrations)
    except Exception as exc:
        logger.warning('migration check skipped: %s', exc)
    bot=Bot(token);dp=Dispatcher();dp.include_router(router)
    # Фоновый publisher-цикл в том же процессе (Bothost: один Python Worker).
    # Отдельное соединение на цикл — безопасно с aiogram.
    global _publisher_task
    _publisher_task=asyncio.create_task(publisher.loop())
    try:
        await dp.start_polling(bot,allowed_updates=['message','my_chat_member','channel_post','edited_channel_post','message_reaction_count'])
    finally:
        _publisher_task.cancel()
        try: await _publisher_task
        except (asyncio.CancelledError, Exception): pass

if __name__=='__main__': asyncio.run(main())

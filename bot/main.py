from __future__ import annotations
import asyncio,json,logging,os,time
from pathlib import Path
import psycopg
from aiogram import Bot,Dispatcher,F,Router
from aiogram.enums import ChatMemberStatus,ChatType
from aiogram.filters import Command,CommandStart
from aiogram.types import CallbackQuery,ChatMemberUpdated,FSInputFile,InlineKeyboardButton,InlineKeyboardMarkup,Message,MessageReactionCountUpdated,WebAppInfo
from bot.access import access_state,required_channel_url
from bot.db import db_url
from bot.forward_capture import router as forward_router
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


WELCOME_IMAGE=Path(__file__).resolve().parents[1]/'assets'/'welcome_channeldesk.png'
WELCOME_CAPTION='''👋 Добро пожаловать в ChannelDesk!

ChannelDesk помогает управлять Telegram-каналами в одном месте:
• создавать и планировать посты;
• принимать рекламные заявки;
• работать с командой;
• следить за публикациями и размещениями.

Выберите нужный раздел ниже.'''
WELCOME_CLOSED_CAPTION='''👋 Добро пожаловать в ChannelDesk!

Сейчас бот находится в закрытом тестировании. Мы готовим запуск и постепенно открываем доступ.

Пока можно посмотреть, как будет работать ChannelDesk, и следить за обновлениями в нашем канале.'''
WELCOME_ABOUT_TEXT='''🧭 О ChannelDesk

ChannelDesk — рабочее пространство для владельцев Telegram-каналов.

В нём можно управлять контентом, рекламными размещениями, командой и каналами без постоянной путаницы в чатах.'''
WELCOME_HELP_TEXT='''📖 Как пользоваться

1. Подключите Telegram-канал в Mini App.
2. Создайте рабочее пространство.
3. Для быстрого черновика просто перешлите сообщение, фото, видео или документ этому боту.
4. Выберите канал — бот соберёт черновик.
5. Откройте черновик, проверьте текст и запланируйте публикацию.

Посты не публикуются автоматически после пересылки.'''
WELCOME_FORWARD_TEXT='''📥 Быстрый черновик

1. Найдите нужный пост в Telegram.
2. Нажмите «Переслать».
3. Выберите этот бот.
4. Если каналов несколько — выберите нужный канал.

Один пересланный альбом сохранится одним черновиком со всеми вложениями.'''


def welcome_keyboard(open_app:bool)->InlineKeyboardMarkup:
    rows=[
        [InlineKeyboardButton(text='О ChannelDesk',callback_data='welcome:about'),InlineKeyboardButton(text='Как пользоваться',callback_data='welcome:help')],
    ]
    if open_app:
        rows.append([InlineKeyboardButton(text='Переслать → черновик',callback_data='welcome:forward')])
        url=os.getenv('MINI_APP_URL','').strip()
        if url:
            rows.append([InlineKeyboardButton(text='Открыть Mini App',web_app=WebAppInfo(url=url))])
    rows.append([InlineKeyboardButton(text='Канал обновлений',url=required_channel_url())])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def welcome_back_keyboard()->InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='← Назад',callback_data='welcome:back')]])


async def send_welcome(message:Message,user_id:int,state:dict|None=None):
    state=state or await access_state(message.bot,user_id)
    open_app=bool(state.get('allowed') and not state.get('closed'))
    caption=WELCOME_CAPTION if open_app else WELCOME_CLOSED_CAPTION
    keyboard=welcome_keyboard(open_app)
    try:
        if WELCOME_IMAGE.exists():
            await message.answer_photo(FSInputFile(str(WELCOME_IMAGE)),caption=caption,reply_markup=keyboard)
        else:
            await message.answer(caption,reply_markup=keyboard)
    except Exception as exc:
        logger.warning('welcome image could not be sent: %s',str(exc)[:180])
        await message.answer(caption,reply_markup=keyboard)


async def send_entry_message(message:Message,invite_token:str|None=None,user_id:int|None=None):
    state=await access_state(message.bot,user_id if user_id is not None else message.from_user.id)
    if not state['allowed']:
        if state['closed']:
            await send_welcome(message,user_id if user_id is not None else message.from_user.id,state)
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
    await send_welcome(message,user_id if user_id is not None else message.from_user.id,state)


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


async def edit_welcome_message(message:Message,text:str,markup:InlineKeyboardMarkup):
    try:
        if message.photo:
            await message.edit_caption(caption=text,reply_markup=markup)
        else:
            await message.edit_text(text,reply_markup=markup)
    except Exception:
        await message.answer(text,reply_markup=markup)


@router.callback_query(F.data=='check_required_subscription')
async def check_required_subscription(callback:CallbackQuery):
    state=await access_state(callback.bot,callback.from_user.id)
    if state['allowed']:
        await callback.answer('Подписка подтверждена ✅')
        if callback.message:
            await edit_welcome_message(callback.message,'✅ Подписка подтверждена.',InlineKeyboardMarkup(inline_keyboard=[]))
            await send_welcome(callback.message,callback.from_user.id,state)
        return
    if state['closed']:
        await callback.answer('Подписка подтверждена. Бот пока в разработке.',show_alert=True)
        if callback.message:
            await edit_welcome_message(callback.message,'✅ Подписка подтверждена.',InlineKeyboardMarkup(inline_keyboard=[]))
            await send_welcome(callback.message,callback.from_user.id,state)
        return
    if state['subscribed'] is None:
        await callback.answer('Не удалось проверить подписку. Попробуйте ещё раз.',show_alert=True)
        return
    await callback.answer('Подписка пока не найдена. Сначала подпишитесь на канал.',show_alert=True)


@router.callback_query(F.data.startswith('welcome:'))
async def welcome_action(callback:CallbackQuery):
    action=(callback.data or '').split(':',1)[1]
    if not callback.message:
        await callback.answer()
        return
    await callback.answer()
    if action=='about':
        await edit_welcome_message(callback.message,WELCOME_ABOUT_TEXT,welcome_back_keyboard())
    elif action=='help':
        await edit_welcome_message(callback.message,WELCOME_HELP_TEXT,welcome_back_keyboard())
    elif action=='forward':
        await edit_welcome_message(callback.message,WELCOME_FORWARD_TEXT,welcome_back_keyboard())
    elif action=='back':
        state=await access_state(callback.bot,callback.from_user.id)
        if state['allowed'] or state['closed']:
            caption=WELCOME_CAPTION if state['allowed'] else WELCOME_CLOSED_CAPTION
            await edit_welcome_message(callback.message,caption,welcome_keyboard(bool(state['allowed'])))
        elif state['subscribed'] is None:
            await edit_welcome_message(callback.message,SUBSCRIPTION_CHECK_ERROR,subscription_keyboard())
        else:
            await edit_welcome_message(callback.message,SUBSCRIPTION_GATE_TEXT,subscription_keyboard())

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
    bot=Bot(token);dp=Dispatcher();dp.include_router(forward_router);dp.include_router(router)
    # Фоновый publisher-цикл в том же процессе (Bothost: один Python Worker).
    # Отдельное соединение на цикл — безопасно с aiogram.
    global _publisher_task
    _publisher_task=asyncio.create_task(publisher.loop())
    try:
        await dp.start_polling(bot,allowed_updates=['message','callback_query','my_chat_member','channel_post','edited_channel_post','message_reaction_count'])
    finally:
        _publisher_task.cancel()
        try: await _publisher_task
        except (asyncio.CancelledError, Exception): pass

if __name__=='__main__': asyncio.run(main())

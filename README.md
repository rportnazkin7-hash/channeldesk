# ChannelDesk Bot

aiogram 3 publisher и уведомления для платформы ChannelDesk.
Хостится на **Bothost** как Python Worker.

## Структура

- `bot/` — aiogram 3 бот (long polling)
- `migrations/` + `migrate.py` — SQL-миграции для общей БД Supabase
- `tests/test_bot.py` — тесты бота
- `docs/` — документация

## Переменные окружения (Bothost)

```text
BOT_TOKEN=<токен @channel_desk_bot>
DATABASE_URL=<Supabase URL>
MINI_APP_URL=https://channeldesk.vercel.app
ADMIN_IDS=<Telegram ID владельца>
SUPABASE_URL=<необязательно для медиа из пересланных сообщений>
SUPABASE_ANON_KEY=<необязательно для медиа из пересланных сообщений>
REQUIRED_CHANNEL=@thechanneldesk
REQUIRED_CHANNEL_URL=https://t.me/thechanneldesk
ZBT_ENABLED=true
```

## Настройки Bothost

```text
Runtime: Python
Type: Worker
Python: 3.11
Entry point: bot/main.py
Requirements: requirements.txt
```

## Быстрый черновик из Telegram

Перешлите боту сообщение, фото, видео или документ. Бот предложит рабочее пространство и канал, создаст пост со статусом `draft` и даст кнопку «Открыть черновик». Публикация автоматически не запускается. Медиа сохраняются в Supabase Storage при наличии `SUPABASE_URL` и `SUPABASE_ANON_KEY`; иначе publisher использует Telegram `file_id`.

## Publisher (очередь публикаций, Этап B)

`bot/publisher.py` публикует посты со статусом `scheduled` в подключённые каналы
(не позднее ~60 секунд после срока). Publisher **запускается автоматически внутри
основного бота** (`bot/main.py` создаёт фоновый цикл через `asyncio.create_task`),
отдельный worker на Bothost не требуется.

Достаточно одной настройки Bothost:

```text
Runtime: Python
Type: Worker
Python: 3.11
Entry point: bot/main.py
Requirements: requirements.txt
```

## Проверка

```bash
python -m pip install -r requirements.txt
python -m pytest tests/ -q
```

> Frontend и FastAPI backend живут в репозитории **channeldesk_web** (Vercel) — здесь их нет,
> поэтому Bothost не определяет проект как Node.js и не пытается запускать Python через Node.

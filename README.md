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
```

## Настройки Bothost

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

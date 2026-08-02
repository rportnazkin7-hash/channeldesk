# Обновление handoff — 2026-08-03

Продолжение разработки ChannelDesk (Этап A завершён в коде). AI Sphere не затрагивался.

## Что сделано в этом сеансе

1. **Проверен фактический `main`** GitHub:
   - `api/channels.py`, `src/api.ts`, `migrations/003_channel_connections.sql`,
     `my_chat_member` handler в `bot/main.py` — присутствуют.
   - Отсутствовали `.gitignore`, `.env.example`, `tests/` — добавлены.
2. **Локальный коммит `92da12d`** (ещё не запушен — нет write-доступа у агента):
   - `api/rbac.py` — централизованная матрица прав (`require_action`);
   - `api/telegram.py` — live-проверка прав бота через `getChatMember`
     непосредственно перед подключением канала (в dev без `BOT_TOKEN` — fallback на сохранённые права);
   - `api/workspaces.py` — `POST /api/invites/accept`, `GET /api/workspaces/{id}/audit`,
     `channel_scope` в приглашениях;
   - `api/channels.py` — подключение канала переведено на live-проверку + RBAC;
   - `tests/` — 35 pytest-тестов (auth, rbac, invites, channels, telegram, workspaces), все зелёные;
   - `src/App.tsx` + `src/api.ts` — панель «Команда» (участники, создание приглашения, копирование токена);
   - `README.md` — документация API.

## Проверено

- `npm run typecheck` — ок;
- `npm run build` — ок;
- `python -m py_compile api/*.py bot/*.py migrate.py tests/*.py` — ок;
- `pytest tests/ -q` — 35 passed;
- smoke-маршруты: все API-эндпоинты регистрируются.

## Осталось (операционные шаги владельца)

1. **Push**: дать агенту write-доступ (интеграция GitHub в Agent Mode) → `git push origin main`.
2. **Supabase**: убедиться в SQL Editor, что выполнены миграции 001–003
   (таблицы `cd_channel_connections` и др.).
3. **Повтор события Telegram** (бот уже запущен владельцем):
   - удалить `@channel_desk_bot` из администраторов тестового канала;
   - снова добавить (выдать публикацию, редактирование, удаление);
   - проверить личное уведомление и появление канала в Mini App (`/api/channel-connections/pending`);
   - подключить канал — теперь перед подключением идёт live-проверка `getChatMember`.
4. **Проверка приглашений**: создать приглашение через Mini App, принять токен через
   `POST /api/invites/accept` (после подключения к боту можно сделать глубокую ссылку `/start invite_...`).

## Следующий этап

Этап B — публикации: миграции `cd_posts`, `cd_post_versions`, `cd_post_comments`,
`cd_content_assets`, `cd_post_templates`; редактор, статусы, календарь, очередь публикации
и надёжный publisher (см. docs/PRODUCT_SPEC.md и раздел 9 handoff).

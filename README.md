# ChannelDesk

Независимая Telegram-платформа для агентств, редакций и владельцев сеток каналов.

## Возможности

- несколько рабочих пространств и каналов;
- роли и доступ сотрудников;
- редактор, версии и согласование публикаций;
- контент-календарь и надёжная очередь публикации;
- рекламодатели, бронирования и ERID;
- доходы, расходы и экспорт;
- медиакиты, задачи, напоминания и аудит.

## Архитектура

- `src/` — React/Vite Mini App;
- `api/` — FastAPI API для Vercel;
- `bot/` — aiogram 3 publisher и уведомления;
- `migrations/` — версионируемые SQL-миграции PostgreSQL;
- `tests/` — backend-тесты (pytest);
- `docs/` — продуктовая и техническая документация.

Проект создан с нуля и не зависит от AI Sphere.

## API (Этап A)

Авторизация: заголовок `X-Telegram-Init-Data` (валидный Telegram WebApp initData)
или `X-Dev-Api-Key` (только при `DEV_API_KEY` в окружении, не в production).

```text
GET    /api/health
GET    /api/workspaces
POST   /api/workspaces
GET    /api/workspaces/{id}
PATCH  /api/workspaces/{id}
GET    /api/workspaces/{id}/members
POST   /api/workspaces/{id}/invites          # role, max_uses, expires_in_days, channel_scope
POST   /api/invites/accept                    # {token}
GET    /api/workspaces/{id}/audit             # журнал действий (?limit=50, максимум 200)

GET    /api/channel-connections/pending
GET    /api/workspaces/{id}/channels
POST   /api/workspaces/{id}/channels/connect  # {connection_id} — live-проверка getChatMember
```

Права проверяются централизованной матрицей в `api/rbac.py`.

## Тесты

```bash
python -m pip install -r requirements.txt
python -m pytest tests/ -q
```

Frontend:

```bash
npm ci
npm run typecheck
npm run build
```

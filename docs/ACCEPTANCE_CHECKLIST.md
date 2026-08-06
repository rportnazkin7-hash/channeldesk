# ChannelDesk — приёмка production

## Перед релизом

- [ ] `git status` чистый в обоих репозиториях.
- [ ] Web: `npm ci && npm run typecheck && npm run build`.
- [ ] Web: `python -m pytest tests/ -q`.
- [ ] Bot: `python -m pytest tests/ -q`.
- [ ] Есть свежий backup Supabase:

```bash
DATABASE_URL='...' ./scripts/backup_database.sh
sha256sum -c backups/*.sha256
```

Секрет не записывать в командную историю и не отправлять в чат.

## После деплоя web

Проверить:

```text
https://channeldesk.vercel.app/api/health
https://channeldesk.vercel.app/api/health/migrations
https://channeldesk.vercel.app/api/health/storage
```

Ожидаемо:

- `/api/health` возвращает `ok: true` и версию `0.47.0`;
- миграции содержат `001`–`016`, `019`–`028`;
- storage показывает настроенные `SUPABASE_URL` и `SUPABASE_ANON_KEY`.

## Smoke-тест Mini App

- [ ] Открытие через `@channel_desk_bot` передаёт Telegram initData.
- [ ] Переключение рабочего пространства не смешивает данные.
- [ ] Канал подключается только после live-проверки прав бота.
- [ ] Черновик проходит workflow: согласование → одобрение → расписание.
- [ ] Рекламный пост из брони редактируется: текст, кнопки, вложения.
- [ ] Опубликованный пост удаляется из Telegram через очередь и подтверждение.
- [ ] Оплаченная бронь публикуется один раз.
- [ ] Неоплаченная бронь не публикуется.
- [ ] Publisher отправляет уведомления о `active`, `overdue`, `cancelled`.
- [ ] Analytics показывает только доступные Bot API показатели.
- [ ] Публичный отчёт рекламодателя открывается без Telegram initData.
- [ ] Ссылка кампании редиректит на целевой URL и увеличивает счётчик переходов.
- [ ] Экспорт приходит от бота документом.

## Smoke-тест Partner API

- [ ] `/docs` и `/openapi.json` открываются через Vercel.
- [ ] В Mini App → «Ещё → Интеграции» создаётся API-ключ.
- [ ] `GET /api/v1/me` возвращает workspace и scopes.
- [ ] `GET /api/v1/workspaces/{id}/channels` возвращает активные каналы.
- [ ] `POST /api/v1/workspaces/{id}/drafts` создаёт черновик.
- [ ] Повтор того же запроса с тем же `Idempotency-Key` не создаёт дубль.
- [ ] Webhook получает `post.created` и проверяется по HMAC-SHA256.

## Smoke-тест Public Newsdesk

- [ ] «Ещё → Приём новостей» создаёт публичную ссылку.
- [ ] Форма открывается без Telegram initData.
- [ ] Текстовая заявка создаёт пост `source=public_news` со статусом `draft`.
- [ ] Фото/видео прикрепляются к черновику через Supabase Storage.
- [ ] Владелец получает уведомление в Telegram с кнопкой открытия черновика.
- [ ] Анонимная заявка не раскрывает контакт в уведомлении.
- [ ] Отключённая ссылка возвращает 404.

## Smoke-тест Bot onboarding

- [ ] `/start` неподписанного пользователя показывает ОП.
- [ ] После проверки подписки показывается welcome-картинка и inline-меню.
- [ ] Владелец из `ADMIN_IDS` получает полный доступ во время ЗБТ.
- [ ] Пересылка одного сообщения создаёт один черновик.
- [ ] Пересылка альбома создаёт один черновик со всеми вложениями.

## Откат

1. Не делать `git reset --hard` на production.
2. Зафиксировать проблемный commit и логи Vercel/Bothost.
3. Вернуть предыдущий commit через обычный revert или выбрать предыдущий deployment в Vercel.
4. Bothost откатить на предыдущий commit и перезапустить Worker.
5. Миграции не откатывать автоматически: база должна двигаться вперёд отдельной исправляющей миграцией.
6. После отката снова проверить `/api/health/migrations` и smoke-тест публикации.

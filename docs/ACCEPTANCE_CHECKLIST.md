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

- `/api/health` возвращает `ok: true` и текущую версию;
- миграции содержат `001`–`016`, `019`, `020`, `021`;
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
- [ ] Экспорт приходит от бота документом.

## Откат

1. Не делать `git reset --hard` на production.
2. Зафиксировать проблемный commit и логи Vercel/Bothost.
3. Вернуть предыдущий commit через обычный revert или выбрать предыдущий deployment в Vercel.
4. Bothost откатить на предыдущий commit и перезапустить Worker.
5. Миграции не откатывать автоматически: база должна двигаться вперёд отдельной исправляющей миграцией.
6. После отката снова проверить `/api/health/migrations` и smoke-тест публикации.

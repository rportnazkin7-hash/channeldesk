# ChannelDesk — release audit 2026-08-06

## Итог

Архитектура готова к закрытому и ограниченному публичному релизу после smoke-теста на production. Полная гарантия «не ляжет при любом количестве пользователей» невозможна без отдельного нагрузочного стенда, поэтому перед массовым открытием нужно проверить реальную конфигурацию Supabase/Vercel/Bothost.

## Что проверено

- Web/API: 164 pytest-теста.
- Bot: 45 pytest-тестов.
- TypeScript typecheck.
- Vite production build.
- npm audit: 0 high/critical vulnerabilities.
- Синтаксис Python и дубли миграций Web/Bot.
- Runtime не использует TGStat, Telemetr или MTProto.
- `SUPABASE_SERVICE_ROLE_KEY` удалён из release-конфигурации.
- Добавлена система баг-репортов из Bot и Mini App.

## Что улучшено

- Пул соединений PostgreSQL для Vercel API (`psycopg_pool`, максимум 4 соединения на экземпляр).
- Один `workspace snapshot` вместо множества параллельных запросов Mini App при обновлении.
- Локальный rate limit Partner API: 120 запросов в минуту на API-ключ.
- Ограничение публичной формы Newsdesk: 20 заявок за 10 минут на страницу.
- Вложения Public Newsdesk привязываются только к своей странице и имеют срок ожидания.
- Webhook-доставки выполняются параллельно максимум к пяти endpoints.
- Добавлен `/api/v1/me` для безопасной проверки API-ключа.
- Исправлена маршрутизация `/docs`, `/redoc` и `/openapi.json` на Vercel.
- Исправлен путь миграций в Bot Worker.
- Версия release: Web/API `0.47.0`, Bot `bot-api-newsdesk-0.47.0`.

## Перед production-релизом

1. Redeploy Web и Bot.
2. Проверить `/api/health` — ожидается версия `0.47.0`.
3. Проверить миграции `027_partner_api`, `028_public_newsdesk` и `029_bug_reports`.
4. Проверить `DB_POOL_ENABLED=true` на Vercel.
5. Убедиться, что `DEV_API_KEY` не задан в production.
6. Убедиться, что в production нет `SUPABASE_SERVICE_ROLE_KEY`.
7. Выполнить backup Supabase.
8. Пройти `docs/ACCEPTANCE_CHECKLIST.md`.

## Известные ограничения

- Publisher остаётся одним Worker и публикует посты последовательно — это безопаснее против дублей, но при большой очереди увеличит задержку.
- Webhook сейчас best-effort: для массового Partner API позже нужен persistent outbox с повторными попытками.
- Нагрузочный тест 100/300/1000 одновременных пользователей ещё не проводился.
- Внешние медиа Partner API должны быть доступны по публичному HTTPS URL.

Эти ограничения не блокируют закрытый beta и первый ограниченный релиз, но должны быть закрыты перед масштабированием.

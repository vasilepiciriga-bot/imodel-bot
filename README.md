# iModel — Telegram AI Photo Bot

Пайплайн: Telegram фото/промпт → Face Lock v2 → GPT refine (опционально) → Replicate Nano Banana → S3 → ответ пользователю. Дополнительный enhancer в рабочей цепочке не используется.

## Что включено
- Быстрый Telegram webhook: update принимается с `200`, обработка уходит в background task.
- Durable state: users, credits, stats, jobs и audit log пишутся в Postgres при наличии `DATABASE_URL`; S3/local JSON остаются fallback.
- Grants: роли `owner`, `admin`, `operator`, `support`, `publisher`, `user`, `banned`; bootstrap owner берётся из `ADMIN_IDS`.
- Structured logs: ключевые события идут JSON-логами с hash для Telegram IDs.
- Mini App: `/webapp` и API `/api/v1/webapp/session`, `/api/v1/me`, `/api/v1/generations`, `/api/v1/gallery`.

## Запуск
1) Создать бота в @BotFather → получить BOT_TOKEN.  
2) Ключи:
   - OpenAI → OPENAI_API_KEY (можно отключить GPT переменной DISABLE_GPT_REFINE=1)
   - Replicate → REPLICATE_API_TOKEN
   - Backblaze B2 S3 → S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET (Public bucket)
   - Railway Postgres → DATABASE_URL
3) Залить репозиторий на GitHub.
4) Railway → New Project → Deploy from GitHub.
5) Railway → Variables → вставить переменные из .env.example.
6) Settings → Domains → взять URL и вписать в WEBHOOK_BASE.
7) Restart/Deploy.
8) В Telegram: /start → селфи → описание → получаешь фото.

Команды: `/start` `/help` `/lang` `/buy` `/balance` `/presets` `/copy` `/gallery` `/refer` `/app`.

Админ-команды: `/grant <telegram_id> <role>`, `/credits <telegram_id> <delta>`.

Проверки: `python3 -m py_compile app.py` и `python3 -m pytest -q`.

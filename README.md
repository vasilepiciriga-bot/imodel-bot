# iModel Studio — Telegram AI Photo Bot

Пайплайн: Telegram фото/промпт → Face Lock v2 → GPT refine (опционально) → Replicate Nano Banana → S3 → ответ пользователю.

**v3.0** добавляет премиум-каталог photoshoots (`imodel/`), Mini App v2 (React), payment ledger, persistent gallery и расширенный API — за feature flags в `.env.example`.

## Что включено
- Telegram webhook + Stars (legacy `pack_10` / `pack_30` / `pack_100` сохранены).
- Copy Mode (scene lock + reference image).
- Postgres: users, credits, jobs, styles, payments, gallery (при `DATABASE_URL`).
- Mini App: `/webapp` (embedded HTML или React build при `WEBAPP_V2_STATIC=1`).
- API: `/api/v1/styles`, `/packs`, `/packages`, `/trends`, `/events/style`, generations, gallery.
- Admin: `/admin?secret=` + payment/style metrics при ledger.

## Feature flags (включайте по одному)
| Переменная | Эффект |
|------------|--------|
| `STYLE_CATALOG_V2=1` | API каталога 30+ commercial photoshoots |
| `USE_PROMPT_BUILDER=1` | Промпты из каталога при генерации |
| `WEBAPP_V2_STATIC=1` | React Mini App из `webapp/dist` |
| `PAYMENT_LEDGER_V2=1` | Idempotent Stars payments в Postgres |
| `NEW_STAR_PACKAGES=1` | Пакеты Starter/Creator/Pro/Max в /buy |
| `PERSISTENT_GALLERY=1` | Галерея 50 результатов в БД |

## Mini App build
```bash
cd webapp && npm install && npm run build
```
Затем `WEBAPP_V2_STATIC=1` на Railway.

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

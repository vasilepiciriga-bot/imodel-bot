# iModel — Telegram AI Photo Bot

Пайплайн: Telegram фото/промпт → job → GPT/Vision (опционально) → Replicate Nano Banana → S3 original/Telegram copy → доставка в Telegram.

Бот нормализует результат под лимиты Telegram `sendPhoto` и автоматически падает назад на `sendDocument`, если Telegram отклоняет фото.

## Запуск
1) Создать бота в @BotFather → получить BOT_TOKEN.  
2) Ключи:
   - OpenAI → OPENAI_API_KEY (можно отключить GPT переменной GPT_OFF=1)
   - Replicate → REPLICATE_API_TOKEN
   - Backblaze B2 S3 → S3_ENDPOINT, S3_ACCESS_KEY_ID, S3_SECRET_ACCESS_KEY, S3_BUCKET
   - METRICS_SECRET и ADMIN_PANEL_SECRET для `/metrics` и `/admin`
   - PUBLIC_API_SECRET для `/api/v1/*`
3) Залить репозиторий на GitHub.
4) Railway → New Project → Deploy from GitHub.
5) Railway → Variables → вставить переменные из .env.example.
6) Settings → Domains → взять URL и вписать в WEBHOOK_BASE.
7) Restart/Deploy.
8) В Telegram: /start → селфи → описание → получаешь фото.

Webhook использует `X-Telegram-Bot-Api-Secret-Token`; старый `?secret=` отключён по умолчанию.

Команды: /start /help /lang /clear /copy /presets /gallery /refer /pricing /buy /balance /diag.
Поддержка языков: RU / EN / RO / DE.

## API
Минимальные endpoints для будущих клиентов:
- `POST /api/v1/generations` — создать generation job (`prompt`, `image_b64` или `image_url`)
- `GET /api/v1/generations/{job_id}` — статус и output URLs
- `GET /api/v1/me/credits?chat_id=...` — баланс

Передавайте `X-API-Key: PUBLIC_API_SECRET`.

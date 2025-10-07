# iModel — Telegram AI Photo Bot

Пайплайн: запрос → GPT (опционально) → Replicate InstantID → Real-ESRGAN → выгрузка в S3 → ответ пользователю.

## Запуск
1) Создать бота в @BotFather → получить BOT_TOKEN.  
2) Ключи:
   - OpenAI → OPENAI_API_KEY (можно отключить GPT переменной GPT_OFF=1)
   - Replicate → REPLICATE_API_TOKEN
   - Backblaze B2 S3 → S3_ENDPOINT, S3_ACCESS_KEY, S3_SECRET_KEY, S3_BUCKET (Public bucket)
3) Залить репозиторий на GitHub.
4) Railway → New Project → Deploy from GitHub.
5) Railway → Variables → вставить переменные из .env.example.
6) Settings → Domains → взять URL и вписать в WEBHOOK_BASE.
7) Restart/Deploy.
8) В Telegram: /start → селфи → описание → получаешь фото.

Команды: /start /help /lang /delete (MVP)  
Поддержка языков: RU / EN / RO.

## Важно: один вебхук на бота
- У Telegram-бота может быть только один активный webhook на один `BOT_TOKEN`.
- Если вы запускаете два инстанса с одним `BOT_TOKEN`, последний запущенный перезапишет вебхук у первого.
- Для второй копии (например, воркер без приёма апдейтов) выставьте `DISABLE_WEBHOOK=1`, чтобы не трогать вебхук основной копии.

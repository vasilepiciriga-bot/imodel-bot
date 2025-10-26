# iModel — Telegram AI Photo Bot

Пайплайн (по умолчанию):
- селфи + текст → GPT‑refine (опционально) → Replicate (NanoBanana) → (опц.) Real‑ESRGAN → ответ пользователю (байты)
- Copy Mode: стиль‑фото → Vision‑GPT строит детальный промпт → селфи + промпт → Replicate (NanoBanana)

По умолчанию вся генерация идёт через основную модель (NanoBanana).

## Запуск
1) Создать бота в @BotFather → получить `BOT_TOKEN`.
2) Настроить переменные окружения (см. `.env.example`):
   - Telegram: `BOT_TOKEN`, `WEBHOOK_BASE`, `WEBHOOK_SECRET`
   - Replicate: `REPLICATE_API_TOKEN`
   - Модели Replicate: `NANOBANANA_MODEL` (по умолчанию `google/nano-banana`), `ESRGAN_MODEL`
   - OpenAI (опционально): `OPENAI_API_KEY`, `OPENAI_MODEL`, `OPENAI_MODEL_VISION`
   - S3 (опционально, для presign): `S3_ENDPOINT`, `S3_REGION`, `S3_ACCESS_KEY_ID`, `S3_SECRET_ACCESS_KEY`, `S3_BUCKET`
   - (Опционально) другие модели Replicate — задавайте slug/версию своей модели
3) Deploy на Railway/Render/другой хостинг.
4) Вставить переменные окружения из `.env.example`.
5) `WEBHOOK_BASE` = публичный HTTPS URL вашего приложения. Вебхук принимает секрет либо как query `/?secret=...`, либо как заголовок `X-Telegram-Bot-Api-Secret-Token`.
6) Перезапустить.
7) В Telegram: `/start` → селфи → описание → получить фото.

Команды: `/start`, `/help`, `/lang`, `/presets`, `/buy`, `/promo`, `/balance`, `/gallery`, `/refer`, `/gender`  
Поддержка языков: RU / EN / RO / DE

## Важно
- У Telegram‑бота может быть только один активный вебхук на `BOT_TOKEN`. Если у вас второй инстанс — установите `DISABLE_WEBHOOK=1` для него.
- Если используете секрет для вебхука — сервер принимает его как query‑параметр или как заголовок (официальный способ Telegram).

## Copy Mode
1) Отправьте фото‑стиль (сцена).  
2) Отправьте селфи.  
Бот использует Vision‑GPT, чтобы построить детальный промпт, затем генерирует новую фотографию с вашим лицом в той же сцене. Стиль‑фото не отправляется в модель как второй вход — это исключает «наклейку лица» поверх исходного человека.

## Советы по идентичности
- Команда `/gender male|female` фиксирует пол в промпте и негатив‑промпте, уменьшая дрейф пола.
 

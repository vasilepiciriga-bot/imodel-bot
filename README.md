# Interior PRO Telegram Bot (aiogram 3.x)

Telegram‑бот с AI‑пайплайном для улучшения интерьерных фотографий уровня топ‑фотосъёмки гостиниц/архитектуры. Интерьер (мебель/декор) не меняется. Есть два режима «очистки мелочей»: авто и ручной (inpainting по сетке).

Основные этапы
- A — Img2Img (Replicate, FLUX.1‑dev/SDXL), низкий strength, сохранение геометрии
- B — Upscale x2 (Real‑ESRGAN) + локальный постпроцесс (вертикали → denoise → micro‑contrast → WB)
- C — Очистка мелочей:
  - C1 Авто: детект мелких объектов → сшивка маленьких масок → inpaint (LaMa)
  - C2 Ручной: сетка 6×6, ввод ячеек (например: B2,C2,C3) → предпросмотр → применить

Установка
1) Python 3.11+
2) Установить зависимости:
   pip install -r requirements.txt
3) Создать .env (см. .env.example) и заполнить:
   - TELEGRAM_TOKEN — токен бота от @BotFather
   - REPLICATE_API_TOKEN — токен Replicate
   - (опц.) IMG_MODEL/UPSCALE_MODEL/INPAINT_MODEL, GRID_ROWS/COLS

Запуск
- python -m bot.main

Токены/секреты
- Локально — через .env
- В GitHub Actions — через Secrets → TELEGRAM_TOKEN, REPLICATE_API_TOKEN

Как пользоваться
- Нажмите кнопку «🏨 Интерьер PRO» → отправьте фото интерьера
- По умолчанию включена «🧹 Авто‑очистка». Для ручной очистки — «🧽 Ручная очистка» и укажите ячейки сетки
- Выбирайте баланс белого (тёплый/нейтральный/холодный) и повтор запуска (seed ±1)

import os
# Загрузка переменных окружения из .env (для локального запуска)
from dotenv import load_dotenv
load_dotenv()

# Чтение необходимых секретных ключей из окружения
BOT_TOKEN = os.getenv("BOT_TOKEN")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

if not BOT_TOKEN or not REPLICATE_API_TOKEN:
    # Предупреждение, если не указаны токены (в продакшн можно вместо этого вызывать ошибку)
    print("Предупреждение: переменные окружения BOT_TOKEN или REPLICATE_API_TOKEN не заданы.")

# Настройка пути для вебхука.
# WEBHOOK_URL – публичный URL вашего приложения (должен быть настроен в переменных окружения, например на Railway).
PUBLIC_URL = os.getenv("WEBHOOK_URL")
if PUBLIC_URL:
    PUBLIC_URL = PUBLIC_URL.rstrip("/")  # убираем завершающий слэш, если есть
    WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
    WEBHOOK_URL = PUBLIC_URL + WEBHOOK_PATH
else:
    WEBHOOK_PATH = f"/webhook/{BOT_TOKEN}"
    WEBHOOK_URL = None

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

# Настройка webhook совпадает с app.py: один POST "/" и секрет в Telegram header.
WEBHOOK_BASE = (os.getenv("WEBHOOK_BASE") or "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "secret123")
WEBHOOK_URL = f"{WEBHOOK_BASE}/" if WEBHOOK_BASE else None

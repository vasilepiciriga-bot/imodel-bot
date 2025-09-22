"""
README — How to run
====================

1) Install dependencies:
   pip install -r requirements.txt

2) Create .env in project root with at least:
   TELEGRAM_TOKEN=123456:ABC...
   REPLICATE_API_TOKEN=r8_xxx

   # Optional overrides (sensible defaults used if not set)
   IMG_MODEL=black-forest-labs/FLUX.1-dev
   UPSCALE_MODEL=xinntao/real-esrgan
   INPAINT_MODEL=jiahui/laminpaint

3) Launch bot:
   python -m bot.main

This bot adds a new flow: "🏨 Интерьер PRO" with two cleanup modes (auto & manual inpainting)
and a high-quality interior photography pipeline.
"""

import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from bot.config import settings
from bot.handlers.interior import router as interior_router


async def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
    bot = Bot(token=settings.TELEGRAM_TOKEN, parse_mode=ParseMode.HTML)
    dp = Dispatcher(storage=MemoryStorage())

    dp.include_router(interior_router)

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())


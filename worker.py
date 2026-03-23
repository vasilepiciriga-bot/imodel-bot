import os
import json
import asyncio
from typing import Optional

from queue_utils import get_redis, Q_UPSCALE, enqueue_upscale, enqueue_dead

# Import app environment and helpers (bot, stats, download, etc.)
from app import bot, _download_with_retries, ESRGAN_MODEL, ESRGAN_DISABLED, DISABLE_ESRGAN, replicate_generate, stats_incr
from aiogram.types import BufferedInputFile

MAX_RETRIES_UPSCALE = int(os.getenv("MAX_RETRIES_UPSCALE", "2"))

async def process_upscale(job: dict) -> None:
    chat_id = int(job.get("chat_id"))
    gen_url = str(job.get("gen_url"))
    caption = str(job.get("caption") or "✅")
    status_msg_id = job.get("status_message_id")
    attempt = int(job.get("attempt") or 0)

    if not gen_url or (not ESRGAN_MODEL) or DISABLE_ESRGAN or ESRGAN_DISABLED:
        # Just resend the original as a fallback
        b = _download_with_retries(gen_url)
        if b:
            try:
                await bot.send_photo(chat_id, BufferedInputFile(b, filename="imodel_result.jpg"), caption=caption)
                stats_incr("finals", 1)
            except Exception:
                pass
        return

    try:
        up_url = replicate_generate(ESRGAN_MODEL, {"image": gen_url, "scale": 4, "face_enhance": False, "model": "RealESRGAN_x4plus"})
        b = None
        if up_url and up_url.startswith("http"):
            b = _download_with_retries(up_url)
        if not b:
            b = _download_with_retries(gen_url)
        if b:
            await bot.send_photo(chat_id, BufferedInputFile(b, filename="imodel_result.jpg"), caption=caption)
            stats_incr("finals", 1)
        # Clean status message
        if status_msg_id:
            try:
                await bot.delete_message(chat_id, status_msg_id)
            except Exception:
                pass
    except Exception as e:
        # Retry with simple backoff, then fallback
        if attempt < MAX_RETRIES_UPSCALE:
            try:
                await asyncio.sleep(max(1, 2 ** attempt))
                await enqueue_upscale(chat_id, gen_url, caption=caption, status_message_id=status_msg_id, attempt=attempt+1)
                return
            except Exception:
                pass
        # Push to DLQ
        try:
            await enqueue_dead("upscale", job, reason="max_retries", error=str(e))
        except Exception:
            pass
        try:
            b = _download_with_retries(gen_url)
            if b:
                await bot.send_photo(chat_id, BufferedInputFile(b, filename="imodel_result.jpg"), caption=caption + " (fallback)")
                stats_incr("finals", 1)
        except Exception:
            pass
        # Clean status message
        if status_msg_id:
            try:
                await bot.delete_message(chat_id, status_msg_id)
            except Exception:
                pass

async def run_worker():
    r = await get_redis()
    if not r:
        print("Redis not configured; worker idle.")
        return
    print("Worker: listening on", Q_UPSCALE)
    while True:
        try:
            item = await r.blpop(Q_UPSCALE, timeout=5)
            if not item:
                await asyncio.sleep(0.2)
                continue
            _q, payload = item
            try:
                job = json.loads(payload)
            except Exception:
                continue
            kind = job.get("kind")
            if kind == "upscale":
                await process_upscale(job)
        except Exception as e:
            print("worker loop error:", str(e)[:200])
            await asyncio.sleep(1.0)

if __name__ == "__main__":
    asyncio.run(run_worker())

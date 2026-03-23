import os
import json
from typing import Optional

try:
    from redis import asyncio as aioredis
except Exception:  # pragma: no cover
    aioredis = None

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
Q_UPSCALE = os.getenv("REDIS_Q_UPSCALE", "q:upscale")

_redis: Optional[aioredis.Redis] = None

async def get_redis() -> Optional["aioredis.Redis"]:
    global _redis
    if aioredis is None:
        return None
    if _redis is None:
        _redis = await aioredis.from_url(REDIS_URL, encoding="utf-8", decode_responses=True)
    return _redis

async def enqueue_upscale(chat_id: int, gen_url: str, caption: str = "✅", status_message_id: int | None = None, attempt: int = 0) -> bool:
    r = await get_redis()
    if not r:
        return False
    payload = json.dumps({
        "kind": "upscale",
        "chat_id": int(chat_id),
        "gen_url": gen_url,
        "caption": caption,
        "status_message_id": int(status_message_id) if status_message_id else None,
        "attempt": int(attempt),
    })
    await r.rpush(Q_UPSCALE, payload)
    return True

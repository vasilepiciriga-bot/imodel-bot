import os
import json
from typing import Optional

try:
    from redis import asyncio as aioredis
except Exception:  # pragma: no cover
    aioredis = None

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")
Q_UPSCALE = os.getenv("REDIS_Q_UPSCALE", "q:upscale")
Q_UPSCALE_DLQ = os.getenv("REDIS_Q_UPSCALE_DLQ", "q:upscale:dlq")

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

async def enqueue_dead(kind: str, job: dict, reason: str = "error", error: str | None = None) -> bool:
    r = await get_redis()
    if not r:
        return False
    try:
        import time
        payload = json.dumps({
            "kind": str(kind),
            "reason": str(reason),
            "error": (str(error) if error else None),
            "ts": int(time.time()),
            "job": job,
        })
        await r.rpush(Q_UPSCALE_DLQ, payload)
        # keep DLQ bounded (best-effort): trim to last 200
        try:
            await r.ltrim(Q_UPSCALE_DLQ, -200, -1)
        except Exception:
            pass
        return True
    except Exception:
        return False

async def queues_snapshot(max_items: int = 10) -> dict:
    r = await get_redis()
    if not r:
        return {"enabled": False}
    out = {"enabled": True, "upscale_len": 0, "dlq_len": 0, "dlq": []}
    try:
        out["upscale_len"] = int(await r.llen(Q_UPSCALE))
        out["dlq_len"] = int(await r.llen(Q_UPSCALE_DLQ))
        raw = await r.lrange(Q_UPSCALE_DLQ, -max_items, -1)
        items = []
        for s in raw or []:
            try:
                items.append(json.loads(s))
            except Exception:
                continue
        out["dlq"] = items
    except Exception:
        pass
    return out

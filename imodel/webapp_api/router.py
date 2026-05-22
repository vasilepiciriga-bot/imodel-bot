"""Studio API v1 — additive routes (Phase 3+)."""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from imodel.config.packages import list_all_packages
from imodel.config.settings import feature_enabled
from imodel.styles import get_pack, list_packs, list_styles, list_trending
from imodel.styles.commercial_styles import get_style
from imodel.trends.trend_catalog import TREND_CATEGORIES, styles_for_category
from imodel.trends.viral_style_packs import VIRAL_PACKS
from imodel.webapp_api import deps


def _public_style(s: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "key": s["key"],
        "name": s["name"],
        "category": s["category"],
        "commercial_angle": s.get("commercial_angle"),
        "audience": s.get("audience", []),
        "use_case": s.get("use_case", []),
        "trend_level": s.get("trend_level"),
        "price_credits": s.get("price_credits", 4),
        "is_premium": s.get("is_premium", True),
        "is_trending": s.get("is_trending", False),
        "prompt_version": s.get("prompt_version"),
    }


def create_studio_router() -> APIRouter:
    router = APIRouter(prefix="/api/v1")

    @router.get("/styles")
    async def api_styles(category: Optional[str] = None):
        items = [_public_style(s) for s in list_styles(category=category)]
        return {"items": items}

    @router.get("/styles/trending")
    async def api_styles_trending():
        return {"items": [_public_style(s) for s in list_trending()]}

    @router.get("/styles/{style_key}")
    async def api_style_detail(style_key: str):
        s = get_style(style_key)
        if not s:
            return JSONResponse({"error": "not_found"}, status_code=404)
        return {"style": _public_style(s)}

    @router.get("/packs")
    async def api_packs():
        return {"items": list_packs()}

    @router.get("/packages")
    async def api_packages():
        premium = feature_enabled("NEW_STAR_PACKAGES")
        if premium:
            return {"items": list_all_packages(premium_only=True), "legacy": list_all_packages(legacy_only=True)}
        return {"items": list_all_packages(legacy_only=True)}

    @router.get("/trends")
    async def api_trends():
        cats = {}
        for cat, keys in TREND_CATEGORIES.items():
            cats[cat] = [k for k in keys if get_style(k)]
        return {"categories": cats, "viral_packs": VIRAL_PACKS}

    @router.get("/trends/weekly")
    async def api_trends_weekly():
        path = deps.get("weekly_trends_path")
        text = ""
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    text = f.read()
            except Exception:
                pass
        return {"markdown": text, "updated_at": time.time()}

    @router.post("/events/style")
    async def api_style_event(request: Request):
        user = deps.get("webapp_user_from_request")(request)
        if not user:
            return JSONResponse({"error": "unauthorized"}, status_code=403)
        data = await request.json()
        uid = int(user["uid"])
        style_key = str(data.get("style_key") or "")
        event = str(data.get("event") or "viewed")
        job_id = data.get("job_id")
        execute = deps.get("db_execute")
        if execute and feature_enabled("STYLE_CATALOG_V2"):
            execute(
                "INSERT INTO imodel_style_events(uid, style_key, event, job_id, created_at) VALUES (%s, %s, %s, %s, %s)",
                (uid, style_key, event, job_id, time.time()),
            )
        return {"ok": True}


    @router.post("/gallery/{result_id}/delete")
    async def api_gallery_delete(result_id: int, request: Request):
        user = deps.get("webapp_user_from_request")(request)
        if not user:
            return JSONResponse({"error": "unauthorized"}, status_code=403)
        if not feature_enabled("PERSISTENT_GALLERY"):
            return JSONResponse({"error": "disabled"}, status_code=404)
        from imodel.db import gallery as gallery_db
        uid = int(user["uid"])
        ok = gallery_db.soft_delete(deps.get("db_execute"), result_id, uid)
        return {"ok": ok}

    @router.post("/generations/{job_id}/regenerate")
    async def api_regenerate(job_id: str, request: Request):
        user = deps.get("webapp_user_from_request")(request)
        if not user:
            return JSONResponse({"error": "unauthorized"}, status_code=403)
        uid = int(user["uid"])
        jobs = deps.get("JOBS") or {}
        job = jobs.get(job_id)
        if not job or int(job.get("chat_id") or 0) != uid:
            return JSONResponse({"error": "not_found"}, status_code=404)
        record_job = deps.get("record_job")
        if not record_job:
            return JSONResponse({"error": "unavailable"}, status_code=503)
        import asyncio
        new_job = record_job(
            kind="regenerate",
            status="queued",
            chat_id=uid,
            username=str(user.get("username") or ""),
            prompt=str(job.get("prompt") or ""),
            model=job.get("model"),
            image_bytes=job.get("image_bytes"),
            style_key=job.get("style_key"),
            lang=str(job.get("lang") or "en"),
        )
        runner = deps.get("run_webapp_generation_job")
        if runner:
            asyncio.create_task(runner(str(new_job["job_id"])))
        return {"job_id": new_job["job_id"], "status": "queued"}

    @router.post("/generations/{job_id}/upscale")
    async def api_upscale(job_id: str, request: Request):
        user = deps.get("webapp_user_from_request")(request)
        if not user:
            return JSONResponse({"error": "unauthorized"}, status_code=403)
        return {"ok": True, "status": "queued", "note": "HD upscale placeholder — enable in a future release"}


    return router

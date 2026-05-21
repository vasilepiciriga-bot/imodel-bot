from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional

from imodel.config.packages import list_packages
from imodel.config.settings import get_settings
from imodel.db import gallery as gallery_db
from imodel.db import styles as styles_db
from imodel.trends.trend_catalog import get_trending_categories, get_weekly_trends


def handle_list_styles(trending: bool = False, category: Optional[str] = None) -> Dict[str, Any]:
    if not get_settings().style_catalog_v2:
        return {"items": [], "enabled": False}
    return {"items": styles_db.list_from_db(trending_only=trending, category=category), "enabled": True}


def handle_style_detail(style_key: str) -> Optional[Dict[str, Any]]:
    if not get_settings().style_catalog_v2:
        return None
    return styles_db.get_from_db(style_key)


def handle_list_packs() -> Dict[str, Any]:
    rows = styles_db.list_from_db()
    categories: Dict[str, List[Dict[str, Any]]] = {}
    for s in rows:
        cat = s.get("category", "General")
        categories.setdefault(cat, []).append(s)
    bundles = [
        {"key": "money_profile_pack", "name": "Money Profile Pack", "style_keys": ["linkedin_premium", "ceo_portrait", "founder_portrait"], "credits_total": 10},
        {"key": "dating_pack", "name": "Dating Pack", "style_keys": ["golden_hour_dating", "coffee_date", "natural_smile"], "credits_total": 8},
        {"key": "luxury_status_pack", "name": "Luxury Status Pack", "style_keys": ["old_money_portrait", "ceo_after_dark", "quiet_luxury"], "credits_total": 12},
    ]
    return {"categories": categories, "bundles": bundles}


def handle_list_packages(include_premium: bool = True) -> Dict[str, Any]:
    return {"packages": list_packages(include_premium=include_premium)}


def handle_trends() -> Dict[str, Any]:
    if not get_settings().style_catalog_v2:
        return {"trending": [], "categories": []}
    return {
        "trending": styles_db.list_from_db(trending_only=True),
        "categories": get_trending_categories(),
    }


def handle_weekly_trends() -> Dict[str, Any]:
    return {"items": get_weekly_trends(), "week_note": "Featured photoshoots this week"}


def handle_gallery(uid: int, job_items: List[Dict[str, Any]]) -> Dict[str, Any]:
    persisted = gallery_db.list_for_user(uid)
    if persisted:
        return {"items": persisted, "source": "database"}
    return {"items": job_items, "source": "jobs"}


def handle_gallery_delete(uid: int, result_id: str) -> bool:
    return gallery_db.soft_delete(uid, result_id)


def handle_record_style_event(uid: int, style_key: str, event: str, meta: Optional[Dict[str, Any]] = None) -> None:
    gallery_db.record_style_event(uid, style_key, event, meta)


def handle_regenerate(
    parent_job: Dict[str, Any],
    uid: int,
) -> Dict[str, Any]:
    return {
        "prompt": parent_job.get("prompt") or "",
        "style_key": parent_job.get("style_key"),
        "lang": parent_job.get("lang", "en"),
        "parent_job_id": parent_job.get("job_id"),
    }


def resolve_prompt_for_request(
    prompt: str,
    style_key: Optional[str],
    lang: str,
) -> tuple[str, int]:
    from imodel.ai.generation_service import resolve_generation_prompt
    return resolve_generation_prompt(prompt, style_key=style_key, lang=lang)

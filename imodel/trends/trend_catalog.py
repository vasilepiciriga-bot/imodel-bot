from __future__ import annotations

from typing import Any, Dict, List

from imodel.db import styles as styles_db


WEEKLY_FEATURED_KEYS = [
    "old_money_portrait",
    "linkedin_glow_up",
    "ceo_after_dark",
    "90s_studio_flash",
    "golden_hour_dating",
    "euro_summer",
    "dubai_mood",
    "copy_any_style",
]


def get_weekly_trends() -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for key in WEEKLY_FEATURED_KEYS:
        s = styles_db.get_from_db(key)
        if s and s.get("is_active", True):
            out.append(s)
    return out


def get_trending_categories() -> List[str]:
    return ["Business", "Dating", "Luxury", "Cinematic", "Viral"]

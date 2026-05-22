"""Viral trend groupings for Trend Lab (Phase 9 UI)."""

from __future__ import annotations

VIRAL_PACKS: dict[str, dict] = {
    "this_week_viral": {
        "title": "Trending this week",
        "style_keys": [
            "old_money_portrait",
            "linkedin_glow_up",
            "nineties_studio_flash",
            "ceo_after_dark",
            "golden_hour_dating",
        ],
    },
    "business_money": {
        "title": "Business money looks",
        "style_keys": [
            "linkedin_premium",
            "ceo_portrait",
            "founder_portrait",
            "speaker_profile",
        ],
    },
    "dating_upgrade": {
        "title": "Dating upgrade",
        "style_keys": [
            "golden_hour_dating",
            "natural_smile",
            "coffee_date",
            "elegant_evening",
        ],
    },
}

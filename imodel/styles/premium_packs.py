"""Commercial style bundles for Stars / credits merchandising."""

from __future__ import annotations

from typing import Any

PACKS: dict[str, dict[str, Any]] = {
    "money_profile_pack": {
        "key": "money_profile_pack",
        "name": "Money Profile Pack",
        "commercial_promise": "Look professional, expensive, and trustworthy.",
        "style_keys": [
            "linkedin_premium",
            "ceo_portrait",
            "founder_portrait",
            "real_estate_agent",
            "consultant_look",
            "podcast_guest",
        ],
        "price_stars": 599,
        "price_credits": 18,
        "category": "Business",
    },
    "dating_upgrade_pack": {
        "key": "dating_upgrade_pack",
        "name": "Dating Upgrade Pack",
        "commercial_promise": "Better profile photos without looking fake.",
        "style_keys": [
            "golden_hour_dating",
            "coffee_date",
            "natural_smile",
            "urban_confidence",
            "weekend_lifestyle",
            "elegant_evening",
        ],
        "price_stars": 599,
        "price_credits": 18,
        "category": "Dating",
    },
    "luxury_status_pack": {
        "key": "luxury_status_pack",
        "name": "Luxury Status Pack",
        "commercial_promise": "See yourself in a luxury editorial world.",
        "style_keys": [
            "old_money_portrait",
            "luxury_hotel_lobby",
            "dubai_mood",
            "rooftop_night",
            "private_jet_mood",
            "ceo_after_dark",
        ],
        "price_stars": 999,
        "price_credits": 35,
        "category": "Luxury",
    },
    "viral_tiktok_pack": {
        "key": "viral_tiktok_pack",
        "name": "Viral TikTok Pack",
        "commercial_promise": "Trending looks made for social media.",
        "style_keys": [
            "nineties_studio_flash",
            "linkedin_glow_up",
            "passport_glow_up",
            "euro_summer",
        ],
        "price_stars": 999,
        "price_credits": 35,
        "category": "Viral",
    },
    "copy_any_style_pack": {
        "key": "copy_any_style_pack",
        "name": "Copy Any Style Pack",
        "commercial_promise": "Any photo style. Your face. One tap.",
        "style_keys": [],  # Uses USER_COPY_MODE flow, not style_key list
        "price_stars": 999,
        "price_credits": 12,
        "credits_per_result": 4,
        "category": "Copy Mode",
        "note": "Preserves app.py Copy Mode until COPY_MODE_V2 pricing (Phase 7).",
    },
}


def get_pack(pack_key: str) -> dict[str, Any] | None:
    return PACKS.get(pack_key)


def list_packs() -> list[dict[str, Any]]:
    return list(PACKS.values())

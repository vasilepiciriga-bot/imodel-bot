"""Trend category index — references commercial style keys."""

from __future__ import annotations

TREND_CATEGORIES: dict[str, list[str]] = {
    "Business Money": [
        "linkedin_premium",
        "ceo_portrait",
        "founder_portrait",
        "real_estate_agent",
        "consultant_look",
        "beauty_master_profile",
        "podcast_guest",
        "speaker_profile",
    ],
    "Dating / Social": [
        "golden_hour_dating",
        "coffee_date",
        "natural_smile",
        "urban_confidence",
        "weekend_lifestyle",
        "elegant_evening",
    ],
    "Luxury / Status": [
        "old_money_portrait",
        "quiet_luxury",
        "luxury_hotel_lobby",
        "dubai_mood",
        "rooftop_night",
        "private_jet_mood",
        "ceo_after_dark",
    ],
    "Cinematic": [
        "dark_hero",
        "noir_portrait",
        "rainy_street",
        "movie_poster",
        "royal_drama",
    ],
    "TikTok / Viral": [
        "nineties_studio_flash",
        "linkedin_glow_up",
        "passport_glow_up",
        "euro_summer",
    ],
    "Seasonal": [
        "christmas_portrait",
        "valentine_dating",
    ],
    "Local Europe": [
        "linkedin_premium",
        "founder_portrait",
        "quiet_luxury",
        "coffee_date",
    ],
}

# Safe commercial aliases for raw social trends (see TREND_OPERATIONS_PLAYBOOK.md)
TREND_SAFE_ALIASES: dict[str, str] = {
    "mob_wife": "elegant_evening",
    "corporate_villain": "ceo_after_dark",
    "old_money": "old_money_portrait",
    "ai_yearbook": "passport_glow_up",
}


def styles_for_category(category: str) -> list[str]:
    return list(TREND_CATEGORIES.get(category, []))


def safe_style_for_trend(trend_slug: str) -> str | None:
    return TREND_SAFE_ALIASES.get(trend_slug.lower().replace(" ", "_"))

"""Map legacy app.py PRESETS indices/keys to commercial style_key (Phase 7 migration)."""

from __future__ import annotations

# PRESETS[].key in app.py → style_key in imodel catalog
PRESET_KEY_TO_STYLE_KEY: dict[str, str] = {
    "studio_soft": "studio_soft_v1",  # not in first 30; fallback linkedin until added
    "cinematic": "dark_hero",
    "golden_hour": "golden_hour_dating",
    "editorial_highkey": "linkedin_premium",
    "bw_film": "noir_portrait",
    "kodak_portra": "natural_smile",
    "beauty_dish": "beauty_master_profile",
    "headshot": "linkedin_premium",
    "neon_night": "urban_confidence",
    "cafe": "coffee_date",
    "forest": "weekend_lifestyle",
    "beach": "euro_summer",
    "architecture": "consultant_look",
    "luxury_interior": "luxury_hotel_lobby",
    "rain_window": "rainy_street",
    "snow": "christmas_portrait",
    "rembrandt": "ceo_portrait",
    "soft_glam": "elegant_evening",
    "vintage70": "nineties_studio_flash",
    "mono_hicon": "noir_portrait",
    "park": "weekend_lifestyle",
    "fitness": "urban_confidence",
    "garage": "dark_hero",
    "bookstore": "coffee_date",
}


def style_key_for_preset(preset_key: str) -> str:
    return PRESET_KEY_TO_STYLE_KEY.get(preset_key, preset_key)

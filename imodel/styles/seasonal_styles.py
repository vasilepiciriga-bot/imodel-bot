"""Seasonal photoshoot seeds (Phase 1 placeholders — expand via trend ops)."""

from __future__ import annotations

from typing import Any

from imodel.styles.commercial_styles import _style

SEASONAL_STYLES: dict[str, dict[str, Any]] = {
    s["key"]: s
    for s in [
        _style(
            "christmas_portrait",
            "Christmas Portrait",
            "Seasonal",
            "Warm holiday portrait without kitsch overload.",
            "Holiday portrait with subtle festive atmosphere, elegant styling.",
            "Warm fairy light bokeh, soft key on face.",
            "85mm portrait, cozy framing.",
            "Winter coat or festive elegant outfit, no cartoon props.",
            "Soft indoor holiday decor blur.",
            "Warm, celebratory, premium holiday card.",
            trend_level="medium",
            is_trending=False,
            sort_order=200,
        ),
        _style(
            "valentine_dating",
            "Valentine Dating",
            "Seasonal",
            "Romantic seasonal dating upgrade.",
            "Valentine-inspired portrait, romantic soft mood, genuine smile.",
            "Rose-toned warm light, soft glow.",
            "85mm romantic portrait.",
            "Date-night elegant outfit, red accents subtle not costume.",
            "Restaurant candles or floral blur background.",
            "Romantic, seasonal, dating-ready.",
            sort_order=201,
            use_case=["dating"],
        ),
    ]
}


def get_seasonal_style(key: str) -> dict[str, Any] | None:
    return SEASONAL_STYLES.get(key)

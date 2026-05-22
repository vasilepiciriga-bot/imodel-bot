"""Score commercial style objects before exposing in Mini App catalog."""

from __future__ import annotations

import re
from typing import Any

_BANNED_NAME_PATTERNS = [
    r"\bjohn\s*wick\b",
    r"\bjames\s*bond\b",
    r"\bthomas\s*shelby\b",
    r"\bcelebrity\b",
    r"\bgucci\b",
    r"\blv\b",
    r"\bnike\b",
]

_NSFW_TERMS = {"nudity", "nude", "nsfw", "sexual", "erotic", "topless"}
_WEAPON_TERMS = {"weapon", "gun", "rifle", "knife", "violence"}


def _collect_text(style: dict[str, Any]) -> str:
    """Creative copy only — negative_prompt lists forbidden terms by design."""
    keys = (
        "name",
        "base_prompt",
        "lighting",
        "camera",
        "clothing",
        "background",
        "mood",
        "commercial_angle",
    )
    parts = [str(style.get(k) or "") for k in keys]
    return " ".join(parts).lower()


def score_prompt(style: dict[str, Any]) -> dict[str, Any]:
    warnings: list[str] = []
    recommendations: list[str] = []
    score = 100

    text = _collect_text(style)

    for pattern in _BANNED_NAME_PATTERNS:
        if re.search(pattern, text, re.I):
            warnings.append(f"Banned reference matched: {pattern}")
            score -= 25

    for term in _NSFW_TERMS:
        if term in text:
            warnings.append(f"NSFW term: {term}")
            score -= 30

    for term in _WEAPON_TERMS:
        if term in text:
            warnings.append(f"Violence/weapon term: {term}")
            score -= 25

    required = ("key", "name", "category", "base_prompt", "identity_lock", "negative_prompt")
    for field in required:
        if field == "negative_prompt":
            if not str(style.get(field) or "").strip():
                warnings.append(f"Missing required field: {field}")
                score -= 10
        elif not style.get(field):
            warnings.append(f"Missing required field: {field}")
            score -= 10

    for component in ("lighting", "camera", "clothing", "background", "mood"):
        if not style.get(component):
            recommendations.append(f"Add more detail: {component}")
            score -= 3

    if not style.get("commercial_angle"):
        recommendations.append("Add commercial_angle for merchandising")
        score -= 5

    if style.get("price_credits", 0) <= 0:
        warnings.append("price_credits should be positive")
        score -= 5

    score = max(0, min(100, score))

    if score >= 92 and not warnings:
        grade = "A+"
    elif score >= 80 and len(warnings) <= 1:
        grade = "A"
    elif score >= 65:
        grade = "B"
    else:
        grade = "C"

    return {
        "score": score,
        "grade": grade,
        "warnings": warnings,
        "recommendations": recommendations,
    }


def is_catalog_ready(style: dict[str, Any]) -> bool:
    result = score_prompt(style)
    return result["grade"] in ("A+", "A") and style.get("is_active", True)

"""Assemble final generation prompts from commercial style objects."""

from __future__ import annotations

import hashlib
import re
from typing import Any

from imodel.prompts.base_identity import BASE_IDENTITY_LOCK
from imodel.prompts.negative_prompts import BASE_NEGATIVE, merge_negative
from imodel.prompts.prompt_versions import get_active_version
from imodel.styles.commercial_styles import get_style

_INTENSITY_MODIFIERS = {
    "natural": "Natural understated polish, soft realistic skin, believable lifestyle finish.",
    "premium": "Premium editorial finish, crisp detail, flattering professional styling.",
    "cinematic": "Cinematic dramatic grade, rich contrast, moody atmospheric depth, film still quality.",
}

_GENDER_MODIFIERS = {
    "keep": "",
    "slight_polish": "Subtle grooming polish only, preserve natural features.",
    "strong_editorial": "Strong editorial styling while strictly preserving facial identity.",
}


def _sanitize_user_description(text: str | None) -> str:
    if not text:
        return ""
    cleaned = " ".join(text.split())
    if len(cleaned) > 400:
        cleaned = cleaned[:400].rstrip() + "..."
    banned = ("nude", "naked", "nsfw", "celebrity", "child", "minor")
    lower = cleaned.lower()
    for term in banned:
        if term in lower:
            return ""
    return cleaned


def build_prompt(
    style_key: str,
    user_description: str | None = None,
    intensity: str = "premium",
    gender_mode: str = "keep",
    output_mode: str = "portrait",
    locale: str = "en",
) -> dict[str, Any]:
    style = get_style(style_key)
    if not style:
        raise KeyError(f"Unknown style_key: {style_key}")

    version = get_active_version(style_key, style.get("prompt_version"))
    identity = style.get("identity_lock") or BASE_IDENTITY_LOCK
    intensity_line = _INTENSITY_MODIFIERS.get(intensity, _INTENSITY_MODIFIERS["premium"])
    gender_line = _GENDER_MODIFIERS.get(gender_mode, "")

    segments = [
        style["base_prompt"],
        f"Lighting: {style.get('lighting', '')}",
        f"Camera: {style.get('camera', '')}",
        f"Wardrobe: {style.get('clothing', '')}",
        f"Background: {style.get('background', '')}",
        f"Mood: {style.get('mood', '')}",
        intensity_line,
        gender_line,
        identity,
    ]
    extra = _sanitize_user_description(user_description)
    if extra:
        segments.append(f"Additional direction: {extra}")

    if output_mode == "portrait":
        segments.append("Vertical portrait composition, subject clearly visible, professional photoshoot framing.")

    final_prompt = " ".join(s for s in segments if s and str(s).strip())
    final_prompt = re.sub(r"\s+", " ", final_prompt).strip()

    negative = merge_negative(style.get("negative_prompt") or "", BASE_NEGATIVE)
    safety_notes = list(style.get("safety_notes") or [])
    if locale and locale != "en":
        safety_notes.append(f"locale_hint={locale}")

    prompt_hash = hashlib.sha256(final_prompt.encode("utf-8")).hexdigest()[:16]
    negative_hash = hashlib.sha256(negative.encode("utf-8")).hexdigest()[:16]

    return {
        "final_prompt": final_prompt,
        "negative_prompt": negative,
        "prompt_version": version,
        "style_key": style_key,
        "price_credits": int(style.get("price_credits") or 1),
        "safety_notes": safety_notes,
        "final_prompt_hash": prompt_hash,
        "negative_prompt_hash": negative_hash,
        "ab_test_group": style.get("ab_test_group"),
    }

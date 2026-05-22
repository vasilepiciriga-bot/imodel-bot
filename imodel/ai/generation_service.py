"""Generation wrapper — prompt builder + job metadata (Phase 7)."""

from __future__ import annotations

from typing import Any, Dict, Optional, Tuple

from imodel.config.settings import feature_enabled
from imodel.prompts.prompt_builder import build_prompt
from imodel.styles.presets_legacy import style_key_for_preset


def resolve_generation_prompt(
    user_prompt: str,
    *,
    style_key: Optional[str] = None,
    preset_key: Optional[str] = None,
    intensity: str = "premium",
    locale: str = "en",
) -> Tuple[str, Dict[str, Any]]:
    meta: Dict[str, Any] = {"style_key": None, "prompt_version": None, "price_credits": 1}

    if feature_enabled("USE_PROMPT_BUILDER"):
        key = style_key
        if not key and preset_key:
            key = style_key_for_preset(preset_key)
        if key:
            built = build_prompt(key, user_description=user_prompt or None, intensity=intensity, locale=locale)
            meta.update(built)
            return built["final_prompt"], meta

    return user_prompt, meta


def copy_mode_credit_cost() -> int:
    if feature_enabled("COPY_MODE_V2"):
        return 4
    return 1

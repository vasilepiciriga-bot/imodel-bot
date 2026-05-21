"""Generation prompt resolution — wraps commercial prompt builder."""

from __future__ import annotations

from typing import Optional, Tuple

from imodel.config.settings import get_settings
from imodel.prompts import prompt_builder


def resolve_generation_prompt(
    user_prompt: str,
    style_key: Optional[str] = None,
    lang: str = "en",
) -> Tuple[str, int]:
    """
    Returns (prompt_text, credit_cost).
    Uses prompt builder when flag on and style_key provided.
    """
    settings = get_settings()
    if settings.use_prompt_builder and style_key:
        built = prompt_builder.build_prompt(style_key, lang=lang, extra_scene=user_prompt)
        if built:
            return built["prompt"], int(built.get("price_credits", 1))
    return user_prompt, 1

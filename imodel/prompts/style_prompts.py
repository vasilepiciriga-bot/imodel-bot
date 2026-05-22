"""Thin export of style-driven prompts (catalog lives in commercial_styles)."""

from imodel.prompts.prompt_builder import build_prompt
from imodel.styles.commercial_styles import get_style, list_styles, list_trending

__all__ = ["build_prompt", "get_style", "list_styles", "list_trending"]

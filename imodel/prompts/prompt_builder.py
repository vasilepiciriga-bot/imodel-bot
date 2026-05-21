"""Commercial photoshoot prompt builder."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from imodel.config.settings import get_settings
from imodel.prompts.base_identity import IDENTITY_LOCK
from imodel.prompts.negative_prompts import DEFAULT_NEGATIVE

_STYLES_CACHE: Optional[List[Dict[str, Any]]] = None


def _seed_path() -> Path:
    s = get_settings()
    return Path(s.styles_seed_path)


def _load_seed() -> List[Dict[str, Any]]:
    global _STYLES_CACHE
    if _STYLES_CACHE is not None:
        return _STYLES_CACHE
    path = _seed_path()
    if not path.is_file():
        _STYLES_CACHE = []
        return _STYLES_CACHE
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    _STYLES_CACHE = data if isinstance(data, list) else data.get("styles", [])
    return _STYLES_CACHE


def reload_styles() -> None:
    global _STYLES_CACHE
    _STYLES_CACHE = None
    _load_seed()


def list_styles(active_only: bool = True, min_quality: str = "B") -> List[Dict[str, Any]]:
    quality_order = {"A+": 4, "A": 3, "B": 2, "C": 1}
    min_q = quality_order.get(min_quality, 0)
    out: List[Dict[str, Any]] = []
    for s in _load_seed():
        if active_only and not s.get("is_active", True):
            continue
        q = s.get("quality_grade", "A")
        if quality_order.get(q, 0) < min_q:
            continue
        out.append(public_style(s))
    out.sort(key=lambda x: (not x.get("is_trending"), x.get("sort_order", 999)))
    return out


def public_style(style: Dict[str, Any]) -> Dict[str, Any]:
    """Strip internal prompt fields for API responses."""
    hidden = {"base_prompt", "identity_lock", "lighting", "camera", "clothing", "background", "mood", "negative_prompt", "safety_notes"}
    return {k: v for k, v in style.items() if k not in hidden}


def get_style(key: str) -> Optional[Dict[str, Any]]:
    for s in _load_seed():
        if s.get("key") == key:
            return dict(s)
    return None


def build_prompt(style_key: str, lang: str = "en", extra_scene: str = "") -> Optional[Dict[str, str]]:
    style = get_style(style_key)
    if not style:
        return None
    parts = [
        style.get("base_prompt", ""),
        style.get("lighting", ""),
        style.get("camera", ""),
        style.get("clothing", ""),
        style.get("background", ""),
        style.get("mood", ""),
    ]
    if extra_scene:
        parts.insert(0, extra_scene.strip())
    prompt_line = ", ".join(p.strip() for p in parts if p and str(p).strip())
    identity = style.get("identity_lock") or IDENTITY_LOCK
    prompt = f"{prompt_line}. {identity}".strip()
    negative = style.get("negative_prompt") or DEFAULT_NEGATIVE
    return {
        "prompt": " ".join(prompt.split()),
        "negative": negative,
        "style_key": style_key,
        "prompt_version": style.get("prompt_version", "v1.0"),
        "price_credits": int(style.get("price_credits", 1)),
    }


def style_prompt_text(style_key: str, extra_scene: str = "") -> Optional[str]:
    built = build_prompt(style_key, extra_scene=extra_scene)
    return built["prompt"] if built else None

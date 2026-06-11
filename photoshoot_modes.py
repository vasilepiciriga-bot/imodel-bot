"""
Photoshoot Mode System — single source of truth for all mode configs.
Imported by app.py.
"""
from __future__ import annotations
import random
from typing import Dict, Any, Optional

PHOTOSHOOT_MODES: Dict[str, Dict[str, Any]] = {
    "everyday": {
        "label": {"ru": "Обычный", "en": "Everyday", "de": "Standard", "ar": "عادي"},
        "emoji": "📸",
        "credits": 1,
        "n_generations": 1,
        "select_best": 1,
        "upscale": False,
        "upscale_factor": 2,
        "upscale_fidelity": 0.8,
        "prompt_layer": None,
        "is_premium": False,
        "requires_custom_prompt": False,
        "badge": None,
        "short_desc": {"ru": "Быстрое AI-фото", "en": "Fast AI photo"},
    },
    "premium": {
        "label": {"ru": "Премиум", "en": "Premium", "de": "Premium", "ar": "بريميوم"},
        "emoji": "💎",
        "credits": 3,
        "n_generations": 4,
        "select_best": 2,
        "upscale": True,
        "upscale_factor": 2,
        "upscale_fidelity": 0.8,
        "prompt_layer": None,
        "is_premium": True,
        "requires_custom_prompt": False,
        "badge": "popular",
        "short_desc": {
            "ru": "4 генерации, лучшие 2, апскейл",
            "en": "4 generations, best 2 selected, upscaled",
        },
    },
    "vogue": {
        "label": {"ru": "Vogue", "en": "Vogue", "de": "Vogue", "ar": "فوغ"},
        "emoji": "👑",
        "credits": 6,
        "n_generations": 8,
        "select_best": 3,
        "upscale": True,
        "upscale_factor": 4,
        "upscale_fidelity": 0.7,
        "prompt_layer": (
            "editorial Vogue magazine quality, high fashion avant-garde styling, "
            "luxury brand campaign, art director composition, ultra-premium photoshoot"
        ),
        "is_premium": True,
        "requires_custom_prompt": False,
        "badge": "best_quality",
        "short_desc": {
            "ru": "8 генераций, топ-3, 4x апскейл",
            "en": "8 generations, top 3, 4× upscale",
        },
    },
    "ceo": {
        "label": {"ru": "CEO", "en": "CEO", "de": "CEO", "ar": "CEO"},
        "emoji": "🤵",
        "credits": 4,
        "n_generations": 6,
        "select_best": 2,
        "upscale": True,
        "upscale_factor": 2,
        "upscale_fidelity": 0.8,
        "prompt_layer": (
            "corporate executive portrait, confident leadership presence, "
            "tailored business suit, authoritative gaze, LinkedIn-ready, boardroom or studio"
        ),
        "is_premium": True,
        "requires_custom_prompt": False,
        "badge": "for_business",
        "short_desc": {
            "ru": "Бизнес/LinkedIn/founder портреты",
            "en": "Business, LinkedIn, founder portraits",
        },
    },
    "dating": {
        "label": {"ru": "Dating", "en": "Dating", "de": "Dating", "ar": "مواعدة"},
        "emoji": "💫",
        "credits": 3,
        "n_generations": 4,
        "select_best": 2,
        "upscale": False,
        "upscale_factor": 2,
        "upscale_fidelity": 0.8,
        "prompt_layer": (
            "natural warm smile, approachable likeable personality, "
            "candid lifestyle photography, authentic relaxed look, social media quality"
        ),
        "is_premium": False,
        "requires_custom_prompt": False,
        "badge": None,
        "short_desc": {
            "ru": "Натуральные привлекательные фото",
            "en": "Natural attractive photos for dating/social",
        },
    },
    "luxury": {
        "label": {"ru": "Luxury", "en": "Luxury", "de": "Luxus", "ar": "فاخر"},
        "emoji": "✨",
        "credits": 4,
        "n_generations": 6,
        "select_best": 2,
        "upscale": True,
        "upscale_factor": 2,
        "upscale_fidelity": 0.8,
        "prompt_layer": (
            "ultra-luxury lifestyle editorial, five-star ambiance, "
            "old money elegance, opulent environment, Instagram-worthy, fashion forward"
        ),
        "is_premium": True,
        "requires_custom_prompt": False,
        "badge": "viral",
        "short_desc": {
            "ru": "Instagram, travel, old money, luxury",
            "en": "Instagram, travel, old money, luxury lifestyle",
        },
    },
    "custom": {
        "label": {"ru": "Свой стиль", "en": "Custom", "de": "Eigener Stil", "ar": "مخصص"},
        "emoji": "🎨",
        "credits": 5,
        "n_generations": 3,
        "select_best": 2,
        "upscale": True,
        "upscale_factor": 2,
        "upscale_fidelity": 0.8,
        "prompt_layer": None,
        "is_premium": True,
        "requires_custom_prompt": True,
        "badge": None,
        "short_desc": {
            "ru": "Опишите образ — AI создаёт prompt",
            "en": "Describe your vision, AI builds the prompt",
        },
    },
}


def get_mode_config(key: str) -> Dict[str, Any]:
    return PHOTOSHOOT_MODES.get(key, PHOTOSHOOT_MODES["everyday"])


def get_mode_credit_cost(key: str) -> int:
    return int(get_mode_config(key)["credits"])


def get_mode_label(key: str, lang: str = "en") -> str:
    cfg = get_mode_config(key)
    return str(cfg["label"].get(lang, cfg["label"].get("en", key)))


def apply_prompt_layer(base_prompt: str, mode_key: str) -> str:
    cfg = get_mode_config(mode_key)
    layer = cfg.get("prompt_layer")
    if layer:
        sep = ", " if base_prompt else ""
        return f"{base_prompt}{sep}{layer}"
    return base_prompt


def _score_candidate(img_bytes: bytes) -> float:
    """
    Stub candidate scorer for Generation Tournament.
    TODO: replace with GPT-4o Vision or CLIP-based judge.
    Heuristic: larger JPEG = more detail retained by encoder = rough quality proxy.
    """
    if not img_bytes:
        return 0.0
    size_score = min(len(img_bytes) / 500_000, 1.0) * 60.0
    noise_score = random.uniform(0.0, 40.0)
    return size_score + noise_score


STEP_LABELS: Dict[str, Dict[str, str]] = {
    "analyzing":      {"en": "Analyzing your selfie...", "ru": "Анализируем фото..."},
    "crafting_prompt":{"en": "Building your prompt...", "ru": "Создаём промпт..."},
    "selecting":      {"en": "Selecting best shots...", "ru": "Выбираем лучшие..."},
    "upscaling":      {"en": "Enhancing quality...",    "ru": "Улучшаем качество..."},
    "ready":          {"en": "Done!",                   "ru": "Готово!"},
}


def step_label_text(step_label: str, lang: str = "en") -> str:
    if step_label.startswith("generating_"):
        parts = step_label.split("_")
        if len(parts) == 4:
            current, total = parts[1], parts[3]
            if lang == "ru":
                return f"Генерируем {current} из {total}..."
            return f"Generating {current} of {total}..."
    entry = STEP_LABELS.get(step_label, {})
    return entry.get(lang, entry.get("en", "Processing..."))

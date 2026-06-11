"""
Photoshoot Mode System — single source of truth for all mode configs.
Phase 2: added style_variants (sub-style branching) and negative_layer per mode.
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
        "negative_layer": None,
        "style_variants": {},
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
        "prompt_layer": "professional portrait photography, studio lighting, sharp focus, magazine quality",
        "negative_layer": "snapshot, casual, blur, overexposed, grainy",
        "style_variants": {
            "studio": {
                "label": {"en": "Studio", "ru": "Студия"},
                "prompt_suffix": "neutral studio backdrop, soft box lighting, clean background",
            },
            "outdoor": {
                "label": {"en": "Outdoor", "ru": "На улице"},
                "prompt_suffix": "golden hour natural light, outdoor lifestyle, bokeh background",
            },
            "moody": {
                "label": {"en": "Moody", "ru": "Атмосферный"},
                "prompt_suffix": "dramatic shadows, cinematic Rembrandt lighting, rich tones",
            },
        },
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
        "negative_layer": (
            "casual clothing, outdoor snapshot, low contrast, amateur, overprocessed, "
            "flat lighting, Instagram filter"
        ),
        "style_variants": {
            "editorial": {
                "label": {"en": "Editorial", "ru": "Редакционный"},
                "prompt_suffix": "editorial spread, strong shadows, dramatic geometric composition, bold colors",
            },
            "street_fashion": {
                "label": {"en": "Street Fashion", "ru": "Уличный стиль"},
                "prompt_suffix": "street style, urban backdrop, motion blur background, candid elegance",
            },
            "minimal": {
                "label": {"en": "Minimalist", "ru": "Минимализм"},
                "prompt_suffix": "clean white studio, minimalist aesthetic, pure elegance, negative space",
            },
        },
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
        "negative_layer": (
            "casual outfit, t-shirt, unformal, blurry, overexposed, cluttered background, "
            "low resolution, distorted face"
        ),
        "style_variants": {
            "formal": {
                "label": {"en": "Formal Office", "ru": "Офис"},
                "prompt_suffix": "boardroom interior, floor-to-ceiling windows, city skyline behind",
            },
            "founder": {
                "label": {"en": "Founder", "ru": "Founder"},
                "prompt_suffix": "startup vibe, casual blazer, open-plan office, approachable leadership",
            },
            "outdoor": {
                "label": {"en": "Outdoor Executive", "ru": "На природе"},
                "prompt_suffix": "rooftop or garden terrace, natural light, relaxed confidence",
            },
        },
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
        "negative_layer": (
            "serious expression, stiff pose, corporate look, dark background, "
            "overfiltered, artificial makeup"
        ),
        "style_variants": {
            "casual": {
                "label": {"en": "Casual & Warm", "ru": "Повседневный"},
                "prompt_suffix": "coffee shop or park, casual outfit, genuine laugh, warm tones",
            },
            "travel": {
                "label": {"en": "Travel Vibe", "ru": "Путешествие"},
                "prompt_suffix": "scenic travel backdrop, adventure spirit, wanderlust lifestyle",
            },
            "social": {
                "label": {"en": "Social Media", "ru": "Соцсети"},
                "prompt_suffix": "Instagram-ready, lifestyle flat lay aesthetic, trendy location",
            },
        },
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
        "negative_layer": (
            "budget setting, casual clothes, plain background, tourist snapshot, "
            "overexposed, low quality"
        ),
        "style_variants": {
            "old_money": {
                "label": {"en": "Old Money", "ru": "Old Money"},
                "prompt_suffix": "estate garden, equestrian aesthetic, classic tailoring, muted palette",
            },
            "yacht": {
                "label": {"en": "Yacht & Travel", "ru": "Яхта & Travel"},
                "prompt_suffix": "Mediterranean coast, yacht deck, golden hour, azure sea backdrop",
            },
            "penthouse": {
                "label": {"en": "Penthouse", "ru": "Пентхаус"},
                "prompt_suffix": "luxury penthouse interior, city skyline at night, designer decor",
            },
        },
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
        "negative_layer": "blurry, low quality, distorted face, bad anatomy",
        "style_variants": {},
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


def get_mode_negative(key: str) -> str:
    """Return negative prompt layer for a mode, or empty string."""
    cfg = get_mode_config(key)
    return str(cfg.get("negative_layer") or "")


def get_style_variants(key: str) -> Dict[str, Any]:
    """Return style_variants dict for a mode."""
    cfg = get_mode_config(key)
    return cfg.get("style_variants", {})


def apply_prompt_layer(
    base_prompt: str,
    mode_key: str,
    style_variant: Optional[str] = None,
) -> str:
    """Combine base prompt with mode prompt_layer and optional sub-style suffix."""
    cfg = get_mode_config(mode_key)
    layer = cfg.get("prompt_layer")
    if layer:
        sep = ", " if base_prompt else ""
        result = f"{base_prompt}{sep}{layer}"
    else:
        result = base_prompt
    # Apply sub-style variant suffix if specified
    if style_variant:
        variants = cfg.get("style_variants", {})
        variant_cfg = variants.get(style_variant, {})
        suffix = str(variant_cfg.get("prompt_suffix", ""))
        if suffix:
            result = f"{result}, {suffix}" if result else suffix
    return result


def _score_candidate(img_bytes: bytes) -> float:
    """
    Stub candidate scorer for Generation Tournament.
    TODO Phase 3: replace with GPT-4o Vision or CLIP-based judge.
    Heuristic: larger JPEG = more detail retained by encoder = rough quality proxy.
    """
    if not img_bytes:
        return 0.0
    size_score = min(len(img_bytes) / 500_000, 1.0) * 60.0
    noise_score = random.uniform(0.0, 40.0)
    return size_score + noise_score


STEP_LABELS: Dict[str, Dict[str, str]] = {
    "analyzing":        {"en": "Analyzing your selfie...",    "ru": "Анализируем фото..."},
    "identity_scan":    {"en": "Reading your features...",    "ru": "Определяем черты лица..."},
    "crafting_prompt":  {"en": "Building your prompt...",     "ru": "Создаём промпт..."},
    "selecting":        {"en": "Selecting best shots...",     "ru": "Выбираем лучшие..."},
    "upscaling":        {"en": "Enhancing quality...",        "ru": "Улучшаем качество..."},
    "ready":            {"en": "Done!",                       "ru": "Готово!"},
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

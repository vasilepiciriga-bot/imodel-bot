"""
Photoshoot Mode System — single source of truth for all mode configs.
Phase 2: added style_variants (sub-style branching) and negative_layer per mode.
Imported by app.py.
"""
from __future__ import annotations
import io as _io
import random
from typing import Dict, Any, Optional

try:
    from PIL import Image as _PILImage, ImageFilter as _PILFilter, ImageStat as _PILStat
except ImportError:
    _PILImage = _PILFilter = _PILStat = None

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


# Beauty layer: skin-tone-aware enhancement phrases injected per mode.
_BEAUTY_LAYERS: Dict[str, Dict[str, str]] = {
    "vogue": {
        "fair":   "flawless porcelain skin, luminous complexion, high-fashion retouching",
        "medium": "radiant warm skin tone, sun-kissed glow, editorial retouching",
        "olive":  "rich olive skin, golden-hour warmth, magazine retouching",
        "dark":   "deep rich skin tone, velvet finish, luxury editorial glow",
        "default":"natural skin texture, professional retouching, magazine quality",
    },
    "premium": {
        "fair":   "smooth even skin, soft diffused light, professional portrait retouching",
        "medium": "warm balanced skin tone, natural glow, portrait enhancement",
        "olive":  "rich natural skin, warm flattering light, portrait quality",
        "dark":   "deep natural skin, cinematic contrast, portrait perfection",
        "default":"natural skin, professional portrait lighting",
    },
    "ceo": {
        "default": "sharp professional appearance, clean polished look, corporate headshot quality",
    },
    "luxury": {
        "fair":   "luminous skin, ultra-high-end retouching, luxury campaign quality",
        "medium": "golden radiant skin, premium retouching, luxury editorial",
        "olive":  "warm bronzed skin, opulent lighting, ultra-luxury finish",
        "dark":   "deep velvet skin tone, dramatic luxury lighting, ultra-premium finish",
        "default":"exceptional skin quality, premium retouching",
    },
    "dating": {
        "default": "natural attractive appearance, warm inviting light, lifestyle photo quality",
    },
}


def get_beauty_layer(mode_key: str, skin_tone: str = "") -> str:
    """Return beauty-layer string for a mode + skin tone combination."""
    mode_beauty = _BEAUTY_LAYERS.get(mode_key)
    if not mode_beauty:
        return ""
    return mode_beauty.get(skin_tone, mode_beauty.get("default", ""))


def apply_prompt_layer(
    base_prompt: str,
    mode_key: str,
    style_variant: Optional[str] = None,
    skin_tone: str = "",
) -> str:
    """Combine base prompt with mode prompt_layer, optional beauty_layer, and sub-style suffix."""
    cfg = get_mode_config(mode_key)
    layer = cfg.get("prompt_layer")
    if layer:
        sep = ", " if base_prompt else ""
        result = f"{base_prompt}{sep}{layer}"
    else:
        result = base_prompt
    # Inject beauty layer (skin-tone-aware enhancement)
    beauty = get_beauty_layer(mode_key, skin_tone)
    if beauty:
        result = f"{result}, {beauty}" if result else beauty
    # Apply sub-style variant suffix if specified
    if style_variant:
        variants = cfg.get("style_variants", {})
        variant_cfg = variants.get(style_variant, {})
        suffix = str(variant_cfg.get("prompt_suffix", ""))
        if suffix:
            result = f"{result}, {suffix}" if result else suffix
    return result


def _score_candidate(img_bytes: bytes) -> tuple:
    """
    Deterministic PIL-based image quality heuristic for tournament fallback.
    Returns (score 0-90, breakdown_dict). Used when Vision judge is unavailable.
    Signals: file size (encoder detail retention) + Laplacian sharpness + brightness balance.
    """
    if not img_bytes:
        return 0.0, {}
    size_score = min(len(img_bytes) / 500_000, 1.0) * 40.0
    if _PILImage is None:
        return float(size_score), {}
    try:
        im = _PILImage.open(_io.BytesIO(img_bytes)).convert("RGB")
        sm = im.resize((256, 256))
        gray = sm.convert("L")
        lap = gray.filter(_PILFilter.Kernel(
            size=3, kernel=[-1, -1, -1, -1, 8, -1, -1, -1, -1], scale=1, offset=0
        ))
        sharpness = min(_PILStat.Stat(lap).var[0] / 1000.0, 1.0) * 35.0
        mean_lum = sum(_PILStat.Stat(sm).mean) / 3.0
        bright_score = (1.0 - abs(mean_lum - 128.0) / 128.0) * 15.0
        return min(float(size_score + sharpness + bright_score), 90.0), {}
    except Exception:
        return float(size_score), {}


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

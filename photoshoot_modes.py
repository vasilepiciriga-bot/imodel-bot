"""
Photoshoot Mode System — single source of truth for all mode configs.
Phase 2A: 35 modes across 8 categories (basics, fashion, career, social, lifestyle, events, pop_culture, fantasy, viral).
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
    # ─── BASICS ──────────────────────────────────────────────────────────────
    "everyday": {
        "label": {"ru": "Обычный", "en": "Everyday", "de": "Standard", "ar": "عادي"},
        "emoji": "📸",
        "credits": 1,
        "n_generations": 1,
        "select_best": 1,
        "upscale": False,
        "upscale_factor": 2,
        "upscale_fidelity": 0.65,
        "prompt_layer": (
            "lifestyle portrait, natural setting, authentic environment, "
            "wearing casual stylish everyday outfit, "
            "flattering ambient light, genuine expression, "
            "half-body candid shot, natural relaxed pose, "
            "85mm f/1.8 lens, shallow depth of field, "
            "real-world background, candid lifestyle photography"
        ),
        "negative_layer": "studio backdrop, fake background, overprocessed, artificial lighting",
        "style_variants": {},
        "is_premium": False,
        "requires_custom_prompt": False,
        "badge": None,
        "category": "basics",
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
        "upscale_fidelity": 0.65,
        "prompt_layer": "professional portrait photography, wearing polished professional attire, studio lighting, sharp focus, magazine quality",
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
            "color_pop": {
                "label": {"en": "Color Pop", "ru": "Яркие цвета"},
                "prompt_suffix": "vibrant saturated colors, bold fashion palette, high-contrast editorial",
            },
            "black_white": {
                "label": {"en": "Black & White", "ru": "Ч/Б"},
                "prompt_suffix": "classic monochrome photography, fine-grain B&W, timeless elegance",
            },
        },
        "is_premium": True,
        "requires_custom_prompt": False,
        "badge": "popular",
        "category": "basics",
        "short_desc": {
            "ru": "4 генерации, лучшие 2, апскейл",
            "en": "4 generations, best 2 selected, upscaled",
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
        "upscale_fidelity": 0.65,
        "prompt_layer": None,
        "negative_layer": "blurry, low quality, distorted face, bad anatomy",
        "style_variants": {},
        "is_premium": True,
        "requires_custom_prompt": True,
        "badge": None,
        "category": "creative",
        "short_desc": {
            "ru": "Опишите образ — AI создаёт prompt",
            "en": "Describe your vision, AI builds the prompt",
        },
    },

    # ─── FASHION ─────────────────────────────────────────────────────────────
    "vogue": {
        "label": {"ru": "Vogue", "en": "Vogue", "de": "Vogue", "ar": "فوغ"},
        "emoji": "👑",
        "credits": 6,
        "n_generations": 8,
        "select_best": 3,
        "upscale": True,
        "upscale_factor": 4,
        "upscale_fidelity": 0.65,
        "prompt_layer": (
            "editorial Vogue magazine quality, high fashion avant-garde styling, "
            "wearing haute couture avant-garde fashion ensemble, "
            "luxury brand campaign shot in octabox-lit fashion studio, grey seamless backdrop, "
            "full body or 3/4 editorial shot, confident angled pose, "
            "art director composition, ultra-premium photoshoot"
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
            "dark_art": {
                "label": {"en": "Dark Art", "ru": "Тёмный арт"},
                "prompt_suffix": "dark dramatic studio, deep jewel tones, moody avant-garde fashion, bold contrast",
            },
            "resort": {
                "label": {"en": "Resort Season", "ru": "Курорт"},
                "prompt_suffix": "resort wear editorial, tropical lush background, vibrant summer palette, luxury vacation",
            },
            "vintage_couture": {
                "label": {"en": "Vintage Couture", "ru": "Ретро-кутюр"},
                "prompt_suffix": "1990s Vogue aesthetic, vintage couture styling, film grain, timeless elegance",
            },
        },
        "is_premium": True,
        "requires_custom_prompt": False,
        "badge": "best_quality",
        "category": "fashion",
        "short_desc": {
            "ru": "8 генераций, топ-3, 4x апскейл",
            "en": "8 generations, top 3, 4× upscale",
        },
    },

    # ─── CAREER ──────────────────────────────────────────────────────────────
    "ceo": {
        "label": {"ru": "CEO", "en": "CEO", "de": "CEO", "ar": "CEO"},
        "emoji": "🤵",
        "credits": 4,
        "n_generations": 6,
        "select_best": 2,
        "upscale": True,
        "upscale_factor": 2,
        "upscale_fidelity": 0.65,
        "prompt_layer": (
            "corporate executive portrait, confident leadership presence, "
            "tailored business suit, authoritative gaze, LinkedIn-ready, "
            "glass-wall corner office interior, city skyline visible through window, "
            "3/4 body portrait, upright confident posture, 85mm lens"
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
            "speaker": {
                "label": {"en": "Keynote Speaker", "ru": "Спикер"},
                "prompt_suffix": "conference stage, audience blur in background, dynamic pose, thought leader",
            },
            "tech_casual": {
                "label": {"en": "Tech Casual", "ru": "Тех-casual"},
                "prompt_suffix": "Silicon Valley smart casual, modern coworking space, relaxed yet sharp",
            },
            "creative": {
                "label": {"en": "Creative Director", "ru": "Арт-директор"},
                "prompt_suffix": "creative agency studio, artistic backdrop, bold individualistic style",
            },
        },
        "is_premium": True,
        "requires_custom_prompt": False,
        "badge": "for_business",
        "category": "career",
        "short_desc": {
            "ru": "Бизнес/LinkedIn/founder портреты",
            "en": "Business, LinkedIn, founder portraits",
        },
    },
    "doctor": {
        "label": {"ru": "Doctor", "en": "Doctor"},
        "emoji": "🩺",
        "credits": 3,
        "n_generations": 4,
        "select_best": 2,
        "upscale": False,
        "upscale_factor": 2,
        "upscale_fidelity": 0.65,
        "prompt_layer": (
            "medical professional portrait, white lab coat, stethoscope, "
            "hospital or clinic background, confident trustworthy expression, professional headshot quality"
        ),
        "negative_layer": "casual clothes, non-medical setting, blurry, unprofessional",
        "style_variants": {
            "hospital": {
                "label": {"en": "Hospital", "ru": "Больница"},
                "prompt_suffix": "modern hospital corridor, clinical white environment, focused professional",
            },
            "clinic_warm": {
                "label": {"en": "Private Clinic", "ru": "Клиника"},
                "prompt_suffix": "warm private practice interior, reassuring smile, approachable bedside manner",
            },
        },
        "is_premium": False,
        "requires_custom_prompt": False,
        "badge": None,
        "category": "career",
        "short_desc": {
            "ru": "Профессиональное фото врача",
            "en": "Medical professional portrait",
        },
    },
    "lawyer": {
        "label": {"ru": "Lawyer", "en": "Lawyer"},
        "emoji": "⚖️",
        "credits": 3,
        "n_generations": 4,
        "select_best": 2,
        "upscale": False,
        "upscale_factor": 2,
        "upscale_fidelity": 0.65,
        "prompt_layer": (
            "attorney portrait, power suit, law office bookshelf background, "
            "authoritative confident expression, professional headshot, legal setting"
        ),
        "negative_layer": "casual clothes, outdoor non-professional, blurry",
        "style_variants": {
            "law_office": {
                "label": {"en": "Law Office", "ru": "Офис"},
                "prompt_suffix": "mahogany desk, leather chair, legal books wall, prestigious firm interior",
            },
            "courtroom": {
                "label": {"en": "Courtroom Ready", "ru": "Суд"},
                "prompt_suffix": "sharp tailored suit, commanding presence, courthouse pillars, confident gaze",
            },
        },
        "is_premium": False,
        "requires_custom_prompt": False,
        "badge": None,
        "category": "career",
        "short_desc": {
            "ru": "Портрет адвоката / юриста",
            "en": "Attorney power portrait",
        },
    },
    "real_estate": {
        "label": {"ru": "Real Estate", "en": "Real Estate Agent"},
        "emoji": "🏠",
        "credits": 3,
        "n_generations": 4,
        "select_best": 2,
        "upscale": False,
        "upscale_factor": 2,
        "upscale_fidelity": 0.65,
        "prompt_layer": (
            "real estate agent professional portrait, welcoming confident smile, "
            "luxury property or modern architecture backdrop, smart business casual, realtor headshot quality"
        ),
        "negative_layer": "casual home setting, unprofessional, blurry, cluttered background",
        "style_variants": {
            "luxury_property": {
                "label": {"en": "Luxury Property", "ru": "Элитная недвижимость"},
                "prompt_suffix": "luxury villa entrance, grand architecture, upscale residential backdrop",
            },
            "modern_office": {
                "label": {"en": "Modern Agency", "ru": "Агентство"},
                "prompt_suffix": "sleek real estate agency, contemporary interior, city view window",
            },
        },
        "is_premium": False,
        "requires_custom_prompt": False,
        "badge": None,
        "category": "career",
        "short_desc": {
            "ru": "Фото агента по недвижимости",
            "en": "Real estate agent headshot",
        },
    },
    "podcast_host": {
        "label": {"ru": "Podcast Host", "en": "Podcast Host"},
        "emoji": "🎙️",
        "credits": 3,
        "n_generations": 4,
        "select_best": 2,
        "upscale": False,
        "upscale_factor": 2,
        "upscale_fidelity": 0.65,
        "prompt_layer": (
            "podcast host portrait, wearing smart casual creator outfit, "
            "professional microphone setup, sound-treated studio, "
            "engaging charismatic expression, content creator vibe, YouTube or podcast cover quality"
        ),
        "negative_layer": "no microphone, bedroom mess, bad lighting, amateur",
        "style_variants": {
            "modern_studio": {
                "label": {"en": "Pro Studio", "ru": "Студия"},
                "prompt_suffix": "broadcast-quality podcast studio, RGB lighting accents, professional equipment",
            },
            "creator_desk": {
                "label": {"en": "Creator Setup", "ru": "Creator-сетап"},
                "prompt_suffix": "aesthetic creator workspace, ring light, bookshelf background, cozy vibe",
            },
        },
        "is_premium": False,
        "requires_custom_prompt": False,
        "badge": "new",
        "category": "career",
        "short_desc": {
            "ru": "Обложка подкаста / YouTube",
            "en": "Podcast host & content creator",
        },
    },
    "fitness_model": {
        "label": {"ru": "Fitness", "en": "Fitness Model"},
        "emoji": "💪",
        "credits": 3,
        "n_generations": 4,
        "select_best": 2,
        "upscale": False,
        "upscale_factor": 2,
        "upscale_fidelity": 0.65,
        "prompt_layer": (
            "fitness model portrait, athletic physique, gym or outdoor training backdrop, "
            "activewear, confident powerful pose, health and wellness magazine quality"
        ),
        "negative_layer": "business suit, formal office, untoned appearance, flat lighting",
        "style_variants": {
            "gym_studio": {
                "label": {"en": "Gym Studio", "ru": "Зал"},
                "prompt_suffix": "modern gym interior, dramatic pump lighting, equipment backdrop, intense focus",
            },
            "outdoor_athlete": {
                "label": {"en": "Outdoor Athlete", "ru": "На природе"},
                "prompt_suffix": "outdoor trail or beach, athletic lifestyle, golden hour energy, dynamic action pose",
            },
        },
        "is_premium": False,
        "requires_custom_prompt": False,
        "badge": None,
        "category": "career",
        "short_desc": {
            "ru": "Фитнес-фото, атлетичный образ",
            "en": "Fitness & athletic model portrait",
        },
    },

    # ─── SOCIAL / DATING ─────────────────────────────────────────────────────
    "dating": {
        "label": {"ru": "Dating", "en": "Dating", "de": "Dating", "ar": "مواعدة"},
        "emoji": "💫",
        "credits": 3,
        "n_generations": 4,
        "select_best": 2,
        "upscale": False,
        "upscale_factor": 2,
        "upscale_fidelity": 0.65,
        "prompt_layer": (
            "natural warm smile, approachable likeable personality, "
            "wearing attractive casual stylish outfit, "
            "candid lifestyle photography, authentic relaxed look, social media quality, "
            "half-body warm approachable pose, 35mm f/2 lens"
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
            "sunset": {
                "label": {"en": "Golden Hour", "ru": "Золотой час"},
                "prompt_suffix": "warm sunset light, beach or park, soft backlit glow, magical hour",
            },
            "sporty": {
                "label": {"en": "Active Life", "ru": "Активный"},
                "prompt_suffix": "athletic lifestyle, outdoor sports vibe, energetic dynamic pose, natural setting",
            },
        },
        "is_premium": False,
        "requires_custom_prompt": False,
        "badge": None,
        "category": "social",
        "short_desc": {
            "ru": "Натуральные привлекательные фото",
            "en": "Natural attractive photos for dating/social",
        },
    },

    # ─── LIFESTYLE ────────────────────────────────────────────────────────────
    "luxury": {
        "label": {"ru": "Luxury", "en": "Luxury", "de": "Luxus", "ar": "فاخر"},
        "emoji": "✨",
        "credits": 4,
        "n_generations": 6,
        "select_best": 2,
        "upscale": True,
        "upscale_factor": 2,
        "upscale_fidelity": 0.65,
        "prompt_layer": (
            "ultra-luxury lifestyle editorial, five-star ambiance, "
            "wearing elegant designer luxury attire, couture fashion outfit, "
            "grand marble hotel lobby with warm chandelier light and architectural columns, "
            "old money elegance, Instagram-worthy, fashion forward, "
            "3/4 body shot, relaxed elegant pose"
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
            "monaco": {
                "label": {"en": "Monaco", "ru": "Монако"},
                "prompt_suffix": "Monaco Grand Prix paddock, casino sophistication, European jetset lifestyle",
            },
            "florence": {
                "label": {"en": "Italian Villa", "ru": "Итальянская вилла"},
                "prompt_suffix": "Tuscany villa courtyard, Renaissance art backdrop, warm golden Italian light",
            },
            "ski_chalet": {
                "label": {"en": "Alpine Chalet", "ru": "Альпийский шале"},
                "prompt_suffix": "luxury ski chalet, snowy mountains, fireplace warmth, après-ski elegance",
            },
        },
        "is_premium": True,
        "requires_custom_prompt": False,
        "badge": "viral",
        "category": "lifestyle",
        "short_desc": {
            "ru": "Instagram, travel, old money, luxury",
            "en": "Instagram, travel, old money, luxury lifestyle",
        },
    },
    "dubai_influencer": {
        "label": {"ru": "Dubai Influencer", "en": "Dubai Influencer"},
        "emoji": "🏙️",
        "credits": 4,
        "n_generations": 6,
        "select_best": 2,
        "upscale": True,
        "upscale_factor": 2,
        "upscale_fidelity": 0.65,
        "prompt_layer": (
            "Dubai luxury influencer portrait, rooftop terrace with Burj Khalifa and Dubai Marina skyline, "
            "wearing luxury designer fashion ensemble, glamorous opulent styling, "
            "golden hour desert glow, social media influencer aesthetic, "
            "3/4 body influencer pose, warm dusk sky backdrop"
        ),
        "negative_layer": "old architecture, casual clothes, cold tones, budget setting",
        "style_variants": {
            "rooftop_skyline": {
                "label": {"en": "Rooftop Skyline", "ru": "На крыше"},
                "prompt_suffix": "luxury hotel rooftop infinity pool, Dubai skyline at sunset, glamorous poolside",
            },
            "desert_dunes": {
                "label": {"en": "Desert Dunes", "ru": "Пустыня"},
                "prompt_suffix": "golden sand dunes, desert sunset photography, flowing luxury outfit, dramatic desert sky",
            },
        },
        "is_premium": True,
        "requires_custom_prompt": False,
        "badge": "new",
        "category": "lifestyle",
        "short_desc": {
            "ru": "Dubai luxury influencer life",
            "en": "Dubai luxury influencer lifestyle",
        },
    },
    "bali_creator": {
        "label": {"ru": "Bali Creator", "en": "Bali Creator"},
        "emoji": "🌴",
        "credits": 3,
        "n_generations": 4,
        "select_best": 2,
        "upscale": False,
        "upscale_factor": 2,
        "upscale_fidelity": 0.65,
        "prompt_layer": (
            "Bali digital nomad lifestyle, tropical lush jungle or rice terraces backdrop, "
            "Ubud creative community vibes, relaxed content creator aesthetic, "
            "golden tropical light, bohemian chic travel fashion"
        ),
        "negative_layer": "urban concrete, cold weather, formal business, grey sky",
        "style_variants": {
            "rice_terraces": {
                "label": {"en": "Rice Terraces", "ru": "Рисовые поля"},
                "prompt_suffix": "iconic Bali rice terraces, morning mist, emerald green terraces, flowing white outfit",
            },
            "jungle_villa": {
                "label": {"en": "Jungle Villa", "ru": "Джунгли"},
                "prompt_suffix": "luxury jungle villa with infinity pool, lush tropical foliage, bamboo architecture",
            },
        },
        "is_premium": False,
        "requires_custom_prompt": False,
        "badge": None,
        "category": "lifestyle",
        "short_desc": {
            "ru": "Тропический lifestyle в Бали",
            "en": "Bali digital nomad tropical lifestyle",
        },
    },
    "cottagecore": {
        "label": {"ru": "Cottagecore", "en": "Cottagecore"},
        "emoji": "🌸",
        "credits": 2,
        "n_generations": 3,
        "select_best": 2,
        "upscale": False,
        "upscale_factor": 2,
        "upscale_fidelity": 0.65,
        "prompt_layer": (
            "cottagecore aesthetic, pastoral countryside, wildflower meadow or cottage garden, "
            "linen and lace or floral dress, soft warm natural light, nostalgic rural idyll, "
            "Pinterest cottagecore dreamy photography"
        ),
        "negative_layer": "urban concrete, modern tech, dark gritty, harsh studio",
        "style_variants": {
            "wildflower_meadow": {
                "label": {"en": "Wildflower Meadow", "ru": "Луговые цветы"},
                "prompt_suffix": "blooming wildflower field, daisy crown, flowing peasant dress, magical golden afternoon",
            },
            "cottage_interior": {
                "label": {"en": "Cozy Cottage", "ru": "Уютный коттедж"},
                "prompt_suffix": "rustic cottage kitchen, dried herbs hanging, warm candlelight, baking bread",
            },
        },
        "is_premium": False,
        "requires_custom_prompt": False,
        "badge": None,
        "category": "lifestyle",
        "short_desc": {
            "ru": "Cottagecore — пастораль и природа",
            "en": "Dreamy cottagecore pastoral aesthetic",
        },
    },
    "y2k": {
        "label": {"ru": "Y2K Aesthetic", "en": "Y2K Aesthetic"},
        "emoji": "💿",
        "credits": 2,
        "n_generations": 3,
        "select_best": 2,
        "upscale": False,
        "upscale_factor": 2,
        "upscale_fidelity": 0.65,
        "prompt_layer": (
            "Y2K aesthetic, year 2000 fashion, early 2000s nostalgia, "
            "butterfly clips, low-rise jeans, metallic fabrics, glossy magazine teen style, "
            "bold saturated 2000s colors, disposable camera quality grain"
        ),
        "negative_layer": "modern fashion, dark moody, formal, high fashion editorial",
        "style_variants": {
            "pop_star": {
                "label": {"en": "Y2K Pop Star", "ru": "Поп-звезда"},
                "prompt_suffix": "Britney Spears era pop star, sparkly crop top, platform shoes, MTV music video energy",
            },
            "mall_aesthetic": {
                "label": {"en": "Mall Aesthetic", "ru": "Молл"},
                "prompt_suffix": "2000s mall photo booth, plaid mini skirt, chunky sneakers, teen magazine editorial",
            },
        },
        "is_premium": False,
        "requires_custom_prompt": False,
        "badge": "trending",
        "category": "lifestyle",
        "short_desc": {
            "ru": "Эстетика 2000-х, Y2K тренд",
            "en": "Y2K early 2000s nostalgia aesthetic",
        },
    },
    "old_money_portrait": {
        "label": {"ru": "Old Money", "en": "Old Money"},
        "emoji": "🏛️",
        "credits": 4,
        "n_generations": 6,
        "select_best": 2,
        "upscale": True,
        "upscale_factor": 2,
        "upscale_fidelity": 0.65,
        "prompt_layer": (
            "old money aesthetic portrait, inherited wealth and understated elegance, "
            "classic tailored clothing, English country estate with manicured lawns and stone manor house, "
            "soft overcast English light, quiet luxury, Slim Aarons photography style"
        ),
        "negative_layer": "flashy nouveau riche, logo-heavy fashion, urban streetwear, loud colors",
        "style_variants": {
            "country_estate": {
                "label": {"en": "Country Estate", "ru": "Поместье"},
                "prompt_suffix": "English countryside manor, manicured lawns, tweed blazer, heritage elegance",
            },
            "library_study": {
                "label": {"en": "Ancestral Library", "ru": "Библиотека"},
                "prompt_suffix": "oak-panelled ancestral library, leather armchair, rare books, scholarly aristocrat",
            },
        },
        "is_premium": True,
        "requires_custom_prompt": False,
        "badge": "new",
        "category": "lifestyle",
        "short_desc": {
            "ru": "Old money — тихая роскошь",
            "en": "Old money quiet luxury aesthetic",
        },
    },

    # ─── EVENTS ──────────────────────────────────────────────────────────────
    "met_gala": {
        "label": {"ru": "Met Gala", "en": "Met Gala"},
        "emoji": "🌟",
        "credits": 4,
        "seasonal_end": "05-07",
        "n_generations": 6,
        "select_best": 2,
        "upscale": True,
        "upscale_factor": 2,
        "upscale_fidelity": 0.65,
        "prompt_layer": (
            "Met Gala celebrity entrance, haute couture avant-garde gown, extravagant headpiece, "
            "Metropolitan Museum of Art red carpet, paparazzi flashes, dramatic fashion editorial lighting"
        ),
        "negative_layer": "casual clothing, plain background, amateur snapshot, mundane setting",
        "style_variants": {
            "theatrical_couture": {
                "label": {"en": "Theatrical", "ru": "Театральный"},
                "prompt_suffix": "surreal avant-garde costume, architectural fashion sculpture, art installation wearable",
            },
            "golden_glam": {
                "label": {"en": "Golden Glam", "ru": "Золотой гламур"},
                "prompt_suffix": "liquid gold metallic gown, opulent jewels, old Hollywood glamour meets modern luxury",
            },
        },
        "is_premium": True,
        "requires_custom_prompt": False,
        "badge": "new",
        "category": "events",
        "short_desc": {
            "ru": "Красная дорожка Met Gala",
            "en": "Met Gala red carpet haute couture",
        },
    },
    "halloween": {
        "label": {"ru": "Halloween", "en": "Halloween"},
        "emoji": "🎃",
        "credits": 3,
        "seasonal_end": "10-31",
        "n_generations": 4,
        "select_best": 2,
        "upscale": False,
        "upscale_factor": 2,
        "upscale_fidelity": 0.65,
        "prompt_layer": (
            "Halloween portrait, dramatic spooky atmosphere, moody cinematic lighting, "
            "dark Halloween backdrop with pumpkins or fog, "
            "wearing elaborate theatrical Halloween costume, professional costume photography"
        ),
        "negative_layer": "bright cheerful daylight, casual plain background, mundane",
        "style_variants": {
            "vampire": {
                "label": {"en": "Vampire", "ru": "Вампир"},
                "prompt_suffix": "vampire aristocrat, Gothic castle hallway, crimson cape, pale dramatic lighting",
            },
            "witch": {
                "label": {"en": "Dark Witch", "ru": "Ведьма"},
                "prompt_suffix": "mysterious witch, enchanted dark forest, full moon glow, spell-casting pose",
            },
            "dark_fantasy": {
                "label": {"en": "Dark Fantasy", "ru": "Тёмное фэнтези"},
                "prompt_suffix": "dark fantasy creature, fallen angel or demon, otherworldly shadow play",
            },
        },
        "is_premium": False,
        "requires_custom_prompt": False,
        "badge": None,
        "category": "events",
        "short_desc": {
            "ru": "Жуткий образ на Хэллоуин",
            "en": "Spooky Halloween costume portrait",
        },
    },
    "christmas_card": {
        "label": {"ru": "Christmas Card", "en": "Christmas Card"},
        "emoji": "🎄",
        "credits": 2,
        "seasonal_end": "12-31",
        "n_generations": 3,
        "select_best": 2,
        "upscale": False,
        "upscale_factor": 2,
        "upscale_fidelity": 0.65,
        "prompt_layer": (
            "festive Christmas portrait, cozy holiday atmosphere, warm golden light, "
            "Christmas tree with lights, snow or winter setting, "
            "wearing cozy festive Christmas sweater or elegant holiday dress, joyful holiday card quality"
        ),
        "negative_layer": "summer, outdoor daytime, casual non-festive outfit",
        "style_variants": {
            "cozy_fireplace": {
                "label": {"en": "Cozy Fireplace", "ru": "У камина"},
                "prompt_suffix": "crackling fireplace glow, knit sweater, mug of cocoa, warm amber light",
            },
            "snowy_wonderland": {
                "label": {"en": "Winter Wonderland", "ru": "Снежная сказка"},
                "prompt_suffix": "snowy forest backdrop, snowflakes falling, winter coat, magical snow scene",
            },
        },
        "is_premium": False,
        "requires_custom_prompt": False,
        "badge": None,
        "category": "events",
        "short_desc": {
            "ru": "Рождественская открытка",
            "en": "Festive Christmas portrait card",
        },
    },
    "valentines": {
        "label": {"ru": "Valentine's Day", "en": "Valentine's Day"},
        "emoji": "💕",
        "credits": 2,
        "seasonal_end": "02-14",
        "n_generations": 3,
        "select_best": 2,
        "upscale": False,
        "upscale_factor": 2,
        "upscale_fidelity": 0.65,
        "prompt_layer": (
            "Valentine's Day romantic portrait, soft rose and pink tones, "
            "wearing elegant romantic dress or stylish date-night outfit, "
            "dreamy romantic atmosphere, roses or flower petals, warm soft lighting"
        ),
        "negative_layer": "cold tones, harsh lighting, casual unromantic setting",
        "style_variants": {
            "romantic_roses": {
                "label": {"en": "Romantic Roses", "ru": "Розы"},
                "prompt_suffix": "surrounded by red roses, passionate romance, deep red velvet background",
            },
            "dreamy_pink": {
                "label": {"en": "Dreamy Pink", "ru": "Розовый сон"},
                "prompt_suffix": "soft pastel pink aesthetic, dreamy bokeh, angelic feminine glow",
            },
        },
        "is_premium": False,
        "requires_custom_prompt": False,
        "badge": None,
        "category": "events",
        "short_desc": {
            "ru": "Романтичный образ на День влюблённых",
            "en": "Romantic Valentine's Day portrait",
        },
    },
    "coachella": {
        "label": {"ru": "Coachella", "en": "Coachella"},
        "emoji": "🌵",
        "credits": 3,
        "seasonal_end": "04-30",
        "n_generations": 4,
        "select_best": 2,
        "upscale": False,
        "upscale_factor": 2,
        "upscale_fidelity": 0.65,
        "prompt_layer": (
            "Coachella music festival, boho chic festival fashion, desert golden hour, "
            "flower crown, fringe and embroidery, carefree festival vibe, influencer editorial"
        ),
        "negative_layer": "formal office, grey background, urban concrete, winter clothes",
        "style_variants": {
            "boho_queen": {
                "label": {"en": "Boho Queen", "ru": "Бохо"},
                "prompt_suffix": "bohemian maxi dress, flower crown, dreamcatcher accessories, golden desert light",
            },
            "y2k_festival": {
                "label": {"en": "Y2K Festival", "ru": "Y2K Festival"},
                "prompt_suffix": "Y2K inspired festival look, butterfly clips, sparkly top, early 2000s energy",
            },
        },
        "is_premium": False,
        "requires_custom_prompt": False,
        "badge": "new",
        "category": "events",
        "short_desc": {
            "ru": "Фестивальный образ Coachella",
            "en": "Coachella festival boho editorial",
        },
    },
    "wedding": {
        "label": {"ru": "Wedding", "en": "Wedding"},
        "emoji": "👰",
        "credits": 4,
        "n_generations": 6,
        "select_best": 2,
        "upscale": True,
        "upscale_factor": 2,
        "upscale_fidelity": 0.65,
        "prompt_layer": (
            "bridal portrait photography, elegant wedding gown or suit, soft romantic lighting, "
            "wedding venue backdrop, timeless elegant photography, pure joy and love, magazine wedding editorial"
        ),
        "negative_layer": "casual outfit, unformal setting, harsh lighting, sad expression",
        "style_variants": {
            "classic_bridal": {
                "label": {"en": "Classic Bride", "ru": "Невеста"},
                "prompt_suffix": "white lace wedding dress, floral bouquet, soft veil, cathedral or garden chapel",
            },
            "garden_romance": {
                "label": {"en": "Garden Romance", "ru": "Сад"},
                "prompt_suffix": "outdoor garden ceremony, flower arch backdrop, warm golden hour, romantic soft focus",
            },
        },
        "is_premium": True,
        "requires_custom_prompt": False,
        "badge": "new",
        "category": "events",
        "short_desc": {
            "ru": "Свадебный портрет",
            "en": "Elegant wedding portrait",
        },
    },

    # ─── POP CULTURE ─────────────────────────────────────────────────────────
    "disney_princess": {
        "label": {"ru": "Disney Princess", "en": "Disney Princess"},
        "emoji": "👸",
        "credits": 3,
        "n_generations": 4,
        "select_best": 2,
        "upscale": False,
        "upscale_factor": 2,
        "upscale_fidelity": 0.65,
        "prompt_layer": (
            "Disney princess style portrait, fairy tale enchanted aesthetic, "
            "sparkly ball gown or royal attire, magical dreamy atmosphere, castle or enchanted forest backdrop, "
            "Disney live-action film quality"
        ),
        "negative_layer": "dark gritty, horror, casual modern clothes, ugly, poorly lit",
        "style_variants": {
            "enchanted_forest": {
                "label": {"en": "Enchanted Forest", "ru": "Волшебный лес"},
                "prompt_suffix": "magical forest with glowing fireflies, floral crown, ethereal light rays through trees",
            },
            "royal_ball": {
                "label": {"en": "Royal Ball", "ru": "Королевский бал"},
                "prompt_suffix": "grand ballroom, crystal chandeliers, jeweled gown, regal princess posture",
            },
        },
        "is_premium": False,
        "requires_custom_prompt": False,
        "badge": "new",
        "category": "pop_culture",
        "short_desc": {
            "ru": "Принцесса в стиле Disney",
            "en": "Disney princess fairy tale portrait",
        },
    },
    "anime_hero": {
        "label": {"ru": "Anime Hero", "en": "Anime Hero"},
        "emoji": "⚡",
        "credits": 3,
        "n_generations": 4,
        "select_best": 2,
        "upscale": False,
        "upscale_factor": 2,
        "upscale_fidelity": 0.65,
        "prompt_layer": (
            "anime-style portrait illustration, manga aesthetic, vibrant cel-shaded colors, "
            "expressive large anime eyes, detailed anime character design, Japanese anime quality"
        ),
        "negative_layer": "realistic photo, western cartoon, ugly proportions, blurry",
        "style_variants": {
            "shonen_fighter": {
                "label": {"en": "Shonen Fighter", "ru": "Боец"},
                "prompt_suffix": "fierce warrior energy, battle aura glowing, power-up effects, determined hero expression",
            },
            "magical_girl": {
                "label": {"en": "Magical Girl", "ru": "Магическая девочка"},
                "prompt_suffix": "magical girl transformation outfit, sparkle effects, pastel magical costume, wand",
            },
        },
        "is_premium": False,
        "requires_custom_prompt": False,
        "badge": "new",
        "category": "pop_culture",
        "short_desc": {
            "ru": "Аниме-персонаж из манги",
            "en": "Anime/manga style character",
        },
    },
    "superhero": {
        "label": {"ru": "Superhero", "en": "Superhero"},
        "emoji": "🦸",
        "credits": 3,
        "n_generations": 4,
        "select_best": 2,
        "upscale": True,
        "upscale_factor": 2,
        "upscale_fidelity": 0.65,
        "prompt_layer": (
            "superhero portrait, Marvel or DC comics style costume, heroic powerful pose, "
            "dramatic comic book lighting, city skyline or rooftop backdrop, cinematic superhero film quality"
        ),
        "negative_layer": "villain defeated pose, civilian clothes, dark ugly, amateur snapshot",
        "style_variants": {
            "cape_hero": {
                "label": {"en": "Cape Hero", "ru": "Супергерой"},
                "prompt_suffix": "cape billowing in wind, city rooftop, spotlight from below, heroic silhouette",
            },
            "armored_suit": {
                "label": {"en": "Armored Suit", "ru": "Бронекостюм"},
                "prompt_suffix": "Iron Man style power armor, hi-tech suit details, energy reactor chest glow",
            },
        },
        "is_premium": False,
        "requires_custom_prompt": False,
        "badge": "new",
        "category": "pop_culture",
        "short_desc": {
            "ru": "Ты как супергерой Marvel/DC",
            "en": "Marvel/DC superhero portrait",
        },
    },
    "movie_poster": {
        "label": {"ru": "Movie Poster", "en": "Movie Poster"},
        "emoji": "🎬",
        "credits": 4,
        "n_generations": 4,
        "select_best": 2,
        "upscale": True,
        "upscale_factor": 2,
        "upscale_fidelity": 0.65,
        "prompt_layer": (
            "cinematic movie poster portrait, Hollywood production quality, "
            "wearing stylish film star costume or cinematic character wardrobe, "
            "dramatic cinematic lighting, blockbuster film aesthetic, "
            "intense compelling expression, film star quality"
        ),
        "negative_layer": "amateur snapshot, flat lighting, boring background, low contrast",
        "style_variants": {
            "action_blockbuster": {
                "label": {"en": "Action Blockbuster", "ru": "Боевик"},
                "prompt_suffix": "explosion background, action hero stance, dramatic smoke and fire, summer blockbuster",
            },
            "noir_thriller": {
                "label": {"en": "Noir Thriller", "ru": "Нуар"},
                "prompt_suffix": "moody film noir, venetian blinds light pattern, detective mystery thriller atmosphere",
            },
        },
        "is_premium": True,
        "requires_custom_prompt": False,
        "badge": "new",
        "category": "pop_culture",
        "short_desc": {
            "ru": "Как будто ты звезда Голливуда",
            "en": "Hollywood movie poster star",
        },
    },
    "rockstar": {
        "label": {"ru": "Rockstar", "en": "Rockstar"},
        "emoji": "🎸",
        "credits": 3,
        "n_generations": 4,
        "select_best": 2,
        "upscale": False,
        "upscale_factor": 2,
        "upscale_fidelity": 0.65,
        "prompt_layer": (
            "rock musician portrait, concert stage with dramatic spotlights, "
            "leather jacket or rock aesthetic outfit, guitar or microphone, "
            "album cover quality, intense rockstar attitude"
        ),
        "negative_layer": "corporate look, plain background, cheerful casual, amateur",
        "style_variants": {
            "stage_performance": {
                "label": {"en": "Live Stage", "ru": "На сцене"},
                "prompt_suffix": "massive concert arena stage, crowd of thousands, pyrotechnics, rock legend moment",
            },
            "album_cover": {
                "label": {"en": "Album Cover", "ru": "Обложка альбома"},
                "prompt_suffix": "iconic album cover composition, moody studio portrait, artistic rock photography",
            },
        },
        "is_premium": False,
        "requires_custom_prompt": False,
        "badge": None,
        "category": "pop_culture",
        "short_desc": {
            "ru": "Образ рок-звезды",
            "en": "Rock musician album cover style",
        },
    },

    # ─── FANTASY ─────────────────────────────────────────────────────────────
    "cyberpunk": {
        "label": {"ru": "Cyberpunk", "en": "Cyberpunk"},
        "emoji": "🤖",
        "credits": 3,
        "n_generations": 4,
        "select_best": 2,
        "upscale": True,
        "upscale_factor": 2,
        "upscale_fidelity": 0.65,
        "prompt_layer": (
            "cyberpunk portrait, neon-lit dystopian megacity, rain-soaked streets, "
            "neon signs in multiple languages, cybernetic implants or augmentations, "
            "wearing futuristic techwear jacket and cybernetic fashion outfit, "
            "Blade Runner 2049 cinematic style"
        ),
        "negative_layer": "natural landscape, bright daylight, cheerful, medieval, pastoral",
        "style_variants": {
            "neon_street": {
                "label": {"en": "Neon Streets", "ru": "Неоновые улицы"},
                "prompt_suffix": "neon-lit night market, rain reflections on pavement, electric blue and pink glow",
            },
            "chrome_tech": {
                "label": {"en": "Chrome Tech", "ru": "Chrome Tech"},
                "prompt_suffix": "chrome and steel cybernetic armor, holographic HUD display, neural implant aesthetics",
            },
        },
        "is_premium": False,
        "requires_custom_prompt": False,
        "badge": "new",
        "category": "fantasy",
        "short_desc": {
            "ru": "Киберпанк в стиле Blade Runner",
            "en": "Blade Runner cyberpunk neon portrait",
        },
    },
    "medieval_knight": {
        "label": {"ru": "Medieval Knight", "en": "Medieval Knight"},
        "emoji": "⚔️",
        "credits": 3,
        "n_generations": 4,
        "select_best": 2,
        "upscale": True,
        "upscale_factor": 2,
        "upscale_fidelity": 0.65,
        "prompt_layer": (
            "medieval knight portrait, detailed plate armor, fantasy realm, "
            "castle or battlefield backdrop, dramatic epic lighting, "
            "high fantasy RPG style, cinematic Game of Thrones quality"
        ),
        "negative_layer": "modern clothing, sci-fi, urban setting, blurry, amateur",
        "style_variants": {
            "castle_throne": {
                "label": {"en": "Royal Knight", "ru": "Рыцарь"},
                "prompt_suffix": "castle throne room, royal crest on armor, king's champion, ceremonial sword",
            },
            "dark_warrior": {
                "label": {"en": "Dark Warrior", "ru": "Тёмный воин"},
                "prompt_suffix": "dark ominous black iron armor, red glowing runes, intimidating dark warrior energy",
            },
        },
        "is_premium": False,
        "requires_custom_prompt": False,
        "badge": None,
        "category": "fantasy",
        "short_desc": {
            "ru": "Средневековый рыцарь в латах",
            "en": "Epic medieval knight portrait",
        },
    },
    "fairy_tale": {
        "label": {"ru": "Fairy Tale", "en": "Fairy Tale"},
        "emoji": "🧚",
        "credits": 3,
        "n_generations": 4,
        "select_best": 2,
        "upscale": False,
        "upscale_factor": 2,
        "upscale_fidelity": 0.65,
        "prompt_layer": (
            "fairy tale fantasy portrait, magical enchanted forest, "
            "wearing ethereal fairy dress or enchanted elven gown, "
            "ethereal glowing light, mystical whimsical atmosphere, "
            "fairy wings or elven features, fantasy storybook illustration quality"
        ),
        "negative_layer": "dark horror, modern urban, sci-fi, harsh lighting, gritty",
        "style_variants": {
            "forest_fairy": {
                "label": {"en": "Forest Fairy", "ru": "Лесная фея"},
                "prompt_suffix": "luminous fairy wings, ancient forest with glowing mushrooms, fireflies, magical nature spirit",
            },
            "dark_fae": {
                "label": {"en": "Dark Fae", "ru": "Тёмная фея"},
                "prompt_suffix": "dark faerie court, thorned crown, moonlit haunted forest, mysterious shadow fae",
            },
        },
        "is_premium": False,
        "requires_custom_prompt": False,
        "badge": None,
        "category": "fantasy",
        "short_desc": {
            "ru": "Фея или эльф из сказки",
            "en": "Magical fairy tale fantasy portrait",
        },
    },
    "space_explorer": {
        "label": {"ru": "Space Explorer", "en": "Space Explorer"},
        "emoji": "🚀",
        "credits": 3,
        "n_generations": 4,
        "select_best": 2,
        "upscale": True,
        "upscale_factor": 2,
        "upscale_fidelity": 0.65,
        "prompt_layer": (
            "space explorer portrait, astronaut suit or sci-fi uniform, "
            "outer space backdrop with nebula and stars, NASA mission quality or sci-fi film aesthetic, "
            "epic cosmic scale, cinematic space photography"
        ),
        "negative_layer": "earth setting, civilian clothes, medieval, dark ugly",
        "style_variants": {
            "nasa_astronaut": {
                "label": {"en": "NASA Astronaut", "ru": "Астронавт"},
                "prompt_suffix": "NASA EVA spacesuit, International Space Station exterior, Earth from orbit background",
            },
            "sci_fi_captain": {
                "label": {"en": "Sci-Fi Captain", "ru": "Капитан корабля"},
                "prompt_suffix": "futuristic starship bridge, sci-fi command uniform, warp speed stars, fleet captain",
            },
        },
        "is_premium": False,
        "requires_custom_prompt": False,
        "badge": "new",
        "category": "fantasy",
        "short_desc": {
            "ru": "Космический исследователь",
            "en": "Epic space explorer portrait",
        },
    },
    "pirate": {
        "label": {"ru": "Pirate", "en": "Pirate"},
        "emoji": "🏴‍☠️",
        "credits": 3,
        "n_generations": 4,
        "select_best": 2,
        "upscale": False,
        "upscale_factor": 2,
        "upscale_fidelity": 0.65,
        "prompt_layer": (
            "swashbuckling pirate portrait, period-accurate pirate costume, "
            "tall ship or tropical port backdrop, dramatic ocean storm or treasure chest, "
            "Pirates of the Caribbean cinematic quality"
        ),
        "negative_layer": "modern clothes, urban setting, sci-fi, office, plain background",
        "style_variants": {
            "captain": {
                "label": {"en": "Pirate Captain", "ru": "Капитан"},
                "prompt_suffix": "captain's tricorn hat, ornate captain's coat, ship helm, commanding the seas",
            },
            "treasure_hunter": {
                "label": {"en": "Treasure Hunter", "ru": "Искатель сокровищ"},
                "prompt_suffix": "tropical island beach, treasure map in hand, golden sunset, adventurous explorer",
            },
        },
        "is_premium": False,
        "requires_custom_prompt": False,
        "badge": None,
        "category": "fantasy",
        "short_desc": {
            "ru": "Пират — приключение на море",
            "en": "Swashbuckling pirate adventure",
        },
    },

    # ─── VIRAL TREND ──────────────────────────────────────────────────────────
    "action_figure": {
        "label": {"ru": "Action Figure", "en": "Action Figure"},
        "emoji": "🎁",
        "credits": 3,
        "n_generations": 3,
        "select_best": 2,
        "upscale": True,
        "upscale_factor": 2,
        "upscale_fidelity": 0.65,
        "prompt_layer": (
            "3D toy action figure, collectible figurine, sealed blister pack retail packaging box, "
            "branded cardboard backing with portrait photo, toy store display product, "
            "studio product photography on white background, sharp focus"
        ),
        "negative_layer": "real human photo, outdoor scene, blurry, watercolor, sketch, painting",
        "style_variants": {
            "hero_box": {
                "label": {"en": "Superhero Box", "ru": "Супергерой"},
                "prompt_suffix": "Marvel comics-style action hero packaging, bold superhero typography, heroic action pose",
            },
            "fashion_doll": {
                "label": {"en": "Fashion Doll", "ru": "Fashion Doll"},
                "prompt_suffix": "Barbie-style fashion doll box, pink glamorous packaging, designer outfits listed on box",
            },
            "collector_edition": {
                "label": {"en": "Collector's Edition", "ru": "Коллекционное"},
                "prompt_suffix": "limited collector's edition, metallic foil accents, premium black-and-gold packaging",
            },
        },
        "is_premium": False,
        "requires_custom_prompt": False,
        "badge": "viral",
        "category": "viral",
        "short_desc": {
            "ru": "#BarbieBoxChallenge — ты как игрушка!",
            "en": "#BarbieBoxChallenge — you as a toy!",
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


# Female-specific wardrobe terms → gender-neutral male alternatives.
# Applied when subject is identified as male.
_MALE_WARDROBE_SUBS: Dict[str, str] = {
    "wearing elegant romantic dress or stylish date-night outfit": "wearing stylish date-night outfit",
    "wearing cozy festive Christmas sweater or elegant holiday dress": "wearing cozy festive Christmas sweater or smart holiday outfit",
    "wearing ethereal fairy dress or enchanted elven gown": "wearing enchanted elven tunic or mystical fantasy robes",
    "linen and lace or floral dress": "linen shirt and rustic pastoral attire",
    "sparkly ball gown or royal attire": "royal attire or regal ceremonial costume",
}


def apply_prompt_layer(
    base_prompt: str,
    mode_key: str,
    style_variant: Optional[str] = None,
    skin_tone: str = "",
    gender: str = "",
) -> str:
    """Combine base prompt with mode prompt_layer, beauty_layer, and sub-style suffix.

    gender: 'man' or 'woman' — when 'man', replaces female-specific wardrobe with neutral alternatives.
    """
    cfg = get_mode_config(mode_key)
    layer = cfg.get("prompt_layer") or ""
    # Apply gender-aware wardrobe substitution for male subjects
    if gender == "man" and layer:
        for female_term, male_term in _MALE_WARDROBE_SUBS.items():
            if female_term in layer:
                layer = layer.replace(female_term, male_term)
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

"""First 30 premium commercial photoshoot definitions (Phase 1 seed catalog)."""

from __future__ import annotations

from typing import Any

from imodel.prompts.base_identity import BASE_IDENTITY_LOCK
from imodel.prompts.negative_prompts import BASE_NEGATIVE


def _style(
    key: str,
    name: str,
    category: str,
    commercial_angle: str,
    base_prompt: str,
    lighting: str,
    camera: str,
    clothing: str,
    background: str,
    mood: str,
    *,
    audience: list[str] | None = None,
    use_case: list[str] | None = None,
    trend_level: str = "medium",
    price_credits: int = 4,
    is_premium: bool = True,
    is_trending: bool = False,
    sort_order: int = 100,
    ab_test_group: str = "default",
) -> dict[str, Any]:
    return {
        "key": key,
        "name": name,
        "category": category,
        "audience": audience or ["men", "women"],
        "use_case": use_case or ["social profile"],
        "trend_level": trend_level,
        "commercial_angle": commercial_angle,
        "prompt_version": "v1.0",
        "base_prompt": base_prompt,
        "identity_lock": BASE_IDENTITY_LOCK,
        "lighting": lighting,
        "camera": camera,
        "clothing": clothing,
        "background": background,
        "mood": mood,
        "negative_prompt": BASE_NEGATIVE,
        "safety_notes": ["SFW", "no famous likenesses", "no visible brand logos"],
        "price_credits": price_credits,
        "is_premium": is_premium,
        "is_trending": is_trending,
        "is_active": True,
        "sort_order": sort_order,
        "ab_test_group": ab_test_group,
        "success_rate": None,
        "conversion_score": None,
    }


# --- Business (8) ---
_LINKEDIN = _style(
    "linkedin_premium",
    "LinkedIn Premium",
    "Business",
    "Look trustworthy, modern, and hire-worthy.",
    "Professional LinkedIn headshot of one adult person, confident approachable expression.",
    "Soft beauty key light with subtle rim, clean corporate fill.",
    "85mm portrait lens, f/2.8, shallow depth, sharp eyes.",
    "Smart business casual blazer or crisp shirt, minimal jewelry.",
    "Neutral modern office blur or soft gray studio backdrop.",
    "Calm competent professional energy.",
    audience=["entrepreneurs", "consultants"],
    use_case=["LinkedIn", "CV"],
    trend_level="high",
    is_trending=True,
    sort_order=10,
)
_CEO = _style(
    "ceo_portrait",
    "CEO Portrait",
    "Business",
    "Executive presence without arrogance.",
    "Executive portrait of one adult person, leadership posture, direct gaze.",
    "Rembrandt-inspired key light, controlled shadows, premium contrast.",
    "50mm, f/2, cinematic corporate framing.",
    "Tailored dark suit, premium fabric texture, no visible logos.",
    "Dark executive office or charcoal studio backdrop.",
    "Authority, calm power, boardroom ready.",
    sort_order=11,
)
_FOUNDER = _style(
    "founder_portrait",
    "Founder Portrait",
    "Business",
    "Startup founder energy — credible and human.",
    "Startup founder portrait, relaxed confidence, modern tech-business look.",
    "Soft window light mixed with subtle studio fill.",
    "35mm environmental portrait, natural perspective.",
    "Smart casual knit or open collar shirt, contemporary founder style.",
    "Bright modern workspace or clean minimalist studio.",
    "Innovative, approachable, authentic.",
    sort_order=12,
)
_REAL_ESTATE = _style(
    "real_estate_agent",
    "Real Estate Agent",
    "Business",
    "Friendly expert who sells trust.",
    "Real estate professional portrait, warm trustworthy smile.",
    "Bright high-key lifestyle light, flattering skin tones.",
    "85mm, crisp focus on face, gentle background bokeh.",
    "Polished business attire, subtle luxury accessories without logos.",
    "Upscale property interior blur or bright neutral backdrop.",
    "Welcoming, successful, local market leader.",
    sort_order=13,
)
_CONSULTANT = _style(
    "consultant_look",
    "Consultant Look",
    "Business",
    "Premium advisor clients want to pay.",
    "Management consultant portrait, thoughtful confident expression.",
    "Clean soft studio lighting, neutral color grade.",
    "85mm head-and-shoulders, classic consulting composition.",
    "Refined business formal, understated elegance.",
    "Soft gray or glass office bokeh background.",
    "Analytical, premium, reliable.",
    sort_order=14,
)
_BEAUTY_MASTER = _style(
    "beauty_master_profile",
    "Beauty Master Profile",
    "Business",
    "Beauty professional clients instantly trust.",
    "Beauty industry professional portrait, flawless natural grooming.",
    "Beauty dish soft light, glossy catchlights, clean skin rendering.",
    "85mm close portrait, editorial beauty framing.",
    "Stylish salon-owner attire, tasteful makeup, modern aesthetic.",
    "Bright salon interior blur or cream studio backdrop.",
    "Expert, elegant, aspirational.",
    sort_order=15,
)
_PODCAST = _style(
    "podcast_guest",
    "Podcast Guest",
    "Business",
    "Memorable guest shot for thumbnails and bios.",
    "Podcast guest portrait, engaging expression mid-conversation energy.",
    "Warm key light, subtle colored rim, studio podcast vibe.",
    "50mm, shallow depth, microphone subtly out of focus optional.",
    "Casual smart top, headphones optional near frame edge.",
    "Dark acoustic foam or moody studio background.",
    "Charismatic, media-ready, conversational.",
    sort_order=16,
)
_SPEAKER = _style(
    "speaker_profile",
    "Speaker Profile",
    "Business",
    "Stage-ready speaker credibility.",
    "Conference speaker portrait, inspiring confident presence.",
    "Spotlight key with soft fill, slight dramatic contrast.",
    "70mm, chest-up framing, stage-ready composition.",
    "Speaker blazer or stage outfit, lapel mic optional subtle.",
    "Blurred auditorium or stage lights bokeh.",
    "Inspiring, credible, keynote energy.",
    sort_order=17,
)

# --- Dating / Social (6) ---
_GOLDEN_HOUR = _style(
    "golden_hour_dating",
    "Golden Hour Dating",
    "Dating",
    "Warm authentic dating-app magnetism.",
    "Outdoor dating profile portrait at golden hour, natural smile.",
    "Warm backlight, sun flare, soft haze, flattering skin.",
    "85mm, f/1.8, creamy bokeh.",
    "Casual stylish outfit, natural hair, minimal heavy makeup.",
    "Park, rooftop, or open sky sunset background.",
    "Romantic, approachable, real-not-filtered.",
    trend_level="high",
    is_trending=True,
    sort_order=20,
    use_case=["dating", "instagram"],
)
_COFFEE = _style(
    "coffee_date",
    "Coffee Date",
    "Dating",
    "Cozy date vibe without looking staged.",
    "Lifestyle portrait in cozy cafe setting, candid relaxed smile.",
    "Warm tungsten interior light, soft window mix.",
    "50mm lifestyle framing, environmental portrait.",
    "Casual date outfit, sweater or light jacket.",
    "Cafe interior bokeh, cups and warm tones blurred.",
    "Intimate, friendly, spontaneous.",
    sort_order=21,
    use_case=["dating"],
)
_NATURAL_SMILE = _style(
    "natural_smile",
    "Natural Smile",
    "Dating",
    "Genuine smile that feels real on Tinder.",
    "Close natural portrait with genuine soft smile, eye contact.",
    "Soft diffused daylight, even skin, no harsh shadows.",
    "85mm portrait, shallow depth.",
    "Simple clean top, minimal accessories.",
    "Neutral outdoor blur or soft bright wall.",
    "Authentic, warm, trustworthy.",
    sort_order=22,
)
_URBAN = _style(
    "urban_confidence",
    "Urban Confidence",
    "Dating",
    "City confidence for modern profiles.",
    "Urban street portrait, confident stance, contemporary style.",
    "Overcast soft city light or blue hour ambient.",
    "35mm street portrait, slight environmental context.",
    "Modern streetwear or smart urban casual.",
    "City architecture and lights bokeh.",
    "Cool, confident, contemporary.",
    sort_order=23,
)
_WEEKEND = _style(
    "weekend_lifestyle",
    "Weekend Lifestyle",
    "Dating",
    "Relaxed weekend energy people want to join.",
    "Weekend lifestyle portrait, relaxed laugh or easy smile.",
    "Natural daylight, airy exposure.",
    "50mm lifestyle, candid framing.",
    "Casual weekend outfit, denim jacket or relaxed shirt.",
    "Park, brunch terrace, or residential street blur.",
    "Fun, relaxed, socially magnetic.",
    sort_order=24,
)
_EVENING = _style(
    "elegant_evening",
    "Elegant Evening",
    "Dating",
    "Evening elegance for upscale dating apps.",
    "Evening portrait with elegant styling, subtle sophisticated smile.",
    "Soft warm indoor light, gentle highlights on cheekbones.",
    "85mm, classic evening portrait composition.",
    "Evening dress or tailored evening wear, understated jewelry.",
    "Dim restaurant or hotel lounge bokeh.",
    "Refined, alluring, classy.",
    sort_order=25,
)

# --- Luxury (7) ---
_OLD_MONEY = _style(
    "old_money_portrait",
    "Old Money Portrait",
    "Luxury",
    "Quiet wealth, calm confidence, old-world refinement.",
    "Old money editorial portrait, understated luxury, composed expression.",
    "Soft natural window light, muted tones, filmic grain subtle.",
    "85mm classic portrait, timeless framing.",
    "Cashmere, linen, heritage tailoring, no logos.",
    "Country estate interior, wood paneling, or garden blur.",
    "Refined, calm, generational wealth aesthetic.",
    trend_level="high",
    is_trending=True,
    sort_order=30,
    ab_test_group="luxury_a",
)
_QUIET_LUXURY = _style(
    "quiet_luxury",
    "Quiet Luxury",
    "Luxury",
    "Stealth wealth — expensive without shouting.",
    "Quiet luxury portrait, minimal styling, premium fabric focus.",
    "Soft neutral studio light, low saturation grade.",
    "85mm, clean composition, negative space.",
    "Neutral tonal designer-inspired outfit, no visible logos.",
    "Textured stone or beige architectural backdrop.",
    "Understated, expensive, serene.",
    sort_order=31,
)
_HOTEL = _style(
    "luxury_hotel_lobby",
    "Luxury Hotel Lobby",
    "Luxury",
    "Five-star arrival moment.",
    "Portrait in luxury hotel lobby, poised traveler elegance.",
    "Warm ambient lobby chandeliers, marble reflections.",
    "35mm environmental luxury portrait.",
    "Travel chic coat or evening wear, polished grooming.",
    "Marble floors, grand lobby, soft gold lighting bokeh.",
    "Jet-set, premium, cosmopolitan.",
    sort_order=32,
    is_trending=True,
)
_DUBAI = _style(
    "dubai_mood",
    "Dubai Mood",
    "Luxury",
    "High-status Gulf luxury editorial.",
    "Luxury desert-city portrait, confident sun-ready elegance.",
    "Bright golden sunlight, clean highlights, modern grade.",
    "50mm, skyline or desert luxury hints in bokeh.",
    "White or sand-toned luxury resort wear.",
    "Modern skyline blur or desert luxury resort background.",
    "Opulent, warm, international status.",
    sort_order=33,
)
_CEO_DARK = _style(
    "ceo_after_dark",
    "CEO After Dark",
    "Luxury",
    "Powerful evening executive — safe corporate villain energy.",
    "Evening executive portrait, dramatic city-night confidence.",
    "Low-key lighting, city lights rim, controlled shadows.",
    "50mm night portrait, cinematic contrast.",
    "Dark tailored suit, open collar or turtleneck under jacket.",
    "City night skyline through glass or rooftop lights.",
    "Powerful, cinematic, high-status evening.",
    trend_level="high",
    is_trending=True,
    sort_order=34,
)
_ROOFTOP = _style(
    "rooftop_night",
    "Rooftop Night",
    "Luxury",
    "Rooftop nightlife prestige.",
    "Rooftop night portrait, wind in hair, city lights behind.",
    "Neon city bokeh, soft key on face, night exposure balance.",
    "35mm, environmental night portrait.",
    "Evening luxury outfit, statement coat.",
    "Rooftop bar lights and skyline bokeh.",
    "Glamorous, urban, exclusive.",
    sort_order=35,
)
_JET = _style(
    "private_jet_mood",
    "Private Jet Mood",
    "Luxury",
    "Private aviation lifestyle fantasy, safe and logo-free.",
    "Private jet interior portrait, relaxed elite traveler mood.",
    "Soft cabin window light, cream leather reflections.",
    "50mm interior lifestyle portrait.",
    "Luxury travel cashmere, sunglasses optional in hand not worn.",
    "Aircraft cabin leather seats, oval window sky blur.",
    "Elite, comfortable, aspirational travel.",
    sort_order=36,
)

# --- Cinematic (5) ---
_DARK_HERO = _style(
    "dark_hero",
    "Dark Hero",
    "Cinematic",
    "Movie hero lighting without franchise references.",
    "Cinematic dark hero portrait, intense gaze, dramatic shadows.",
    "Hard rim light, deep shadows, teal-orange subtle grade.",
    "50mm anamorphic feel, shallow depth.",
    "Dark textured coat, minimal wardrobe.",
    "Stormy sky or industrial dark backdrop.",
    "Epic, brooding, cinematic tension.",
    sort_order=40,
)
_NOIR = _style(
    "noir_portrait",
    "Noir Portrait",
    "Cinematic",
    "Classic noir city elegance — not a celebrity cosplay.",
    "Film noir portrait, formal vintage city mood, mysterious expression.",
    "Single hard key, venetian shadow pattern optional subtle.",
    "85mm classic noir framing.",
    "Vintage formal coat, hat optional subtle off-frame.",
    "Rain-slick city night bokeh, neon reflections.",
    "Mysterious, timeless, cinematic noir.",
    sort_order=41,
)
_RAINY = _style(
    "rainy_street",
    "Rainy Street",
    "Cinematic",
    "Moody rain-soaked street portrait.",
    "Portrait on rainy city street, reflective wet pavement lights.",
    "Diffused overcast rain light, specular highlights on rain.",
    "35mm street cinematic framing.",
    "Dark coat, umbrella optional away from face.",
    "Wet street, neon reflections, evening rain.",
    "Melancholic, cinematic, atmospheric.",
    sort_order=42,
)
_MOVIE_POSTER = _style(
    "movie_poster",
    "Movie Poster",
    "Cinematic",
    "Blockbuster poster energy, generic original character.",
    "Movie poster style portrait, heroic three-quarter angle, graded contrast.",
    "Dramatic backlight and fill, high production value.",
    "Wide-ish portrait crop, poster-style headroom.",
    "Costume-inspired formal hero outfit, no IP characters.",
    "Smoke, particles, or epic sky gradient backdrop.",
    "Heroic, larger-than-life, theatrical.",
    sort_order=43,
)
_ROYAL = _style(
    "royal_drama",
    "Royal Drama",
    "Cinematic",
    "Regal drama lighting, fictional nobility aesthetic.",
    "Royal drama portrait, regal posture, rich fabrics.",
    "Chiaroscuro window light, painterly softness.",
    "85mm classical portrait composition.",
    "Velvet coat or formal regal-inspired attire, no crowns unless subtle.",
    "Palace interior blur, columns, warm stone.",
    "Majestic, dramatic, period elegance.",
    sort_order=44,
)

# --- Viral (4) ---
_NINETIES = _style(
    "nineties_studio_flash",
    "90s Studio Flash",
    "Viral",
    "Trending 90s studio flash nostalgia.",
    "90s studio flash portrait, direct flash look, nostalgic color.",
    "On-camera flash aesthetic, crisp shadows, retro grade.",
    "50mm studio snapshot feel.",
    "Retro casual outfit, denim or graphic-free top.",
    "Seamless studio backdrop, retro color gels subtle.",
    "Playful, nostalgic, viral throwback.",
    trend_level="high",
    is_trending=True,
    sort_order=50,
)
_LINKEDIN_GLOW = _style(
    "linkedin_glow_up",
    "LinkedIn Glow Up",
    "Viral",
    "Viral professional glow-up transformation.",
    "LinkedIn glow-up portrait, polished skin, bright confident eyes.",
    "Bright soft studio, subtle glow, commercial retouch balanced natural.",
    "85mm, clean headshot crop.",
    "Crisp professional top, groomed hair.",
    "Clean white or soft gradient studio.",
    "Transformed, hire-me energy, viral professional trend.",
    trend_level="high",
    is_trending=True,
    sort_order=51,
)
_PASSPORT = _style(
    "passport_glow_up",
    "Passport Photo Glow Up",
    "Viral",
    "ID-photo structure with premium glow-up finish.",
    "Passport-style headshot glow-up, straight posture, neutral expression softened.",
    "Even flat studio light upgraded to premium soft beauty light.",
    "85mm straight-on, official framing but editorial quality.",
    "Plain solid top, neat grooming.",
    "Clean neutral passport-style background, premium color.",
    "Viral ID glow-up, neat, surprisingly premium.",
    sort_order=52,
)
_EURO_SUMMER = _style(
    "euro_summer",
    "Euro Summer",
    "Viral",
    "European summer travel profile aesthetic.",
    "Euro summer travel portrait, sun-kissed skin, breezy outfit.",
    "Harsh midday sun softened, warm film grade.",
    "35mm vacation portrait, sea or architecture hints.",
    "Linen shirt, sunglasses on head optional, resort casual.",
    "Mediterranean coast, white buildings, blue sea blur.",
    "Carefree, vacation, instagram travel trend.",
    trend_level="high",
    is_trending=True,
    sort_order=53,
)

COMMERCIAL_STYLES: dict[str, dict[str, Any]] = {
    s["key"]: s
    for s in [
        _LINKEDIN,
        _CEO,
        _FOUNDER,
        _REAL_ESTATE,
        _CONSULTANT,
        _BEAUTY_MASTER,
        _PODCAST,
        _SPEAKER,
        _GOLDEN_HOUR,
        _COFFEE,
        _NATURAL_SMILE,
        _URBAN,
        _WEEKEND,
        _EVENING,
        _OLD_MONEY,
        _QUIET_LUXURY,
        _HOTEL,
        _DUBAI,
        _CEO_DARK,
        _ROOFTOP,
        _JET,
        _DARK_HERO,
        _NOIR,
        _RAINY,
        _MOVIE_POSTER,
        _ROYAL,
        _NINETIES,
        _LINKEDIN_GLOW,
        _PASSPORT,
        _EURO_SUMMER,
    ]
}


def get_style(style_key: str) -> dict[str, Any] | None:
    from imodel.styles.seasonal_styles import SEASONAL_STYLES

    return COMMERCIAL_STYLES.get(style_key) or SEASONAL_STYLES.get(style_key)


def list_styles(*, active_only: bool = True, category: str | None = None) -> list[dict[str, Any]]:
    items = list(COMMERCIAL_STYLES.values())
    if active_only:
        items = [s for s in items if s.get("is_active")]
    if category:
        items = [s for s in items if s.get("category") == category]
    return sorted(items, key=lambda s: (s.get("sort_order", 999), s.get("name", "")))


def list_trending() -> list[dict[str, Any]]:
    return [s for s in list_styles() if s.get("is_trending")]

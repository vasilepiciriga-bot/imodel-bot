
# prompt_engine.py
# Prompt crafting utilities: Copy mode vision analysis + Photoshoot Prompt Builder 2.0
from typing import Optional, Dict, Any, Tuple
import base64, json, os

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL_VISION = os.getenv("OPENAI_MODEL_VISION", os.getenv("OPENAI_MODEL", "gpt-4o"))

SYSTEM_PROMPT = (
    "You are a senior prompt engineer for photo generation. "
    "Given ONE reference photo, output a JSON object with fields: "
    "{prompt, negative}. "
    "The 'prompt' MUST be a SINGLE LINE English text describing the exact scene, lighting, lens, pose, framing, attire, background and mood, "
    "suitable for text-to-image. Never mention real people or brands. Keep the subject generic: 'adult male' or 'adult person'. "
    "The 'negative' MUST be a concise comma-separated list forbidding irrelevant elements (e.g., 'outdoor, color, daylight, trees, ...'). "
    "Be precise and technical; prefer photographic terms (Rembrandt light, 85mm, f/2, seamless backdrop, vignette). "
    "Do not include JSON code fences. Do not add extra keys."
)

NEGATIVE_DEFAULTS = (
    "low-res, artifacts, watermark, text, logo, extra limbs, duplicates, "
    "color, cartoon, cgi, 3d, overbeautify, makeup, face reshaping, age change"
)

def _b64(img_bytes: bytes) -> str:
    return base64.b64encode(img_bytes).decode("utf-8")

def _craft_simple_prompt(user_text: str, gender: str = "") -> str:
    """Light GPT refinement of free-text into a photoshoot prompt line."""
    if not OPENAI_API_KEY or OpenAI is None:
        return user_text
    client = OpenAI(api_key=OPENAI_API_KEY)
    gender_hint = f"The subject is {gender}. " if gender else ""
    system = (
        "You are a prompt engineer for face-preserving portrait photo generation. "
        "Rewrite the user description into ONE LINE of precise English: "
        "environment, mood, lighting, lens type, pose, attire, background. "
        "Never mention real people or brands. Subject: 'adult person'. "
        "Output ONLY the prompt text, no quotes, no JSON."
    )
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL_VISION,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": f"{gender_hint}{user_text}"},
            ],
            temperature=0.3,
            max_tokens=200,
        )
        result = (resp.choices[0].message.content or "").strip().strip('"')
        return " ".join(result.split()) or user_text
    except Exception:
        return user_text


def _aspect_to_wh(aspect_ratio: str) -> Tuple[int, int]:
    """Map aspect ratio string to (width, height) at ~768px base."""
    return {
        "1:1":  (768, 768),
        "16:9": (1024, 576),
        "9:16": (576, 1024),
        "4:3":  (1024, 768),
        "3:4":  (768, 1024),
    }.get(aspect_ratio, (768, 768))


def analyze_selfie_identity(selfie_bytes: bytes) -> Dict[str, str]:
    """
    Identity Passport — builds a per-user appearance profile for prompt personalization.

    Returns dict with keys:
        gender, age_range, eye_color, skin_tone, hair_color,
        identity_layer (ready-to-inject prefix string),
        gender_negative (clothing terms to exclude in negative prompt)
    Returns empty dict on any failure (caller must handle gracefully).
    """
    if not selfie_bytes or not OPENAI_API_KEY or OpenAI is None:
        return {}
    client = OpenAI(api_key=OPENAI_API_KEY)
    img_url = f"data:image/jpeg;base64,{_b64(selfie_bytes)}"
    system = (
        "You are an expert at analyzing portrait photos for AI image generation. "
        "Study this photo carefully and determine the person's biological characteristics. "
        "Return ONLY a compact JSON with these exact fields — no other text, no code fences:\n"
        "{\n"
        "  \"gender\": \"man\" or \"woman\",\n"
        "  \"age_range\": \"teens\" or \"20s\" or \"30s\" or \"40s\" or \"50s+\",\n"
        "  \"eye_color\": \"brown\" or \"blue\" or \"green\" or \"hazel\" or \"gray\" or \"dark\",\n"
        "  \"skin_tone\": \"fair\" or \"medium\" or \"olive\" or \"dark\",\n"
        "  \"hair_color\": \"dark\" or \"blonde\" or \"red\" or \"gray\" or \"none\"\n"
        "}\n"
        "CRITICAL: gender must be either 'man' or 'woman' — never 'person' or ambiguous. "
        "Look at facial bone structure, jaw, brow ridge, and overall features to determine gender confidently."
    )
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL_VISION,
            messages=[
                {"role": "system", "content": system},
                {"role": "user", "content": [
                    {"type": "text", "text": "Analyze this portrait and return the JSON identity profile."},
                    {"type": "image_url", "image_url": {"url": img_url, "detail": "low"}},
                ]},
            ],
            temperature=0.1,
            max_tokens=120,
            timeout=15,
        )
        raw = (resp.choices[0].message.content or "").strip().strip("`\n")
        if raw.lower().startswith("json"):
            raw = raw[4:].strip()
        data = json.loads(raw)
        gender = str(data.get("gender", "woman")).strip().lower()
        if gender not in ("man", "woman"):
            gender = "woman"
        age_range = str(data.get("age_range", "")).strip()
        eye_color = str(data.get("eye_color", "")).strip()
        skin_tone = str(data.get("skin_tone", "")).strip()
        hair_color = str(data.get("hair_color", "")).strip()

        # Build identity_layer — goes at the START of the prompt as an anchor
        # Format: "adult man in his 30s, blue eyes, medium skin, dark hair"
        gender_word = "man" if gender == "man" else "woman"
        pronoun = "his" if gender == "man" else "her"
        parts = [f"adult {gender_word}"]
        if age_range:
            parts.append(f"in {pronoun} {age_range}")
        if eye_color:
            parts.append(f"{eye_color} eyes")
        if skin_tone:
            parts.append(f"{skin_tone} skin")
        if hair_color and hair_color != "none":
            parts.append(f"{hair_color} hair")
        identity_layer = ", ".join(parts)

        # Gender negative — prevents wrong-gender clothing from appearing
        gender_negative = ""
        if gender == "man":
            gender_negative = "dress, skirt, women's clothing, feminine fashion, female attire, high heels"
        # For women we don't restrict — women can wear suits, jackets, any style

        return {
            "gender": gender,
            "age_range": age_range,
            "eye_color": eye_color,
            "skin_tone": skin_tone,
            "hair_color": hair_color,
            "identity_layer": identity_layer,
            "gender_negative": gender_negative,
        }
    except Exception:
        return {}


def build_photoshoot_prompt(
    mode: str,
    style: str = "",
    user_request: str = "",
    gender: str = "",
    aspect_ratio: str = "1:1",
    identity_passport: Optional[Dict[str, str]] = None,
    style_variant: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Photoshoot Prompt Builder 2.0 — independent module.
    Phase 2: adds identity_passport injection and style_variant support.

    Args:
        mode:             One of everyday | premium | vogue | ceo | dating | luxury | custom
        style:            Optional style description / reference text
        user_request:     Free-text vision from user
        gender:           Optional subject gender hint for GPT refinement
        aspect_ratio:     Target aspect ratio string e.g. "1:1", "9:16"
        identity_passport: Dict from analyze_selfie_identity() — injects identity_layer
        style_variant:    Sub-style key within the mode (e.g. "editorial" for vogue)

    Returns:
        { finalPrompt, negativePrompt, modelParams, aspectRatio, styleName }
    """
    try:
        from photoshoot_modes import apply_prompt_layer, get_mode_config, get_mode_negative
    except ImportError:
        return {
            "finalPrompt": user_request or style or "",
            "negativePrompt": NEGATIVE_DEFAULTS,
            "modelParams": {},
            "aspectRatio": aspect_ratio,
            "styleName": mode,
        }

    cfg = get_mode_config(mode) or {}
    base_text = (user_request or style or "").strip()

    # Identity layer from passport (Phase 2)
    identity_layer = ""
    if identity_passport:
        identity_layer = str(identity_passport.get("identity_layer", "")).strip()
        if not gender and identity_passport.get("gender"):
            gender = str(identity_passport["gender"])

    # Build base prompt:
    # 1. GPT refine user request if provided
    # 2. Inject identity_layer as enrichment
    if base_text:
        base_prompt = _craft_simple_prompt(base_text, gender)
    elif identity_layer:
        base_prompt = identity_layer
    else:
        base_prompt = ""

    # Enrich with identity layer if not already used as base
    if identity_layer and base_text:
        base_prompt = f"{base_prompt}, {identity_layer}"

    # Apply mode-specific prompt layer + optional sub-style variant
    final_prompt = apply_prompt_layer(base_prompt, mode, style_variant=style_variant)

    # Negative prompt: mode-specific layer > NEGATIVE_DEFAULTS
    mode_negative = get_mode_negative(mode)
    negative_prompt = f"{mode_negative}, {NEGATIVE_DEFAULTS}" if mode_negative else NEGATIVE_DEFAULTS

    # Model params
    w, h = _aspect_to_wh(aspect_ratio)
    mode_label = cfg.get("label", {})
    style_name = mode_label.get("en", mode) if isinstance(mode_label, dict) else str(mode_label or mode)

    return {
        "finalPrompt": final_prompt,
        "negativePrompt": negative_prompt,
        "modelParams": {
            "width": w,
            "height": h,
            "num_outputs": cfg.get("n_generations", 1),
            "num_inference_steps": 30,
            "guidance_scale": 7.5,
        },
        "aspectRatio": aspect_ratio,
        "styleName": style_name,
    }


def craft_prompt_from_style_image(style_bytes: bytes) -> Optional[Dict[str, str]]:
    """Return {'prompt': str, 'negative': str} from a style image via OpenAI Vision."""
    if not OPENAI_API_KEY or OpenAI is None:
        return None
    client = OpenAI(api_key=OPENAI_API_KEY)
    img_url = f"data:image/jpeg;base64,{_b64(style_bytes)}"
    messages = [
        { "role": "system", "content": SYSTEM_PROMPT },
        { "role": "user", "content": [
            {"type": "text", "text": "Analyze this photo and return JSON with {prompt, negative}."},
            {"type": "image_url", "image_url": {"url": img_url}},
        ]}
    ]
    try:
        resp = client.chat.completions.create(
            model=OPENAI_MODEL_VISION,
            messages=messages,
            temperature=0.2,
            max_tokens=400,
        )
        raw = (resp.choices[0].message.content or "").strip()
        # Try parse JSON (may come with code fences occasionally)
        raw = raw.strip("` \n")
        if raw.startswith("json"):
            raw = raw[4:].strip()
        data = json.loads(raw)
        prompt = (data.get("prompt") or "").strip()
        negative = (data.get("negative") or "").strip()
        # Enforce defaults
        if not negative:
            negative = NEGATIVE_DEFAULTS
        else:
            negative = negative + ", " + NEGATIVE_DEFAULTS
        # One-line cleanup
        prompt = " ".join(prompt.split())
        negative = ", ".join([p.strip() for p in negative.split(",") if p.strip()])
        return {"prompt": prompt, "negative": negative}
    except Exception as e:
        # Fallback minimal prompt
        return {"prompt": "adult person, exact same scene, lighting, pose, framing and background as the reference photo.",
                "negative": NEGATIVE_DEFAULTS}

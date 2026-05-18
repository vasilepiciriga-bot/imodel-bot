
# prompt_engine.py
# Robust prompt crafting for Copy mode using OpenAI Vision with strict schema.
from typing import Optional, Dict, Any
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
    "{prompt, negative, seed_hint}. "
    "The 'prompt' MUST be a SINGLE LINE English text describing the exact scene, lighting, lens, pose, framing, attire, background and mood, "
    "suitable for text-to-image. Never mention real people or brands. Keep the subject generic: 'adult male' or 'adult person'. "
    "The 'negative' MUST be a concise comma-separated list forbidding irrelevant elements (e.g., 'outdoor, color, daylight, trees, ...'). "
    "The 'seed_hint' MUST be a short stable string derived from composition keywords (e.g., 'studio-bw-thinker-85mm'). "
    "Be precise and technical; prefer photographic terms (Rembrandt light, 85mm, f/2, seamless backdrop, vignette). "
    "Do not include JSON code fences. Do not add extra keys."
)

NEGATIVE_DEFAULTS = (
    "low-res, artifacts, watermark, text, logo, extra limbs, duplicates, "
    "color, cartoon, cgi, 3d, overbeautify, makeup, face reshaping, age change"
)

def _b64(img_bytes: bytes) -> str:
    return base64.b64encode(img_bytes).decode("utf-8")

def craft_prompt_from_style_image(style_bytes: bytes) -> Optional[Dict[str, str]]:
    \"\"\"Return {'prompt': str, 'negative': str, 'seed_hint': str} from a style image via OpenAI Vision.\"\"\"
    if not OPENAI_API_KEY or OpenAI is None:
        return None
    client = OpenAI(api_key=OPENAI_API_KEY)
    img_url = f"data:image/jpeg;base64,{_b64(style_bytes)}"
    messages = [
        { "role": "system", "content": SYSTEM_PROMPT },
        { "role": "user", "content": [
            {"type": "text", "text": "Analyze this photo and return JSON with {prompt, negative, seed_hint}."},
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
        seed_hint = (data.get("seed_hint") or "").strip()
        # Enforce defaults
        if not negative:
            negative = NEGATIVE_DEFAULTS
        else:
            negative = negative + ", " + NEGATIVE_DEFAULTS
        # One-line cleanup
        prompt = " ".join(prompt.split())
        negative = ", ".join([p.strip() for p in negative.split(",") if p.strip()])
        seed_hint = "-".join(seed_hint.split()).lower() or "style-seed"
        return {"prompt": prompt, "negative": negative, "seed_hint": seed_hint}
    except Exception as e:
        # Fallback minimal prompt
        return {"prompt": "adult person, exact same scene, lighting, pose, framing and background as the reference photo.",
                "negative": NEGATIVE_DEFAULTS,
                "seed_hint": "style-seed"}

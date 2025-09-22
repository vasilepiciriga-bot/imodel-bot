import io
import time
from typing import List, Dict, Optional, Tuple

import replicate
from bot.config import settings


def _run_with_retry(model: str, inputs: Dict, retries: int = 2, backoff: float = 1.0):
    last_err = None
    for i in range(retries + 1):
        try:
            return replicate.run(model, input=inputs)
        except Exception as e:
            last_err = e
            time.sleep(backoff * (i + 1))
    raise last_err  # type: ignore


def run_img2img(
    prompt: str,
    negative: str,
    image_bytes: bytes,
    strength: float,
    guidance: float,
    seed: int,
    scheduler: Optional[str] = None,
    control: Optional[Dict] = None,
) -> bytes:
    """Img2Img via Replicate. Prefers FLUX models; falls back to SDXL img2img."""
    model = settings.IMG_MODEL
    img_stream = io.BytesIO(image_bytes)

    inputs: Dict = {
        "prompt": prompt,
        "negative_prompt": negative,
        "image": img_stream,
        "strength": float(strength),
        "guidance_scale": float(guidance),
        "seed": int(seed),
    }
    if scheduler:
        inputs["scheduler"] = scheduler
    if control:
        # Pass through control images/weights if supported by the target model
        inputs.update(control)

    # Try the preferred model first
    try:
        out = _run_with_retry(model, inputs)
    except Exception:
        # Fallback to SDXL img2img
        out = _run_with_retry("stability-ai/sdxl", inputs)

    # Replicate may return URL(s) or bytes. Normalize to bytes.
    if isinstance(out, list) and out:
        out = out[-1]
    if isinstance(out, (bytes, bytearray)):
        return bytes(out)
    if isinstance(out, str) and out.startswith("http"):
        # Let Replicate fetcher turn it into bytes in a second run
        import requests
        r = requests.get(out, timeout=30)
        r.raise_for_status()
        return r.content
    raise RuntimeError("Img2Img returned unexpected output")


def run_upscale(image_bytes: bytes, scale: int = 2) -> bytes:
    img_stream = io.BytesIO(image_bytes)
    inputs = {
        "image": img_stream,
        "scale": int(scale),
        "face_enhance": False,
    }
    out = _run_with_retry(settings.UPSCALE_MODEL, inputs)
    if isinstance(out, list) and out:
        out = out[-1]
    if isinstance(out, (bytes, bytearray)):
        return bytes(out)
    if isinstance(out, str) and out.startswith("http"):
        import requests
        r = requests.get(out, timeout=30)
        r.raise_for_status()
        return r.content
    raise RuntimeError("Upscale returned unexpected output")


def detect_small_objects(image_bytes: bytes, classes: List[str]) -> List[List[Tuple[int, int]]]:
    """
    Use Grounding-DINO + SAM (or nearest stack on Replicate) to get small object polygons.
    Returns list of polygons, each polygon is list of (x,y) integer points in image coordinates.
    If detection is unavailable or fails, returns [].
    """
    try:
        # Example stack; adjust to available endpoints in your Replicate account.
        # Many community models wrap detection+segmentation into a single call returning masks.
        model = "yolov8/segments"  # fallback generic segmenter; replace with grounding-dino+sam wrapper if available
        img_stream = io.BytesIO(image_bytes)
        out = _run_with_retry(model, {"image": img_stream})
        # Expect polygons as list of dicts with "points" key or similar
        polys: List[List[Tuple[int, int]]] = []
        if isinstance(out, list):
            for item in out:
                pts = item.get("points") if isinstance(item, dict) else None
                if pts:
                    poly = [(int(x), int(y)) for x, y in pts]
                    polys.append(poly)
        return polys
    except Exception:
        return []


def inpaint(image_bytes: bytes, mask_bytes: bytes) -> bytes:
    img_stream = io.BytesIO(image_bytes)
    mask_stream = io.BytesIO(mask_bytes)
    inputs = {"image": img_stream, "mask": mask_stream}
    out = _run_with_retry(settings.INPAINT_MODEL, inputs)
    if isinstance(out, list) and out:
        out = out[-1]
    if isinstance(out, (bytes, bytearray)):
        return bytes(out)
    if isinstance(out, str) and out.startswith("http"):
        import requests
        r = requests.get(out, timeout=30)
        r.raise_for_status()
        return r.content
    raise RuntimeError("Inpaint returned unexpected output")


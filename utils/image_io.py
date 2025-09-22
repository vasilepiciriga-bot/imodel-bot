from typing import Tuple
from PIL import Image, ImageOps
import io


def bytes_to_pil(b: bytes) -> Image.Image:
    img = Image.open(io.BytesIO(b))
    img = ImageOps.exif_transpose(img)
    return img.convert("RGB")


def pil_to_bytes(img: Image.Image, quality: int = 92) -> bytes:
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=quality, optimize=True)
    return buf.getvalue()


def maybe_downscale(img: Image.Image, max_side: int = 3500) -> Image.Image:
    w, h = img.size
    long_side = max(w, h)
    if long_side <= max_side:
        return img
    scale = max_side / float(long_side)
    new_size = (int(w * scale), int(h * scale))
    return img.resize(new_size, Image.LANCZOS)


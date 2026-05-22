"""Negative prompt baselines."""

BASE_NEGATIVE = (
    "different person, changed ethnicity, changed age, face reshaped, de-aged, over-beautified, "
    "plastic skin, doll face, fake smile, uncanny face, distorted face, asymmetrical eyes, extra fingers, "
    "extra hands, bad anatomy, low quality, blurry, pixelated, watermark, logo, text, brand name, "
    "celebrity, copyrighted character, nudity, sexual content, violence, weapon"
)

COPY_MODE_EXTRA_NEGATIVE = (
    "changed background, different background, different scene, composition changed, new objects, "
    "added elements, beautify filter, airbrushed skin, over-retouched skin, body reshaped"
)


def merge_negative(*parts: str) -> str:
    seen: set[str] = set()
    out: list[str] = []
    for part in parts:
        for chunk in part.split(","):
            token = chunk.strip().lower()
            if token and token not in seen:
                seen.add(token)
                out.append(chunk.strip())
    return ", ".join(out)

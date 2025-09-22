from typing import List
from PIL import Image, ImageDraw, ImageFont
import re


def _grid_labels(rows: int, cols: int):
    letters = [chr(ord('A') + i) for i in range(rows)]
    numbers = [str(i + 1) for i in range(cols)]
    return letters, numbers


def make_grid_overlay(image: Image.Image, rows: int = 6, cols: int = 6) -> Image.Image:
    img = image.copy().convert("RGB")
    draw = ImageDraw.Draw(img)
    w, h = img.size
    dx = w / cols
    dy = h / rows
    # grid lines
    for c in range(1, cols):
        x = int(c * dx)
        draw.line([(x, 0), (x, h)], fill=(0, 255, 0), width=2)
    for r in range(1, rows):
        y = int(r * dy)
        draw.line([(0, y), (w, y)], fill=(0, 255, 0), width=2)
    # labels
    letters, numbers = _grid_labels(rows, cols)
    try:
        font = ImageFont.truetype("arial.ttf", max(18, int(min(dx, dy) * 0.12)))
    except Exception:
        font = ImageFont.load_default()
    for r_idx, L in enumerate(letters):
        for c_idx, N in enumerate(numbers):
            x = int(c_idx * dx + 6)
            y = int(r_idx * dy + 4)
            draw.text((x, y), f"{L}{N}", fill=(0, 255, 0), font=font)
    return img


_CELL_RE = re.compile(r"^[A-Za-z]\s*\d+$")


def _parse_cells(cells: List[str], rows: int, cols: int):
    letters, numbers = _grid_labels(rows, cols)
    Lmap = {L.upper(): i for i, L in enumerate(letters)}
    Nmap = {n: j for j, n in enumerate(numbers)}
    out = []
    for raw in cells:
        tok = raw.strip().upper().replace(" ", "")
        if not tok:
            continue
        # split L + number
        L = tok[0]
        N = tok[1:]
        if L in Lmap and N in Nmap:
            out.append((Lmap[L], Nmap[N]))
    return out


def cells_to_mask(image: Image.Image, cells: List[str], rows: int = 6, cols: int = 6, feather: int = 8) -> Image.Image:
    w, h = image.size
    dx = w / cols
    dy = h / rows
    mask = Image.new("L", (w, h), 0)
    draw = ImageDraw.Draw(mask)
    idxs = _parse_cells(cells, rows, cols)
    for r_idx, c_idx in idxs:
        x0 = int(c_idx * dx)
        y0 = int(r_idx * dy)
        x1 = int((c_idx + 1) * dx)
        y1 = int((r_idx + 1) * dy)
        draw.rectangle([x0, y0, x1, y1], fill=255)

    if feather > 0:
        # simple blur feather
        from PIL import ImageFilter
        mask = mask.filter(ImageFilter.GaussianBlur(radius=feather))
    return mask.convert("RGB")


from typing import Literal
import cv2
import numpy as np
from PIL import Image


def _pil_to_cv(img: Image.Image) -> np.ndarray:
    arr = np.array(img.convert("RGB"))
    return cv2.cvtColor(arr, cv2.COLOR_RGB2BGR)


def _cv_to_pil(img: np.ndarray) -> Image.Image:
    rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)


def fix_verticals(image: Image.Image) -> Image.Image:
    """Attempt to straighten vertical lines gently. If uncertain, returns original image."""
    cv = _pil_to_cv(image)
    gray = cv2.cvtColor(cv, cv2.COLOR_BGR2GRAY)
    gray = cv2.GaussianBlur(gray, (3, 3), 0)
    edges = cv2.Canny(gray, 40, 120)
    lines = cv2.HoughLines(edges, 1, np.pi / 180.0, 160)
    if lines is None:
        return image
    # Collect near-vertical angles
    angles = []
    for r_theta in lines[:200]:
        rho, theta = r_theta[0]
        # theta near 0 or pi => vertical in Hough polar
        deg = (theta * 180.0 / np.pi)
        # normalize around 0 or 180
        if deg > 90:
            deg = deg - 180
        if abs(deg) < 20:  # only near-vertical
            angles.append(deg)
    if not angles:
        return image
    median_angle = float(np.median(angles))
    if abs(median_angle) < 0.4:  # tiny tilt
        return image
    h, w = cv.shape[:2]
    M = cv2.getRotationMatrix2D((w // 2, h // 2), median_angle, 1.0)
    rotated = cv2.warpAffine(cv, M, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
    return _cv_to_pil(rotated)


def gentle_denoise(image: Image.Image) -> Image.Image:
    cv = _pil_to_cv(image)
    den = cv2.fastNlMeansDenoisingColored(cv, None, h=3, hColor=3, templateWindowSize=7, searchWindowSize=21)
    return _cv_to_pil(den)


def micro_contrast(image: Image.Image, amount: float = 0.15) -> Image.Image:
    cv = _pil_to_cv(image)
    blur = cv2.GaussianBlur(cv, (0, 0), 3)
    # Unsharp mask
    usm = cv2.addWeighted(cv, 1 + amount, blur, -amount, 0)
    return _cv_to_pil(usm)


def apply_white_balance(image: Image.Image, mode: Literal["warm", "neutral", "cool"] = "neutral") -> Image.Image:
    cv = _pil_to_cv(image)
    b, g, r = cv2.split(cv)
    if mode == "warm":
        r = cv2.add(r, 5)
        b = cv2.subtract(b, 5)
    elif mode == "cool":
        r = cv2.subtract(r, 5)
        b = cv2.add(b, 5)
    # neutral: no change
    merged = cv2.merge([b, g, r])
    return _cv_to_pil(merged)


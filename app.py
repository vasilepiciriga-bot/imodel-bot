# app.py — iModel v2.6.0
# Copy-mode v2 (Scene Lock) + Identity Lock ++ Negative + Stable Seed
# Остальное: AutoLang + GPT refine + S3 + Replicate (NanoBanana + RealESRGAN_x4plus)
# Stars + Whitelist/Admin unlimited + Promo + 3 langs + pricing + gallery + refer
# Безопасные отправки; Видео/анимация отключены. Доставка — байты.

import os
import json
import re
import time
import uuid
import base64
import random
import hashlib
import asyncio
from urllib.parse import urlsplit, urlunsplit
from typing import Optional, Dict, List, Set

import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, HTMLResponse

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.exceptions import TelegramRetryAfter
from aiogram.types import (
    Message, Update, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    LabeledPrice, PreCheckoutQuery,
    BufferedInputFile,
    BotCommand, BotCommandScopeDefault,
    InputMediaPhoto,
)
from aiogram.exceptions import TelegramForbiddenError, TelegramNotFound, TelegramBadRequest

import replicate
import boto3
from botocore.config import Config
try:
    import stripe
except Exception:
    stripe = None

# ---------- OpenAI (GPT + Vision) ----------
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

APP_VERSION = "iModel 2.6.0"

# ===================== ENV ==========================
BOT_TOKEN      = os.getenv("BOT_TOKEN", "")
WEBHOOK_BASE   = os.getenv("WEBHOOK_BASE", "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "secret123")
WEBHOOK_URL = f"{WEBHOOK_BASE}/?secret={WEBHOOK_SECRET}"
DISABLE_WEBHOOK = os.getenv("DISABLE_WEBHOOK", "0") == "1"


REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")
os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_MODEL_VISION = os.getenv("OPENAI_MODEL_VISION", OPENAI_MODEL)

# Stripe (optional card payments)
STRIPE_SECRET_KEY     = os.getenv("STRIPE_SECRET_KEY", "")
STRIPE_WEBHOOK_SECRET = os.getenv("STRIPE_WEBHOOK_SECRET", "")
STRIPE_PRICE_10       = os.getenv("STRIPE_PRICE_10", "")
STRIPE_PRICE_30       = os.getenv("STRIPE_PRICE_30", "")
STRIPE_PRICE_100      = os.getenv("STRIPE_PRICE_100", "")
STRIPE_SUCCESS_URL    = os.getenv("STRIPE_SUCCESS_URL", "") or (WEBHOOK_BASE + "/thanks" if WEBHOOK_BASE else "https://example.com/thanks")
STRIPE_CANCEL_URL     = os.getenv("STRIPE_CANCEL_URL", "") or (WEBHOOK_BASE + "/cancel" if WEBHOOK_BASE else "https://example.com/cancel")
STRIPE_ENABLED = bool(STRIPE_SECRET_KEY and (STRIPE_PRICE_10 or STRIPE_PRICE_30 or STRIPE_PRICE_100))
if STRIPE_ENABLED and stripe is not None:
    try:
        stripe.api_key = STRIPE_SECRET_KEY
        print("Stripe enabled")
    except Exception as e:
        print("Stripe init error:", str(e)[:160])
        STRIPE_ENABLED = False
else:
    if STRIPE_SECRET_KEY and stripe is None:
        print("Stripe SDK not installed; Stripe disabled")

# Filter toggles
ALLOW_NSFW   = os.getenv("ALLOW_NSFW", "0") == "1"
ALLOW_CELEBS = os.getenv("ALLOW_CELEBS", "1") == "1"
PREVIEW_FIRST = os.getenv("PREVIEW_FIRST", "1") == "1"
QUEUE_ENABLED = os.getenv("QUEUE_ENABLED", "1") == "1"

# Metrics/Stats
METRICS_SECRET = os.getenv("METRICS_SECRET", "")
ADMIN_PANEL_SECRET = os.getenv("ADMIN_PANEL_SECRET", METRICS_SECRET)
SESSION_GAP_SECONDS = int(os.getenv("SESSION_GAP_SECONDS", "900"))  # 15 min
STATS = {
    "start_ts": time.time(),
    "updates": 0,
    "messages": 0,
    "photos": 0,
    "blocked": 0,
    "gens_ok": 0,
    "gens_fail": 0,
    "gens_copy_ok": 0,
    "gens_copy_fail": 0,
    "mj_prompt_ok": 0,
    "mj_prompt_fail": 0,
    "payments": 0,
    "promo_used": 0,
    "referrals": 0,
    "published_channel": 0,
    "published_group": 0,
    "auto_post": 0,
    "nudges_sent": 0,
    "nudges_errors": 0,
    "nudges_granted": 0,
    "previews": 0,
    "finals": 0,
}
STATS_USERS: Set[int] = set()
STATS_USERS_INFO: Dict[int, Dict[str, object]] = {}

# ===== Persistent stats storage =====
DATA_DIR = os.getenv("DATA_DIR", "data")
STATS_TOTALS_FILE = os.path.join(DATA_DIR, "stats_totals.json")
STATS_DAILY_FILE  = os.path.join(DATA_DIR, "stats_daily.json")
USERS_FILE        = os.path.join(DATA_DIR, "users.json")

STATS_DAILY: Dict[str, Dict[str, int]] = {}

def _date_key(ts: Optional[float] = None) -> str:
    t = time.gmtime(ts or time.time())
    return f"{t.tm_year:04d}-{t.tm_mon:02d}-{t.tm_mday:02d}"

def _ensure_data_dir():
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
    except Exception as e:
        print("[persist] mkdata error:", str(e)[:160])

def _save_json_atomic(path: str, obj: object):
    try:
        _ensure_data_dir()
        tmp = path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(obj, f, ensure_ascii=False)
        os.replace(tmp, path)
    except Exception as e:
        print("[persist] save error:", path, str(e)[:160])

def stats_save_totals():
    try:
        to_save = dict(STATS)
        # Don't persist huge sets in totals
        to_save.pop("start_ts", None)
        _save_json_atomic(STATS_TOTALS_FILE, to_save)
        try:
            _s3_put_text(STATE_PREFIX + "stats_totals.json", json.dumps(to_save, ensure_ascii=False))
        except Exception:
            pass
    except Exception as e:
        print("[stats] save totals error:", str(e)[:160])

def stats_save_daily():
    _save_json_atomic(STATS_DAILY_FILE, STATS_DAILY)
    try:
        _s3_put_text(STATE_PREFIX + "stats_daily.json", json.dumps(STATS_DAILY, ensure_ascii=False))
    except Exception:
        pass

def users_save():
    try:
        _save_json_atomic(USERS_FILE, STATS_USERS_INFO)
        try:
            _s3_put_text(STATE_PREFIX + "users.json", json.dumps(STATS_USERS_INFO, ensure_ascii=False))
        except Exception:
            pass
    except Exception as e:
        print("[users] save error:", str(e)[:160])

def stats_load():
    global STATS_DAILY
    try:
        loaded = None
        txt = _s3_get_text(STATE_PREFIX + "stats_totals.json")
        if txt:
            loaded = json.loads(txt)
        elif os.path.exists(STATS_TOTALS_FILE):
            with open(STATS_TOTALS_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
        if loaded:
            for k, v in loaded.items():
                try:
                    if isinstance(v, (int, float)):
                        STATS[k] = v
                except Exception:
                    pass
    except Exception as e:
        print("[stats] load totals error:", str(e)[:160])
    try:
        txt = _s3_get_text(STATE_PREFIX + "stats_daily.json")
        if txt:
            STATS_DAILY = json.loads(txt) or {}
        elif os.path.exists(STATS_DAILY_FILE):
            with open(STATS_DAILY_FILE, "r", encoding="utf-8") as f:
                STATS_DAILY = json.load(f) or {}
        else:
            STATS_DAILY = {}
    except Exception as e:
        print("[stats] load daily error:", str(e)[:160])
        STATS_DAILY = {}
    try:
        data = None
        txt = _s3_get_text(STATE_PREFIX + "users.json")
        if txt:
            data = json.loads(txt) or {}
        elif os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
        if data:
            for uid_str, info in data.items():
                try:
                    STATS_USERS_INFO[int(uid_str)] = info
                except Exception:
                    continue
    except Exception as e:
        print("[users] load error:", str(e)[:160])

def stats_incr(key: str, n: int = 1):
    try:
        STATS[key] = int(STATS.get(key, 0)) + n
        stats_save_totals()
        day = _date_key()
        d = STATS_DAILY.setdefault(day, {})
        d[key] = int(d.get(key, 0)) + n
        stats_save_daily()
    except Exception as e:
        print("[stats] incr error:", key, str(e)[:160])

def _touch_user(uid: int, username: Optional[str] = None):
    now = time.time()
    info = STATS_USERS_INFO.get(uid)
    if info is None:
        info = {
            "first_seen": now,
            "last_seen": now,
            "sessions": 1,
            "session_start": now,
            "active_seconds": 0.0,
            "username": (username or "")[:64],
            "messages": 0,
            "photos": 0,
            "gens_ok": 0,
            "gens_fail": 0,
            "gens_copy_ok": 0,
            "gens_copy_fail": 0,
            "published": 0,
            "payments": 0,
        }
        STATS_USERS_INFO[uid] = info
    else:
        last_seen = float(info.get("last_seen", now))
        if now - last_seen > SESSION_GAP_SECONDS:
            info["sessions"] = int(info.get("sessions", 0)) + 1
            info["session_start"] = now
        else:
            info["active_seconds"] = float(info.get("active_seconds", 0.0)) + max(0.0, now - last_seen)
        info["last_seen"] = now
        if username and not info.get("username"):
            info["username"] = username[:64]
    # persist user info after updates
    try:
        users_save()
    except Exception:
        pass

def _uadd(uid: int, key: str, n: int = 1):
    info = STATS_USERS_INFO.get(uid)
    if not info:
        _touch_user(uid)
        info = STATS_USERS_INFO.get(uid)
    try:
        info[key] = int(info.get(key, 0)) + n
    except Exception:
        info[key] = n
    try:
        users_save()
    except Exception:
        pass

# S3 (Backblaze B2 S3-compatible)
S3_ENDPOINT = os.getenv("S3_ENDPOINT", "https://s3.eu-central-003.backblazeb2.com")
S3_REGION   = os.getenv("S3_REGION", "eu-central-003")
S3_KEY_ID   = os.getenv("S3_ACCESS_KEY_ID", "")
S3_SECRET   = os.getenv("S3_SECRET_ACCESS_KEY", "")
S3_BUCKET   = os.getenv("S3_BUCKET", "")

_s3 = boto3.client(
    "s3",
    endpoint_url=S3_ENDPOINT,
    aws_access_key_id=S3_KEY_ID,
    aws_secret_access_key=S3_SECRET,
    region_name=S3_REGION,
    config=Config(s3={"addressing_style": "virtual"})
)

# Optional: persist state to S3 to survive ephemeral filesystems
STATE_PREFIX = os.getenv("STATE_PREFIX", "state/")
USE_S3_STATE = bool(S3_BUCKET and S3_KEY_ID and S3_SECRET)

def _s3_put_text(key: str, text: str):
    if not USE_S3_STATE:
        return
    try:
        _s3.put_object(Bucket=S3_BUCKET, Key=key, Body=text.encode("utf-8"), ContentType="application/json; charset=utf-8")
    except Exception as e:
        print("[s3] put error:", key, str(e)[:160])

def _s3_get_text(key: str) -> Optional[str]:
    if not USE_S3_STATE:
        return None
    try:
        obj = _s3.get_object(Bucket=S3_BUCKET, Key=key)
        return obj["Body"].read().decode("utf-8")
    except Exception as e:
        # Not found or access issues → ignore
        return None

# Replicate models
NANOBANANA_MODEL = os.getenv("NANOBANANA_MODEL", "google/nano-banana")
ESRGAN_MODEL     = os.getenv("ESRGAN_MODEL", "nightmareai/real-esrgan")  # x4plus via params
DISABLE_ESRGAN   = os.getenv("DISABLE_ESRGAN", "1") == "1"
ESRGAN_DISABLED  = False  # auto-disable on first 404

# Language / quotas
LANG_DEFAULT = os.getenv("LANG_DEFAULT", "en")
FREE_QUOTA   = int(os.getenv("FREE_QUOTA", "3"))

# Channel & autopost
GALLERY_CHANNEL_ID = os.getenv("GALLERY_CHANNEL_ID", "")
try:
    if GALLERY_CHANNEL_ID:
        GALLERY_CHANNEL_ID = int(GALLERY_CHANNEL_ID)
except Exception:
    GALLERY_CHANNEL_ID = None
AUTO_POST = os.getenv("AUTO_POST", "0") == "1"  # if 1: авто-пост в канал «до/после»

# Optional group for manual publishing
PUBLISH_GROUP_ID = os.getenv("PUBLISH_GROUP_ID", "")
try:
    if PUBLISH_GROUP_ID:
        PUBLISH_GROUP_ID = int(PUBLISH_GROUP_ID)
except Exception:
    PUBLISH_GROUP_ID = None

# ===================== Admins =======================
def _parse_admins(val: str) -> Set[int]:
    out: Set[int] = set()
    for x in (val or "").replace(";", ",").split(","):
        x = x.strip()
        if not x:
            continue
        try:
            out.add(int(x))
        except Exception:
            pass
    return out

ADMIN_IDS: Set[int] = _parse_admins(os.getenv("ADMIN_IDS", ""))
ADMIN_USERNAMES_RAW = os.getenv("ADMIN_USERNAMES", "@piciriga,@MarkBeth_beauty,@tamara_piciriga")
ADMIN_USERNAMES = {
    u.lstrip("@").lower()
    for u in re.split(r"[,\s]+", ADMIN_USERNAMES_RAW)
    if u.strip()
}

def is_admin(uid: int, username: Optional[str] = None) -> bool:
    if uid in ADMIN_IDS:
        return True
    if username:
        return username.lower() in ADMIN_USERNAMES
    return False

def is_free_user(uid: int, username: Optional[str] = None) -> bool:
    """Whitelist или админ (безлимит)."""
    # Active time subscription
    try:
        if SUBSCR_EXPIRY.get(uid, 0.0) > time.time():
            return True
    except Exception:
        pass
    if uid in FREE_USERS:
        return True
    return is_admin(uid, username)

# ===================== State ========================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI(title="iModel Bot")
api = app  # alias

USER_REFS: Dict[int, List[bytes]]  = {}   # 1–4 селфи (последние)
USER_LAST_OUTPUT: Dict[int, bytes] = {}   # последний результат
USER_LAST_PROMPT: Dict[int, str]   = {}   # последний prompt
USER_LANG: Dict[int, str]          = {}   # язык
USER_CREDITS: Dict[int, int]       = {}   # баланс
USER_SEEN_TEXT: Set[int]           = set()
USER_ONBOARDED: Set[int]           = set()

# Persistent storage for credits
DATA_DIR = os.getenv("DATA_DIR", "data")
CREDITS_FILE = os.getenv("CREDITS_FILE", os.path.join(DATA_DIR, "credits.json"))
SUBSCR_FILE = os.getenv("SUBSCR_FILE", os.path.join(DATA_DIR, "subscriptions.json"))

def _credits_save():
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = CREDITS_FILE + ".tmp"
        payload = json.dumps({str(k): int(v) for k, v in USER_CREDITS.items()}, ensure_ascii=False)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp, CREDITS_FILE)
        _s3_put_text(STATE_PREFIX + "credits.json", payload)
    except Exception as e:
        print("[credits] save error:", str(e)[:160])

def _credits_load():
    try:
        # Prefer S3 state if available
        txt = _s3_get_text(STATE_PREFIX + "credits.json")
        if txt:
            data = json.loads(txt)
            for k, v in (data or {}).items():
                try:
                    USER_CREDITS[int(k)] = int(v)
                except Exception:
                    continue
            return
        if os.path.exists(CREDITS_FILE):
            with open(CREDITS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in (data or {}).items():
                try:
                    USER_CREDITS[int(k)] = int(v)
                except Exception:
                    continue
    except Exception as e:
        print("[credits] load error:", str(e)[:160])

def ensure_user_credit(uid: int):
    if uid not in USER_CREDITS:
        USER_CREDITS[uid] = FREE_QUOTA
        _credits_save()

_credits_load()
# Subscriptions (time-based)
SUBSCR_EXPIRY: Dict[int, float] = {}

# Referral persistence
REFS_FILE = os.path.join(DATA_DIR, "refstats.json")

def _refs_save():
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = REFS_FILE + ".tmp"
        payload = json.dumps({str(k): {"count": int(v.get("count",0)), "earned": int(v.get("earned",0))} for k, v in REF_STATS.items()}, ensure_ascii=False)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp, REFS_FILE)
        _s3_put_text(STATE_PREFIX + "refstats.json", payload)
    except Exception as e:
        print("[refs] save error:", str(e)[:160])

def _refs_load():
    try:
        txt = _s3_get_text(STATE_PREFIX + "refstats.json")
        data = None
        if txt:
            data = json.loads(txt)
        elif os.path.exists(REFS_FILE):
            with open(REFS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        for k, v in (data or {}).items():
            try:
                REF_STATS[int(k)] = {"count": int(v.get("count",0)), "earned": int(v.get("earned",0))}
            except Exception:
                continue
    except Exception as e:
        print("[refs] load error:", str(e)[:160])

def _subs_save():
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = SUBSCR_FILE + ".tmp"
        payload = json.dumps({str(k): float(v) for k, v in SUBSCR_EXPIRY.items()}, ensure_ascii=False)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp, SUBSCR_FILE)
        _s3_put_text(STATE_PREFIX + "subscriptions.json", payload)
    except Exception as e:
        print("[subs] save error:", str(e)[:160])

def _subs_load():
    try:
        txt = _s3_get_text(STATE_PREFIX + "subscriptions.json")
        data = None
        if txt:
            data = json.loads(txt)
        elif os.path.exists(SUBSCR_FILE):
            with open(SUBSCR_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
        for k, v in (data or {}).items():
            try:
                SUBSCR_EXPIRY[int(k)] = float(v)
            except Exception:
                continue
    except Exception as e:
        print("[subs] load error:", str(e)[:160])

_subs_load()
_refs_load()

# публикация до/после
LAST_REF: Dict[int, bytes]   = {}
LAST_PHOTO: Dict[int, bytes] = {}

# Copy Mode
USER_COPY_MODE: Set[int]         = set()
USER_COPY_STYLE: Dict[int, bytes]= {}
USER_COPY_PROMPT: Dict[int, str] = {}

# Retouch Mode
 

# Whitelist
FREE_USERS: set[int] = set()

# Промокоды
PROMO_CODES: Dict[str, Dict[str, int]] = {
    "JOIN2025": {"add": 10, "uses": 200},
    "IMODEL5":  {"add": 5,  "uses": 500},
}

# История /gallery
USER_HISTORY: Dict[int, List[bytes]] = {}
GALLERY_LIMIT = 5

# Рефералка
REF_BONUS_NEW  = int(os.getenv("REF_BONUS_NEW", "1"))
REF_BONUS_REF  = int(os.getenv("REF_BONUS_REF", "1"))
REF_PREMIUM_THRESHOLD = int(os.getenv("REF_PREMIUM_THRESHOLD", "15"))  # +1 day Premium per N invited
REF_MAP: Dict[int, int] = {}
REF_STATS: Dict[int, Dict[str, int]] = {}

BOT_USERNAME_GLOBAL = None

# ===================== PRESETS =======================
# 24 styled presets: short labels and hidden prompts
from dataclasses import dataclass

@dataclass
class Preset:
    key: str
    label_ru: str
    label_en: str
    label_ro: str
    label_de: str
    prompt: str

PRESETS: List[Preset] = [
    Preset("studio_soft", "📸 Студия", "📸 Studio", "📸 Studiou", "📸 Studio", "studio portrait photo of a person, soft beauty light, dark seamless backdrop, 85mm lens, f/1.8, crisp details, natural skin, editorial look, award‑winning photograph"),
    Preset("cinematic", "🎬 Кинематик", "🎬 Cinematic", "🎬 Cinematic", "🎬 Cinematisch", "cinematic portrait, teal & orange color grade, rim light, shallow depth, dramatic mood, 50mm anamorphic look, high dynamic range"),
    Preset("golden_hour", "🌅 Голден-ауэр", "🌅 Golden Hour", "🌅 Ora de aur", "🌅 Goldene Stunde", "outdoor portrait at golden hour, warm backlight, sun flare, soft haze, dreamy bokeh, natural colors, filmic rendering"),
    Preset("editorial_highkey", "🧴 Эдиториал", "🧴 Editorial", "🧴 Editorial", "🧴 Editorial High‑Key", "high‑key studio fashion portrait, clean white backdrop, softboxes, glossy highlights, magazine editorial style, minimal shadows"),
    Preset("bw_film", "⚫️ Ч/Б Плёнка", "⚫️ B/W Film", "⚫️ Film B/N", "⚫️ S/W Film", "black and white portrait, rich contrast, soft film grain, timeless classic look, ilford hp5 vibe, elegant"),
    Preset("kodak_portra", "🎞 Portra", "🎞 Portra", "🎞 Portra", "🎞 Portra", "portrait in kodak portra 400 film style, warm skin tones, gentle contrast, natural colors, subtle grain"),
    Preset("beauty_dish", "💄 Бьюти", "💄 Beauty", "💄 Beauty", "💄 Beauty", "beauty portrait, beauty dish, soft ring catchlights, flawless yet natural skin, glossy lips, editorial makeup, close‑up"),
    Preset("headshot", "👔 Хэдшот", "👔 Headshot", "👔 Portret CV", "👔 Headshot", "corporate headshot, neutral gray background, flattering key light, 85mm, professional linkedin style, crisp focus"),
    Preset("neon_night", "🌃 Неон", "🌃 Neon Night", "🌃 Noapte Neon", "🌃 Neon Nacht", "city night portrait, neon lights, cyberpunk colors, wet streets reflections, cinematic bokeh, moody atmosphere"),
    Preset("cafe", "☕️ Кафе", "☕️ Cafe", "☕️ Cafenea", "☕️ Café", "cozy cafe portrait, warm tungsten lights, string lights bokeh, candid mood, shallow depth, lifestyle"),
    Preset("forest", "🌲 Лес", "🌲 Forest", "🌲 Pădure", "🌲 Wald", "forest portrait, diffused light under trees, green tones, soft atmosphere, misty background"),
    Preset("beach", "🏖 Пляж", "🏖 Beach", "🏖 Plajă", "🏖 Strand", "sunrise beach portrait, pastel colors, gentle breeze, fresh tones, soft backlight, cinematic"),
    Preset("architecture", "🏛 Архитектура", "🏛 Architecture", "🏛 Arhitectură", "🏛 Architektur", "minimalist architecture backdrop, concrete and glass, symmetry, modern editorial street portrait"),
    Preset("luxury_interior", "🏨 Интерьер", "🏨 Interior", "🏨 Interior", "🏨 Interieur", "luxury hotel lobby portrait, marble, warm ambient lights, elegant depth, upscale vibe"),
    Preset("rain_window", "🌧 Дождь", "🌧 Rain", "🌧 Ploaie", "🌧 Regen", "portrait through rainy window, droplets bokeh, moody reflections, intimate cinematic feel"),
    Preset("snow", "❄️ Снег", "❄️ Snow", "❄️ Zăpadă", "❄️ Schnee", "snow portrait, soft falling snowflakes, cool tones, cozy winter look, scarf, gentle light"),
    Preset("rembrandt", "🕯 Рембрандт", "🕯 Rembrandt", "🕯 Rembrandt", "🕯 Rembrandt", "classic Rembrandt lighting portrait, chiaroscuro, painterly, timeless, museum quality"),
    Preset("soft_glam", "✨ Глам", "✨ Soft Glam", "✨ Soft Glam", "✨ Soft Glam", "soft glam portrait, delicate highlights, pearly skin, subtle retouch, editorial beauty, cinematic glow"),
    Preset("vintage70", "📼 70‑е", "📼 70s", "📼 Ani 70", "📼 70er", "vintage 1970s film look, muted colors, halation glow, analog feel, flare"),
    Preset("mono_hicon", "⬛️ Моно Контраст", "⬛️ Mono High‑Contrast", "⬛️ Mono Contrast", "⬛️ Mono Kontrast", "high‑contrast monochrome portrait, deep blacks, punchy highlights, gallery style"),
    Preset("park", "🌿 Парк", "🌿 Park", "🌿 Parc", "🌿 Park", "outdoor park portrait, gentle green bokeh, 85mm, soft light, lifestyle"),
    Preset("fitness", "💪 Фитнес", "💪 Fitness", "💪 Fitness", "💪 Fitness", "dramatic gym portrait, hard light, textured muscles, moody shadows, grit"),
    Preset("garage", "🚗 Гараж", "🚗 Garage", "🚗 Garaj", "🚗 Garage", "portrait in garage, glossy reflections, metallic textures, cinematic teal accents"),
    Preset("bookstore", "📚 Книги", "📚 Bookstore", "📚 Librărie", "📚 Buchladen", "bookstore portrait, warm ambient tungsten, shelves bokeh, intellectual cozy vibe"),
]

USER_PRESET_PENDING: Dict[int, int] = {}

def kb_presets_grid(chat_id: int) -> InlineKeyboardMarkup:
    lang = USER_LANG.get(chat_id, LANG_DEFAULT)
    def label(p: Preset) -> str:
        if lang.startswith("ru"):
            return p.label_ru
        if lang.startswith("ro"):
            return p.label_ro
        if lang.startswith("de"):
            return p.label_de
        return p.label_en
    rows: List[List[InlineKeyboardButton]] = []
    for i, p in enumerate(PRESETS):
        if i % 4 == 0:
            rows.append([])
        rows[-1].append(InlineKeyboardButton(text=label(p), callback_data=f"preset_{i}"))
    # Back button
    back_txt = {
        "ru": "⬅️ Назад",
        "en": "⬅️ Back",
        "ro": "⬅️ Înapoi",
        "de": "⬅️ Zurück",
    }.get(lang, "⬅️ Back")
    rows.append([InlineKeyboardButton(text=back_txt, callback_data="back_main")])
    return InlineKeyboardMarkup(inline_keyboard=rows)

# ===================== I18N =========================
T = {
    "ru": {
        "menu_lang": "🌐 Язык",
        "onboard_welcome": "Добро пожаловать в iModel. Нажмите «Старт», чтобы начать.",
        "onboard_btn": "🚀 Старт",
        "start": "✨ Добро пожаловать в iModel — AI фотостудию.\nВаши фотографии могут выглядеть так, словно их сделал профессиональный фотограф.\n\n🔹 Загрузите 1–4 селфи — хороший свет поможет.\n🔹 Опишите сцену или атмосферу, которую хотите.\n🔹 Или используйте функцию «Скопировать»: загрузите понравившееся фото из интернета, добавьте своё селфи — и получите стильный результат в том же духе.\n\n📌 Меню:\n⭐ Купить — пополните баланс и откройте новые возможности.\n💰 Баланс — всегда знайте, сколько генераций у вас доступно.\n📸 Пресеты — готовые стили фотосессий.\n📋 Скопировать — повторите понравившийся стиль с вашим фото.\n🆘 Помощь — ответы на все вопросы.\n🌐 Язык — переключение интерфейса.\n\n🎁 Бесплатные генерации — пригласите друзей: /refer\n\n📷 Ваши фото — ваша история. Мы сделаем её безупречной.",
        "help": "🆘 Помощь\n\nКак получить лучший результат:\n• Пришлите 1–4 селфи при ровном свете, без сильных фильтров\n• В описании укажите место, свет, стиль, кадрирование, настроение\n• Быстрый старт: откройте Пресеты и выберите стиль\n• Скопировать сцену: режим ‘Скопировать’ — сначала образец, затем селфи\n\nОплата и баланс:\n• Покупка — раздел ‘Купить’ (Telegram Stars)\n• Списание — только при успешной генерации (кроме whitelist/админ)\n• Промокоды — команда /promo КОД\n\nРеферальная программа:\n• Пригласи друга — ты +{ref_ref}, новый пользователь +{ref_new}\n• Твоя ссылка: /refer\n\nПравила и приватность:\n• Запрещены NSFW/селебы\n• Фото хранятся временно; /clear — очистка, /forget — полное удаление\n\nНужна помощь? Напишите @piciriga — ответим быстро.",
        "need_photo": "Сначала пришли фото лица.",
        "photo_ok": "Фото получено ✅ Теперь опишите сцену или используйте /presets.",
        "gen": "Генерирую… ⏳",
        "fail": "Не удалось сгенерировать. Попробуйте изменить описание или фото.",
        "ready": "Готово ✅",
        "credits_none": "Нет кредитов. Используй /buy или /promo. Также можно пригласить друга: /refer",
        "limit_80": "Ты уже использовал {pct}% своего лимита.",
        "unlock": "🔒 Разблокируй безлимит за 2 € / день",
        "hint_refer_zero": "👥 У вас 0 генераций. Пригласите друга — +{ref_ref} вам и +{ref_new} ему: /refer",
        "btn_invite": "👥 Пригласить друга",
        "choose_lang": "🌐 Выберите язык интерфейса:",
        "lang_ru": "Язык установлен: Русский",
        "lang_en": "Язык установлен: Английский",
        "lang_ro": "Язык установлен: Румынский",
        "lang_de": "Язык установлен: Немецкий",
        "presets": "Идеи сцен:\n• Студия: портрет, мягкий свет, тёмный фон\n• Улица: закат, боке, 85мм\n• Интерьер: кафе, тёплый свет, винтаж\n• Природа: лес, рассеянный свет, «плёнка»",
        "blocked": "⛔ Запрос запрещён.",
        "btn_balance": "Баланс",
        "btn_buy": "Купить",
        "btn_more": "Ещё вариант",
        "btn_publish": "Опубликовать",
        "btn_publish_group": "В группу",
        "menu_presets": "📸 Пресеты",
        "menu_help": "🆘 Помощь",
        "menu_refer": "🎁 Бесплатные генерации",
        "menu_invite": "👥 Пригласить друга",
        "btn_support": "📨 Написать поддержку",
        "btn_back": "⬅️ Назад",
        "btn_refer": "🎁 Бесплатные генерации",
        "hint_refer_pay": "🎁 Бонусы: пригласи друга — +{ref_ref} тебе и +{ref_new} другу",
        "menu_pricing": "💎 Тарифы",
        "buy_title": "💳 Покупка генераций (Telegram Stars)\nВыберите удобный пакет:",
        "buy_btn_10": "10 генераций — 200★",
        "buy_btn_30": "30 генераций — 500★",
        "buy_btn_100": "100 генераций — 1200★",
        "bought": "Спасибо! +{add}. Всего: {all}.",
        "promo_usage": "Использование: /promo КОД",
        "promo_ok": "Промокод: +{add}. Всего: {all}.",
        "promo_bad": "Промокод не найден.",
        "version": "ℹ️ Версия: {ver}",
        "balance": "Ваш баланс: {n} генераций{free}",
        "balance_free": " (whitelist/админ — списание не производится)",
        "cleared": "Память очищена.",
        "tos": "Условия: фото используются только для генерации; запрещены NSFW/селебы; результат хранится до 72ч.",
        "privacy": "Приватность: не передаём фото; /clear удаляет временные данные; /forget — полное удаление.",
        "admin_only": "Команда только для админов.",
        "granted": "Выдано {n} генераций пользователю {uid}. Баланс: {bal}.",
        "free_added": "Пользователь {uid} добавлен в whitelist.",
        "gallery_empty": "Галерея пуста.",
        "ref_link_fail": "Не удалось определить username бота.",
        "pricing": "💎 Тарифы iModel\n\n• 10 генераций — 200★  (20★/шт)\n• 30 генераций — 500★  (≈16.7★/шт)\n• 100 генераций — 1200★ (12★/шт)\n\nОплата звёздами Telegram. Чем больше пакет — тем выгоднее.",
        "copy_intro": "📋 Режим «Скопировать фото»\nШаг 1: пришлите фото‑образец (сцена)\nШаг 2: пришлите своё селфи\nРезультат: та же сцена, заменено только лицо.",
        "copy_style_ok": "Образец принят ✅ Теперь пришли своё селфи.",
        "copy_need_style": "Сначала пришли фото-образец (сцена).",
        "copy_done": "Готово ✅",
        "copy_exit": "Режим «Скопировать фото» выключен.",
        "menu_copy": "📋 Скопировать",
    },
    "en": {
        "menu_lang": "🌐 Language",
        "onboard_welcome": "Welcome to iModel. Tap Start to begin.",
        "onboard_btn": "🚀 Start",
        "start": "👋 Welcome to iModel — professional photo generation.\n\nHow it works:\n1) Send 1–4 selfies (good lighting helps)\n2) Describe the scene or use Copy Mode (/copy)\n3) Get the result.\n\nQuick commands: /help · /presets · /buy · /pricing · /promo · /balance · /gallery · /refer · /lang · /copy",
        "help": "🆘 Help\n\nBest results:\n• Send 1–4 selfies in even lighting, minimal filters\n• In your prompt describe location, light, style, framing, mood\n• Quick start: open Presets and pick a style\n• Copy a scene: use ‘Copy’ — first the reference, then your selfie\n\nPayments & balance:\n• Buy in ‘Buy’ (Telegram Stars)\n• Credits are deducted only on successful generation (except whitelist/admin)\n• Promo codes — /promo CODE\n\nReferral program:\n• Invite a friend — you +{ref_ref}, they +{ref_new}\n• Your link: /refer\n\nRules & privacy:\n• NSFW/celebrities are forbidden\n• Photos are stored temporarily; /clear to purge temp, /forget for full delete\n\nNeed help? Message @piciriga — we’ll reply quickly.",
        "need_photo": "Please send a face photo first.",
        "photo_ok": "Photo received ✅ Now describe the scene or use /presets.",
        "gen": "Working… ⏳",
        "fail": "Generation failed. Try adjusting your description or selfie.",
        "ready": "Done ✅",
        "credits_none": "No credits. Use /buy or /promo. You can also invite a friend: /refer",
        "limit_80": "You have used {pct}% of your limit.",
        "unlock": "🔒 Unlock unlimited for €2/day",
        "hint_refer_zero": "👥 You have 0 credits. Invite a friend — +{ref_ref} you and +{ref_new} them: /refer",
        "btn_invite": "👥 Invite a friend",
        "choose_lang": "🌐 Choose your interface language:",
        "lang_ru": "Language set: Russian",
        "lang_en": "Language set: English",
        "lang_ro": "Language set: Romanian",
        "lang_de": "Language set: German",
        "presets": "Scene ideas:\n• Studio: portrait, soft light, dark backdrop\n• Outdoor: sunset, bokeh, 85mm\n• Interior: cafe, warm tones, vintage\n• Nature: forest, diffused light, film look",
        "blocked": "⛔ Request blocked.",
        "btn_balance": "Balance",
        "btn_buy": "Buy",
        "btn_more": "More",
        "btn_publish": "Publish",
        "btn_publish_group": "To group",
        "menu_presets": "🎛 Presets",
        "menu_help": "🆘 Help",
        "menu_refer": "🎁 Free credits",
        "menu_invite": "👥 Invite a friend",
        "btn_support": "📨 Contact support",
        "btn_back": "⬅️ Back",
        "btn_refer": "🎁 Free credits",
        "hint_refer_pay": "🎁 Tip: invite a friend — +{ref_ref} you · +{ref_new} them",
        "menu_pricing": "💎 Pricing",
        "buy_title": "💳 Buy generations (Telegram Stars)\nChoose a value pack:",
        "buy_btn_10": "10 gens — 200★",
        "buy_btn_30": "30 gens — 500★",
        "buy_btn_100": "100 gens — 1200★",
        "bought": "Thanks! +{add}. Total: {all}.",
        "promo_usage": "Usage: /promo CODE",
        "promo_ok": "Promo applied: +{add}. Total: {all}.",
        "promo_bad": "Promo not found.",
        "version": "ℹ️ Version: {ver}",
        "balance": "Your balance: {n} generations{free}",
        "balance_free": " (whitelisted/admin — no deductions)",
        "cleared": "Memory cleared.",
        "tos": "Terms: photos are used only for generation; NSFW/celebrities forbidden; result may be kept up to 72h.",
        "privacy": "Privacy: we don't share photos; /clear removes temporary data; /forget purges all.",
        "admin_only": "Admins only.",
        "granted": "Granted {n} gens to {uid}. Balance: {bal}.",
        "free_added": "User {uid} added to whitelist.",
        "gallery_empty": "Gallery is empty.",
        "ref_link_fail": "Can't detect bot username.",
        "pricing": "💎 iModel Pricing\n\n• 10 gens — 200★  (20★/gen)\n• 30 gens — 500★  (≈16.7★/gen)\n• 100 gens — 1200★ (12★/gen)\n\nPay with Telegram Stars. Bigger packs are more cost‑effective.",
        "copy_intro": "📋 Copy Mode\nStep 1: send a style reference (scene)\nStep 2: send your selfie\nResult: same scene, face replaced only.",
        "copy_style_ok": "Style reference received ✅ Now send your selfie.",
        "copy_need_style": "Please send the style reference first.",
        "copy_done": "Done ✅",
        "copy_exit": "Copy Mode OFF.",
        "menu_copy": "📋 Copy",
    },
    "ro": {
        "menu_lang": "🌐 Limba",
        "onboard_welcome": "Bine ai venit la iModel. Apasă Start pentru a începe.",
        "onboard_btn": "🚀 Start",
        "start": "👋 Bine ai venit la iModel — generare foto profesională.\n\nCum funcționează:\n1) Trimite 1–4 selfie‑uri (lumina bună ajută)\n2) Descrie scena sau folosește „Copiază” (/copy)\n3) Primești rezultatul.\n\nComenzi rapide: /help · /presets · /buy · /pricing · /promo · /balance · /gallery · /refer · /lang · /copy",
        "help": "🆘 Ajutor\n\nRezultate mai bune:\n• Trimite 1–4 selfie‑uri cu lumină uniformă, fără filtre puternice\n• În descriere: locație, lumină, stil, încadrare, mood\n• Start rapid: deschide Preseturi și alege un stil\n• Copiere scenă: ‘Copiază’ — mai întâi referința, apoi selfie‑ul\n\nPlăți & sold:\n• Cumpără în ‘Cumpără’ (Stele Telegram)\n• Creditul se scade doar la generare reușită (exceptând whitelist/admin)\n• Cod promo — /promo COD\n\nProgram de recomandări:\n• Invită un prieten — tu +{ref_ref}, el/ea +{ref_new}\n• Linkul tău: /refer\n\nReguli & confidențialitate:\n• NSFW/celebr. interzise\n• Pozele se păstrează temporar; /clear curăță, /forget ștergere totală\n\nAi nevoie de ajutor? Scrie la @piciriga — răspundem rapid.",
        "need_photo": "Trimite o poză cu fața mai întâi.",
        "photo_ok": "Poză primită ✅ Acum descrie scena sau folosește /presets.",
        "gen": "Generez… ⏳",
        "fail": "Nu am reușit. Încearcă altă descriere sau alt selfie.",
        "ready": "Gata ✅",
        "credits_none": "Nu mai ai credite. /buy sau /promo. Poți invita un prieten: /refer",
        "limit_80": "Ai folosit {pct}% din limită.",
        "unlock": "🔒 Deblochează nelimitat cu 2 €/zi",
        "hint_refer_zero": "👥 Ai 0 credite. Invită un prieten — +{ref_ref} ție și +{ref_new} lui/ei: /refer",
        "btn_invite": "👥 Invită un prieten",
        "choose_lang": "🌐 Alege limba interfeței:",
        "lang_ru": "Limba setată: Rusă",
        "lang_en": "Limba setată: Engleză",
        "lang_ro": "Limba setată: Română",
        "lang_de": "Limba setată: Germană",
        "presets": "Idei de scenă:\n• Studio: portret, lumină moale, fundal închis\n• Exterior: apus, bokeh, 85mm\n• Interior: cafenea, tonuri calde, vintage\n• Natură: pădure, lumină difuză, aspect film",
        "blocked": "⛔ Cerere blocată.",
        "btn_balance": "Sold",
        "btn_buy": "Cumpără",
        "btn_more": "Încă una",
        "btn_publish": "Publică",
        "btn_publish_group": "În grup",
        "menu_presets": "🎛 Preseturi",
        "menu_help": "🆘 Ajutor",
        "menu_refer": "🎁 Generații gratuite",
        "menu_invite": "👥 Invită un prieten",
        "btn_support": "📨 Contact suport",
        "btn_back": "⬅️ Înapoi",
        "btn_refer": "🎁 Generații gratuite",
        "hint_refer_pay": "🎁 Bonus: invită un prieten — +{ref_ref} ție · +{ref_new} lui/ei",
        "menu_pricing": "💎 Prețuri",
        "buy_title": "💳 Cumpără generații (Stele Telegram)\nAlege pachetul avantajos:",
        "buy_btn_10": "10 gen — 200★",
        "buy_btn_30": "30 gen — 500★",
        "buy_btn_100": "100 gen — 1200★",
        "bought": "Mulțumesc! +{add}. Total: {all}.",
        "promo_usage": "Folosește: /promo COD",
        "promo_ok": "Promo: +{add}. Total: {all}.",
        "promo_bad": "Promo invalid.",
        "version": "ℹ️ Versiune: {ver}",
        "balance": "Sold: {n} generații{free}",
        "balance_free": " (whitelist/admin — fără scădere)",
        "cleared": "Memoria a fost ștearsă.",
        "tos": "Termeni: pozele sunt folosite doar pentru generare; interzis NSFW/celebr; rezultatul poate fi păstrat până la 72h.",
        "privacy": "Confidențialitate: nu partajăm pozele; /clear șterge temporarele; /forget ștergere totală.",
        "admin_only": "Doar admin.",
        "granted": "Atribuit {n} gen utilizatorului {uid}. Sold: {bal}.",
        "free_added": "Utilizatorul {uid} în whitelist.",
        "gallery_empty": "Galeria este goală.",
        "ref_link_fail": "Nu pot obține username-ul botului.",
        "pricing": "💎 Prețuri iModel\n\n• 10 gen — 200★  (20★/gen)\n• 30 gen — 500★  (≈16.7★/gen)\n• 100 gen — 1200★ (12★/gen)\n\nPlată cu Stele Telegram. Pachetele mari sunt avantajoase.",
        "copy_intro": "📋 Modul „Copiază”\nPasul 1: trimite poza model (scenă)\nPasul 2: trimite selfie‑ul tău\nRezultat: aceeași scenă, doar fața schimbată.",
        "copy_style_ok": "Poză model primită ✅ Acum trimite selfie-ul.",
        "copy_need_style": "Trimite mai întâi poza model.",
        "copy_done": "Gata ✅",
        "copy_exit": "Modul „Copiază” oprit.",
        "menu_copy": "📋 Copiază",
    }
    ,
    "de": {
        "menu_lang": "🌐 Sprache",
        "onboard_welcome": "Willkommen bei iModel. Tippe auf Start, um zu beginnen.",
        "onboard_btn": "🚀 Start",
        "start": "👋 Willkommen bei iModel — professionelle Fotogenerierung.\n\nSo geht’s:\n1) Sende 1–4 Selfies (gutes Licht hilft)\n2) Beschreibe die Szene oder nutze den Kopier‑Modus (/copy)\n3) Erhalte das Ergebnis.\n\nSchnellbefehle: /help · /presets · /buy · /pricing · /promo · /balance · /gallery · /refer · /lang · /copy",
        "help": "🆘 Hilfe\n\nBeste Ergebnisse:\n• 1–4 Selfies bei gleichmäßiger Beleuchtung, ohne starke Filter\n• Beschreibe Ort, Licht, Stil, Bildausschnitt, Stimmung\n• Schnellstart: Presets öffnen und Stil wählen\n• Szene kopieren: ‘Kopieren’ — zuerst Referenz, dann Selfie\n\nZahlung & Guthaben:\n• Kaufen in ‘Kaufen’ (Telegram Stars)\n• Abzug nur bei erfolgreicher Generierung (außer Whitelist/Admin)\n• Promo‑Code — /promo CODE\n\nEmpfehlungsprogramm:\n• Freund einladen — du +{ref_ref}, er/sie +{ref_new}\n• Dein Link: /refer\n\nRegeln & Datenschutz:\n• NSFW/Promis verboten\n• Fotos werden temporär gespeichert; /clear löscht temporär, /forget vollständig\n\nBrauchen Sie Hilfe? Schreiben Sie @piciriga — wir antworten schnell.",
        "need_photo": "Bitte zuerst ein Gesichts‑Foto senden.",
        "photo_ok": "Foto empfangen ✅ Beschreibe jetzt die Szene oder nutze /presets.",
        "gen": "Erzeuge… ⏳",
        "fail": "Erzeugung fehlgeschlagen. Bitte Beschreibung oder Selfie anpassen.",
        "ready": "Fertig ✅",
        "credits_none": "Keine Credits. Nutze /buy oder /promo. Du kannst auch einen Freund einladen: /refer",
        "limit_80": "Du hast {pct}% deines Limits verbraucht.",
        "unlock": "🔒 Unbegrenzt freischalten für 2 €/Tag",
        "hint_refer_zero": "👥 Du hast 0 Credits. Lade einen Freund ein — +{ref_ref} dir und +{ref_new} ihm/ihr: /refer",
        "btn_invite": "👥 Freund einladen",
        "choose_lang": "🌐 Sprache für die Oberfläche wählen:",
        "lang_ru": "Sprache gesetzt: Russisch",
        "lang_en": "Sprache gesetzt: Englisch",
        "lang_ro": "Sprache gesetzt: Rumänisch",
        "lang_de": "Sprache gesetzt: Deutsch",
        "presets": "Szenen‑Ideen:\n• Studio: Porträt, weiches Licht, dunkler Hintergrund\n• Outdoor: Sonnenuntergang, Bokeh, 85mm\n• Interior: Café, warme Töne, Vintage\n• Natur: Wald, diffuses Licht, Film‑Look",
        "blocked": "⛔ Anfrage blockiert.",
        "btn_balance": "Guthaben",
        "btn_buy": "Kaufen",
        "btn_more": "Mehr",
        "btn_publish": "Veröffentlichen",
        "btn_publish_group": "In Gruppe",
        "menu_presets": "🎛 Presets",
        "menu_help": "🆘 Hilfe",
        "menu_refer": "🎁 Kostenlose Credits",
        "menu_invite": "👥 Freund einladen",
        "btn_support": "📨 Support kontaktieren",
        "btn_back": "⬅️ Zurück",
        "btn_refer": "🎁 Kostenlose Credits",
        "hint_refer_pay": "🎁 Tipp: Freund einladen — +{ref_ref} dir · +{ref_new} ihm/ihr",
        "menu_pricing": "💎 Preise",
        "buy_title": "💳 Käufe (Telegram Stars)\nWähle ein passendes Paket:",
        "buy_btn_10": "10 Gen — 200★",
        "buy_btn_30": "30 Gen — 500★",
        "buy_btn_100": "100 Gen — 1200★",
        "bought": "Danke! +{add}. Gesamt: {all}.",
        "promo_usage": "Verwendung: /promo CODE",
        "promo_ok": "Promo angewendet: +{add}. Gesamt: {all}.",
        "promo_bad": "Promo ungültig.",
        "version": "ℹ️ Version: {ver}",
        "balance": "Dein Guthaben: {n} Generationen{free}",
        "balance_free": " (Whitelist/Admin — keine Abzüge)",
        "cleared": "Speicher geleert.",
        "tos": "Nutzung: Fotos nur zur Generierung; NSFW/Celebrities verboten; Ergebnis bis zu 72h gespeichert.",
        "privacy": "Datenschutz: keine Weitergabe; /clear löscht temporär; /forget löscht vollständig.",
        "admin_only": "Nur Admins.",
        "granted": "{n} Gen an {uid} vergeben. Guthaben: {bal}.",
        "free_added": "Nutzer {uid} zur Whitelist hinzugefügt.",
        "gallery_empty": "Galerie ist leer.",
        "ref_link_fail": "Bot‑Username nicht ermittelt.",
        "pricing": "💎 iModel Preise\n\n• 10 Gen — 200★  (20★/Gen)\n• 30 Gen — 500★  (≈16.7★/Gen)\n• 100 Gen — 1200★ (12★/Gen)\n\nBezahlung via Telegram Stars. Größere Pakete sind günstiger.",
        "copy_intro": "📋 Kopier‑Modus\nSchritt 1: Stil‑Referenz senden (Szene)\nSchritt 2: dein Selfie senden\nErgebnis: gleiche Szene, nur Gesicht ersetzt.",
        "copy_style_ok": "Stil‑Referenz empfangen ✅ Jetzt dein Selfie senden.",
        "copy_need_style": "Bitte zuerst die Stil‑Referenz senden.",
        "copy_done": "Fertig ✅",
        "copy_exit": "Kopier‑Modus AUS.",
        "menu_copy": "📋 Kopieren",
    }
}

def L(chat_id: int) -> dict:
    return T.get(USER_LANG.get(chat_id, LANG_DEFAULT), T[LANG_DEFAULT])

def locale_to_lang(code: Optional[str]) -> str:
    if not code:
        return LANG_DEFAULT
    code = code.lower()
    base = code.split("-")[0]
    if base in ("ru", "uk", "be"):
        return "ru"
    if base in ("ro", "mo"):
        return "ro"
    if base in ("en",):
        return "en"
    if base in ("de",):
        return "de"
    return LANG_DEFAULT

# ===================== FILTER ========================
_SEXUAL_RE = re.compile(r"(nsfw|nude|nudity|porn|xxx|sex|sexual)", re.IGNORECASE)
_CELEB_RE  = re.compile(r"(celebrity|public\s*figure)", re.IGNORECASE)
_MINOR_RE  = re.compile(r"(minor|underage|child|kid|teen|baby|дет|реб[её]нок|подросток)", re.IGNORECASE)

def blocked(text: str) -> bool:
    s = (text or "").strip()
    # Ignore safe disclaimers like "no nudity", "no celebrity", "no public figure(s)", "no minors"
    s = re.sub(r"\bno\s+(nsfw|nude|nudity|porn|xxx|sex|sexual|celebrity|celebrities|public\s*figure[s]?|minor[s]?|children|kids|teens|underage)\b", "", s, flags=re.I)

    # Always block sexual content involving minors
    if _SEXUAL_RE.search(s) and _MINOR_RE.search(s):
        return True

    # Optional blocks controlled by env flags
    if (not ALLOW_NSFW) and _SEXUAL_RE.search(s):
        return True
    return False

# ===================== Lang detect (fallback) ========
def detect_lang(sample: str) -> str:
    s = (sample or "").lower()
    if not s:
        return LANG_DEFAULT
    if re.search(r"[ăâîșşțţ]", s):
        return "ro"
    if re.search(r"[äöüß]", s):
        return "de"
    cyr = sum(1 for ch in s if "а" <= ch <= "я" or ch == "ё")
    lat = sum(1 for ch in s if "a" <= ch <= "z")
    if cyr > lat * 1.2:
        return "ru"
    return "en"

# ===================== Safe Telegram send ============
async def safe_answer(m: Message, text: str, **kwargs):
    try:
        return await m.answer(text, **kwargs)
    except (TelegramForbiddenError, TelegramNotFound):
        print(f"[safe_answer] blocked/not found: chat_id={m.chat.id}")
    except TelegramBadRequest as e:
        print(f"[safe_answer] bad request: {e}")
    return None

async def safe_answer_photo(m: Message, photo: BufferedInputFile, **kwargs):
    try:
        return await m.answer_photo(photo=photo, **kwargs)
    except (TelegramForbiddenError, TelegramNotFound):
        print(f"[safe_answer_photo] blocked/not found: chat_id={m.chat.id}")
    except TelegramBadRequest as e:
        print(f"[safe_answer_photo] bad request: {e}")
    return None

async def safe_edit_text(msg: Message, text: str):
    try:
        return await msg.edit_text(text)
    except TelegramBadRequest as e:
        print(f"[safe_edit_text] bad request: {e}")
    return None

async def safe_cb_answer(c: CallbackQuery, *args, **kwargs):
    try:
        return await c.answer(*args, **kwargs)
    except TelegramBadRequest as e:
        print(f"[safe_cb_answer] bad request: {e}")
    except Exception as e:
        print(f"[safe_cb_answer] exception: {e}")
    return None
async def safe_send_text(chat_id: int, text: str, **kwargs):
    try:
        return await bot.send_message(chat_id, text, **kwargs)
    except (TelegramForbiddenError, TelegramNotFound):
        print(f"[safe_send_text] blocked/not found: chat_id={chat_id}")
    except TelegramBadRequest as e:
        print(f"[safe_send_text] bad request: {e}")
    return None

# ===================== PROMO: +2 TO ALL ===============
def _promo_two_msg(lang: str) -> str:
    lang = (lang or LANG_DEFAULT).lower()
    if lang.startswith("ru"):
        return (
            "Сегодня только: +2 бесплатные генерации в iModel. Обнови аватарку, примерь стиль, сделай кадр уровня журнала.\n"
            "Бонус уже начислен на ваш баланс. Отправьте селфи — и получите результат за секунды.\n"
            "/presets для идей • /copy чтобы скопировать стиль • /start"
        )
    if lang.startswith("ro"):
        return (
            "Doar azi: +2 generări gratuite în iModel. Reîmprospătează avatarul, încearcă un stil nou, rezultate de nivel revistă.\n"
            "Bonusul a fost adăugat. Trimite un selfie — primești rezultatul în secunde.\n"
            "/presets pentru idei • /copy pentru a copia stilul • /start"
        )
    if lang.startswith("de"):
        return (
            "Nur heute: +2 kostenlose Generierungen in iModel. Neues Profilbild, neuer Stil, Magazin‑Look.\n"
            "Bonus ist bereits gutgeschrieben. Schicke ein Selfie — Ergebnis in Sekunden.\n"
            "/presets für Ideen • /copy um Stil zu kopieren • /start"
        )
    # default EN
    return (
        "Today only: +2 free generations in iModel. Refresh your avatar, try a new style, get magazine‑level results.\n"
        "Bonus already added to your balance. Send a selfie — get results in seconds.\n"
        "/presets for ideas • /copy to copy a style • /start"
    )

@dp.message(Command("grant2all"))
async def cmd_grant2all(m: Message):
    # Admin‑only safety
    if not is_admin(m.chat.id, getattr(m.from_user, "username", None)):
        return await safe_answer(m, L(m.chat.id)["admin_only"])
    # Grant +2 to all known users and send localized message
    uids = list(STATS_USERS_INFO.keys())
    if not uids:
        return await safe_answer(m, "Нет сохранённых пользователей для рассылки.")
    added = 0
    sent = 0
    for uid in uids:
        try:
            USER_CREDITS[uid] = USER_CREDITS.get(uid, FREE_QUOTA) + 2
            added += 1
        except Exception:
            continue
    try:
        _credits_save()
    except Exception:
        pass
    # Send messages in user language (if known)
    for uid in uids:
        try:
            lang = USER_LANG.get(uid, LANG_DEFAULT)
            text = _promo_two_msg(lang)
            r = await safe_send_text(uid, text)
            if r:
                sent += 1
        except Exception:
            continue
    await safe_answer(m, f"✅ Начислено +2 всем ({added}). Сообщение отправлено: {sent}.")

# One-per-day referral hint
async def maybe_send_referral_hint(uid: int):
    try:
        day = _date_key()
        info = STATS_USERS_INFO.setdefault(uid, {})
        if info.get("ref_hint_day") == day:
            return
        info["ref_hint_day"] = day
        users_save()
        lang = USER_LANG.get(uid, LANG_DEFAULT)
        txt = {
            "ru": f"👥 Рефералка: пригласи друга — +{REF_BONUS_REF} тебе и +{REF_BONUS_NEW} ему. /refer",
            "en": f"👥 Referral: invite a friend — +{REF_BONUS_REF} you, +{REF_BONUS_NEW} friend. /refer",
            "ro": f"👥 Recomandă: invită un prieten — +{REF_BONUS_REF} ție, +{REF_BONUS_NEW} lui/ei. /refer",
            "de": f"👥 Empfehlung: lade Freund ein — +{REF_BONUS_REF} dir, +{REF_BONUS_NEW} ihm/ihr. /refer",
        }.get(lang, f"Referral: invite a friend — +{REF_BONUS_REF} you, +{REF_BONUS_NEW} friend. /refer")
        await safe_send_text(uid, txt)
    except Exception as e:
        print("referral hint error:", str(e)[:160])

# ===================== S3 HELPERS ====================
def s3_put_and_presign(img_bytes: bytes, key_prefix: str = "inputs/") -> Optional[str]:
    missing = []
    if not S3_BUCKET:   missing.append("S3_BUCKET")
    if not S3_KEY_ID:   missing.append("S3_ACCESS_KEY_ID")
    if not S3_SECRET:   missing.append("S3_SECRET_ACCESS_KEY")
    if not S3_ENDPOINT: missing.append("S3_ENDPOINT")
    if not S3_REGION:   missing.append("S3_REGION")
    if missing:
        print("❌ S3 config incomplete →", ", ".join(missing))
        return None
    key = f"{key_prefix}{int(time.time())}_{hashlib.md5(img_bytes).hexdigest()[:8]}.jpg"
    try:
        _s3.put_object(Bucket=S3_BUCKET, Key=key, Body=img_bytes, ContentType="image/jpeg")
        url = _s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": S3_BUCKET, "Key": key},
            ExpiresIn=3600
        )
        # Avoid leaking signed parameters in logs
        try:
            parts = urlsplit(url)
            masked = urlunsplit((parts.scheme, parts.netloc, parts.path, "", ""))
            print("S3 presigned url:", masked)
        except Exception:
            pass
        return url
    except Exception as e:
        print("S3 upload/presign error:", str(e)[:200])
        return None

# ===================== REPLICATE HELPERS =============
def _extract_first_url(output) -> Optional[str]:
    if output is None:
        return None
    if isinstance(output, str):
        return output if output.startswith("http") else None
    if isinstance(output, dict):
        if "output" in output:
            return _extract_first_url(output["output"])
        for v in output.values():
            u = _extract_first_url(v)
            if u:
                return u
        return None
    if isinstance(output, (list, tuple)):
        for v in output:
            u = _extract_first_url(v)
            if u:
                return u
        return None
    return None

def replicate_wait_prediction(pred_id: str, timeout: float = 180.0, interval: float = 1.5):
    start = time.time()
    while True:
        pred = replicate.predictions.get(pred_id)
        st = getattr(pred, "status", None) or (pred.get("status") if isinstance(pred, dict) else None)
        if st in ("succeeded", "failed", "canceled"):
            return pred
        if time.time() - start > timeout:
            return pred
        time.sleep(interval)

REPLICATE_LAST_ERROR: str = ""

def replicate_generate(model: str, inputs: dict) -> Optional[str]:
    global REPLICATE_LAST_ERROR
    REPLICATE_LAST_ERROR = ""
    # Allow passing either owner/name or owner/name:version
    model_name = model
    model_version = None
    if ":" in model and not model.endswith(":"):
        try:
            model_name, model_version = model.split(":", 1)
        except ValueError:
            model_name = model
            model_version = None
    try:
        # Prefer creating by version if provided
        if model_version:
            pred = replicate.predictions.create(version=model_version, input=inputs)
        else:
            pred = replicate.predictions.create(model=model_name, input=inputs)
        pid = getattr(pred, "id", None) or (pred.get("id") if isinstance(pred, dict) else None)
        if pid:
            pred = replicate_wait_prediction(pid)
            status = getattr(pred, "status", None) or (pred.get("status") if isinstance(pred, dict) else None)
            if status != "succeeded":
                err = getattr(pred, "error", None) or (pred.get("error") if isinstance(pred, dict) else None)
                if err:
                    msg = str(err)
                    print("Replicate prediction error:", msg[:200])
                    if "sensitive" in msg.lower():
                        return "SENSITIVE"
                else:
                    print("Replicate prediction not succeeded:", status)
            out = getattr(pred, "output", None) or (pred.get("output") if isinstance(pred, dict) else None)
            url = _extract_first_url(out)
            if url:
                return url
            try:
                url = _extract_first_url(dict(pred))
                if url:
                    return url
            except Exception:
                pass
    except Exception as e:
        em = str(e)
        REPLICATE_LAST_ERROR = em
        print("replicate.predictions.create error:", em[:200])
        if "sensitive" in em.lower():
            return "SENSITIVE"

    try:
        # replicate.run supports owner/name or owner/name:version
        out = replicate.run(model if not model_version else f"{model_name}:{model_version}", input=inputs)
        url = _extract_first_url(out)
        if url:
            return url
    except Exception as e2:
        em2 = str(e2)
        REPLICATE_LAST_ERROR = em2
        print("replicate.run error:", em2[:200])
        if "sensitive" in em2.lower():
            return "SENSITIVE"

    return None

# ===================== HTTP DOWNLOAD ==================
def _download_with_retries(url: str, tries: int = 4, base_sleep: float = 0.6) -> Optional[bytes]:
    for i in range(max(1, tries)):
        try:
            r = requests.get(url, timeout=180)
            if r.ok and r.content:
                return r.content
        except Exception:
            pass
        time.sleep(base_sleep * (i + 1))
    return None

## size-shrink helper removed per request

# ===================== PROMPTS ========================
def _safe_suffix() -> str:
    parts = []
    if not ALLOW_NSFW:
        parts.append("safe for work, fully clothed")
        parts.append("no nudity")
        parts.append("no sexual content")
    if not ALLOW_CELEBS:
        parts.append("no celebrity")
    parts.append("respectful")
    return " | " + ", ".join(parts)

IDENTITY_LOCK = (
    "Keep the SAME person from the input selfie. Preserve facial identity, "
    "facial structure, bone structure, age, skin tone, natural eye color, hairline and hair color. "
    "Do not alter ethnicity, face proportions, freckles, moles, or scars. "
    "No face reshaping, no beautification filters, no de-aging, no make-up exaggeration."
)

NEGATIVE_LOCK = (
    "different person, identity change, changed ethnicity, de-aged, "
    "face morph, face swap artifacts, over-smooth skin, plastic doll, uncanny face, "
    "warped features, duplicate face, extra fingers, extra hands, artifacts, lowres"
)

# Используем только когда нужно зафиксировать сцену (copy exact scene)
SCENE_CHANGE_BAN = (
    "changed background, different background, different scene, composition changed, new objects, added elements"
)

SCENE_LOCK = (
    "Copy the scene EXACTLY from the style reference: the same background and environment, the same composition and framing, "
    "the same camera angle and focal length, the same depth of field, the same lighting direction/intensity and color grading, "
    "the same time of day and ambience, the same pose and head orientation. Do not add or remove objects; do not crop or reframe. "
    "Only replace the face; keep everything else identical."
)

STRICT_NEGATIVE = (
    "beautify filter, airbrushed skin, over-retouched skin, body reshaped, face reshaped"
)

def enforce_safe_prompt(user_text: str) -> str:
    text = (user_text or "").strip()
    if not ALLOW_NSFW:
        # Remove explicit NSFW terms; keep SFW framing
        text = re.sub(r"\b(nsfw|nude|nudity|xxx|sex)\b", "", text, flags=re.I)
    suffix = _safe_suffix()
    if suffix.lower() not in text.lower():
        text = f"{text}. {suffix}"
    return text

def safer_variant(prompt: str) -> str:
    base = re.sub(r",?\s*no celebrity.*$", "", prompt, flags=re.I)
    extra = " | conservative clothing, neutral pose, documentary portrait, editorial style"
    return f"{base}{extra}"

def craft_prompt_gpt(raw_prompt: str, lang: str = "ru", allow_refine: bool = True) -> str:
    safe_raw = enforce_safe_prompt(raw_prompt)
    if not allow_refine or os.getenv("DISABLE_GPT_REFINE") == "1" or not OPENAI_API_KEY or OpenAI is None:
        base = safe_raw
    else:
        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
            sys = ("You are a prompt writer for a face-preserving image generation pipeline. "
                   "Rewrite the user's brief into a concise, vivid, SFW English prompt that "
                   "keeps the same person and the same intent. Ensure: fully clothed, SFW.")
            user = (f"User prompt: {raw_prompt}\n\n"
                    "Rewrite to one line. Add environment, mood, lighting, camera. Keep it respectful and SFW.")
            resp = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "system", "content": sys},
                          {"role": "user", "content": user}],
                temperature=0.5,
                max_tokens=160,
            )
            refined = (resp.choices[0].message.content or "").strip()
            base = enforce_safe_prompt(refined or safe_raw)
        except Exception as e:
            print("GPT refine error:", str(e)[:200])
            base = safe_raw
    final = f"{base}. {IDENTITY_LOCK}".strip()
    return final

# ===== Vision: извлечение «scene spec» из style-рефа =====
def craft_scene_spec_from_image(style_bytes: bytes) -> Optional[str]:
    if not OPENAI_API_KEY or OpenAI is None:
        return None
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        b64 = base64.b64encode(style_bytes).decode("utf-8")
        sys = (
            "You are a senior photographer. Extract a ONE-LINE SCENE SPEC for exact recreation with a different face. "
            "Be concrete and visual, avoid prose. Include in order: environment/location; composition & framing (closeup/half-body/etc); "
            "camera angle and focal length feel; pose & head orientation; time of day; lighting direction/quality; color palette/color grading; "
            "style adjectives; any distinctive background cues. Keep subject generic (person). SFW only."
        )
        msg = [
            {"role": "system", "content": sys},
            {"role": "user", "content": [
                {"type": "text", "text": "Describe the scene for 1:1 copy."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ]}
        ]
        r = client.chat.completions.create(model=OPENAI_MODEL_VISION, messages=msg, temperature=0.2, max_tokens=180)
        line = (r.choices[0].message.content or "").strip()
        if not line:
            return None
        line = enforce_safe_prompt(line)
        return f"{line}. {SCENE_LOCK}"
    except Exception as e:
        print("Vision scene error:", str(e)[:200])
        return None

def craft_mj_prompt_from_image(style_bytes: bytes) -> Optional[str]:
    """Produce a detailed Midjourney-style prompt describing the style image (SFW)."""
    if not OPENAI_API_KEY or OpenAI is None:
        return None
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        b64 = base64.b64encode(style_bytes).decode("utf-8")
        sys = (
            "You are an expert Midjourney prompt engineer. Given a single reference photo, "
            "write ONE LINE Midjourney-style prompt (concise but very detailed). "
            "Focus on: subject description (generic, no names), environment, composition/framing, camera angle, lens/focal feel, "
            "lighting direction/quality, color palette/color grading, mood, style/adjectives, textures, time of day. "
            "Keep SFW (fully clothed), avoid any brand/celebrity names, keep it respectful. Do not mention 'reference' or 'face swap'."
        )
        user_content = [
            {"type": "text", "text": "Create a one-line Midjourney prompt capturing this photo's style."},
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
        ]
        msg = [
            {"role": "system", "content": sys},
            {"role": "user", "content": user_content},
        ]
        r = client.chat.completions.create(
            model=OPENAI_MODEL_VISION,
            messages=msg,
            temperature=0.2,
            max_tokens=200,
        )
        line = (r.choices[0].message.content or "").strip()
        if not line:
            return None
        # Ensure SFW suffix but do not force age
        try:
            line2 = enforce_safe_prompt(line)
            if line2:
                line = line2
            stats_incr("mj_prompt_ok", 1)
        except Exception:
            stats_incr("mj_prompt_ok", 1)
        return line
    except Exception as e:
        print("Vision MJ prompt error:", str(e)[:200])
        stats_incr("mj_prompt_fail", 1)
        return None

# ===== Короткий caption (для канала) =================
def generate_instacaption(user_prompt: str, lang: str = "ru") -> str:
    # (как раньше) — опущено ради краткости
    salts = ["Soft light. Sharp story.", "A little magic, a lot of you.", "Subtle glow, bold vibe."]
    return random.choice(salts)

# (retouch feature removed)

# ===================== NUDGES ========================
NUDGE_ENABLED = os.getenv("NUDGE_ENABLED", "0") == "1"
NUDGE_INTERVAL_HOURS = int(os.getenv("NUDGE_INTERVAL_HOURS", "24"))
NUDGE_MIN_GAP_HOURS = int(os.getenv("NUDGE_MIN_GAP_HOURS", "24"))
NUDGE_BATCH_LIMIT = int(os.getenv("NUDGE_BATCH_LIMIT", "25"))
NUDGE_DAY_START_HOUR = int(os.getenv("NUDGE_DAY_START_HOUR", "10"))  # 10:00
NUDGE_DAY_END_HOUR = int(os.getenv("NUDGE_DAY_END_HOUR", "20"))      # 20:00
NUDGE_TZ_DEFAULT = os.getenv("NUDGE_TZ_DEFAULT", "UTC")
NUDGE_INFO: Dict[int, Dict[str, object]] = {}

def _nudge_eligible(uid: int) -> bool:
    now = time.time()
    ui = STATS_USERS_INFO.get(uid) or {}
    last_seen = float(ui.get("last_seen", 0))
    if last_seen <= 0:
        return False
    if now - last_seen < NUDGE_INTERVAL_HOURS * 3600:
        return False
    ni = NUDGE_INFO.get(uid) or {}
    last_sent = float(ni.get("last_sent", 0))
    if last_sent and now - last_sent < NUDGE_MIN_GAP_HOURS * 3600:
        return False
    return True

def _nudge_pick_offer(uid: int) -> Dict[str, object]:
    # Profile-based: paid users → PROMO3, others → FREE1
    ui = STATS_USERS_INFO.get(uid) or {}
    paid = int(ui.get("payments", 0)) > 0
    if paid:
        return {"kind": "PROMO3"}
    return {"kind": "FREE1"}

def _lang_to_tz(lang: str) -> str:
    base = (lang or "").lower()
    if base.startswith("ru") or base.startswith("uk") or base.startswith("be"):
        return os.getenv("NUDGE_TZ_RU", "Europe/Moscow")
    if base.startswith("ro") or base.startswith("mo"):
        return os.getenv("NUDGE_TZ_RO", "Europe/Bucharest")
    if base.startswith("en"):
        return os.getenv("NUDGE_TZ_EN", NUDGE_TZ_DEFAULT)
    return NUDGE_TZ_DEFAULT

def _nudge_allowed_now(lang: str) -> bool:
    try:
        from zoneinfo import ZoneInfo
        tzname = _lang_to_tz(lang)
        now_local = time.time()
        # Convert using ZoneInfo
        dt = time.gmtime(now_local)
        # Using time module for portability: derive offset via ZoneInfo by datetime
        import datetime as _dt
        dt_local = _dt.datetime.now(ZoneInfo(tzname))
        hour = dt_local.hour
    except Exception:
        hour = int(time.strftime("%H", time.gmtime()))
    start_h = min(NUDGE_DAY_START_HOUR, NUDGE_DAY_END_HOUR)
    end_h = max(NUDGE_DAY_START_HOUR, NUDGE_DAY_END_HOUR)
    return start_h <= hour < end_h

def _create_user_promo(uid: int, add: int = 3, ttl_uses: int = 1) -> str:
    code = f"BACK{add}_{uid}_{random.randint(100,999)}".upper()
    PROMO_CODES[code] = {"add": add, "uses": ttl_uses}
    return code

def craft_gpt_nudge(lang: str, offer: Dict[str, object], promo_code: str | None = None) -> str:
    base_fallbacks = {
        "ru": [
            "Возвращайтесь в iModel — новые стили уже ждут вас!",
            "Пора обновить аватарку? Загружайте селфи и получайте результат за секунды.",
            "Дарим бонусную генерацию — попробуйте новый образ прямо сейчас!",
        ],
        "en": [
            "Come back to iModel — fresh styles are waiting!",
            "Time to refresh your avatar? Drop a selfie and get magic.",
            "Claim your bonus generation and try a new look now!",
        ],
        "ro": [
            "Revino în iModel — stiluri noi te așteaptă!",
            "E timpul pentru un avatar nou? Încarcă un selfie și vezi magia.",
            "Primește o generație bonus — încearcă acum!",
        ],
    }
    try:
        if not OPENAI_API_KEY or OpenAI is None:
            raise RuntimeError("no_openai")
        client = OpenAI(api_key=OPENAI_API_KEY)
        sys = (
            "You are a direct-response marketer. Write a short, punchy, 1-2 sentence push message "
            "to re-engage a user in a photo-generation bot. Use energetic, inviting tone and clear CTA. "
            "No hashtags, no emojis overuse (max 1)."
        )
        offer_line = ""
        if offer.get("kind") == "FREE1":
            offer_line = "Offer: 1 free generation today."
        elif offer.get("kind") == "PROMO3":
            offer_line = f"Offer: promo code {promo_code} (+3 gens)."
        lang_hint = {"ru": "Russian", "en": "English", "ro": "Romanian"}.get(lang, "English")
        user = f"User language: {lang_hint}. {offer_line}\nWrite the push copy."
        r = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "system", "content": sys}, {"role": "user", "content": user}],
            temperature=0.8,
            max_tokens=80,
        )
        msg = (r.choices[0].message.content or "").strip()
        if not msg:
            raise RuntimeError("empty")
        return msg
    except Exception:
        arr = base_fallbacks.get(lang) or base_fallbacks["en"]
        return random.choice(arr)

async def _send_nudge(uid: int, lang: str):
    ni = NUDGE_INFO.setdefault(uid, {})
    offer = _nudge_pick_offer(uid)
    promo_code = None
    granted = 0
    if offer["kind"] == "FREE1":
        USER_CREDITS[uid] = USER_CREDITS.get(uid, FREE_QUOTA) + 1
        _credits_save()
        granted = 1
    elif offer["kind"] == "PROMO3":
        promo_code = _create_user_promo(uid, add=3, ttl_uses=1)
    text = craft_gpt_nudge(lang, offer, promo_code)
    if offer["kind"] == "FREE1":
        text += ({"ru": "\nБонус: +1 генерация уже на балансе.", "en": "\nBonus: +1 generation added.", "ro": "\nBonus: +1 generație adăugată."}.get(lang, ""))
    elif offer["kind"] == "PROMO3" and promo_code:
        k = {"ru": "\nПромокод: ", "en": "\nPromo code: ", "ro": "\nCod promo: "}.get(lang, "\nPromo: ")
        text += f"{k}{promo_code}"
    sent = await safe_send_text(uid, text)
    if sent:
        ni["last_sent"] = time.time()
        stats_incr("nudges_sent", 1)
        if granted:
            stats_incr("nudges_granted", 1)
    else:
        stats_incr("nudges_errors", 1)

async def nudge_loop():
    # Run hourly; send up to NUDGE_BATCH_LIMIT eligible nudges
    await asyncio.sleep(5)
    while True:
        try:
            if NUDGE_ENABLED and STATS_USERS_INFO:
                # Pass 1: 12h inactivity nudges (one per inactivity episode)
                try:
                    now_ts = time.time()
                    uids = list(STATS_USERS_INFO.keys())
                    random.shuffle(uids)
                    sent_total = 0
                    for uid in uids:
                        if sent_total >= NUDGE_BATCH_LIMIT:
                            break
                        ui = STATS_USERS_INFO.get(uid) or {}
                        last_seen = float(ui.get("last_seen", 0.0))
                        last_sent = float(ui.get("inactive12_sent_at", 0.0))
                        if last_seen <= 0:
                            continue
                        # Send once after 12h since last activity, and only once per inactivity episode
                        if (now_ts - last_seen) >= 12 * 3600 and (last_sent < last_seen):
                            lang = USER_LANG.get(uid, LANG_DEFAULT)
                            if not _nudge_allowed_now(lang):
                                continue
                            if await safe_send_text(uid, _msg_inactive12(lang)):
                                ui["inactive12_sent_at"] = now_ts
                                users_save()
                                stats_incr("nudges_sent", 1)
                                sent_total += 1
                except Exception as e:
                    print("inactive12 nudge error:", str(e)[:200])

                # Pass 2: generic offer nudges per existing logic
                eligible = [uid for uid in list(STATS_USERS_INFO.keys()) if _nudge_eligible(uid)]
                random.shuffle(eligible)
                for uid in eligible[:NUDGE_BATCH_LIMIT]:
                    lang = USER_LANG.get(uid, LANG_DEFAULT)
                    if not _nudge_allowed_now(lang):
                        continue
                    await _send_nudge(uid, lang)
        except Exception as e:
            print("nudge_loop error:", str(e)[:200])
        await asyncio.sleep(3600)

# ===================== CORE GEN ======================
def generate_image_from_bytes(
    img_bytes: bytes,
    user_prompt: str,
    lang: str = "ru",
    seed: Optional[int] = None,
    strict: bool = False,
    style_bytes: Optional[bytes] = None,
    lock_scene: bool = True,
) -> Optional[bytes]:
    if blocked(user_prompt):
        print("⛔ Заблокировано фильтром")
        return None

    # In strict (Copy Mode), avoid GPT rephrasing to keep scene constraints intact
    refined = craft_prompt_gpt(user_prompt, lang=lang, allow_refine=not strict)
    if strict and lock_scene:
        refined = f"{refined}. {SCENE_LOCK}. Exact same background, composition, lighting, color grading; only replace the face."

    print(f"→ Генерация: {refined[:180]}...")

    src_url = s3_put_and_presign(img_bytes, key_prefix="inputs/")
    if not src_url:
        print("→ Не удалось получить S3 presigned URL")
        return None

    style_url: Optional[str] = None
    if strict and style_bytes:
        style_url = s3_put_and_presign(style_bytes, key_prefix="style/")
        if not style_url:
            print("→ Не удалось получить S3 URL для style-ref (продолжаем без него)")

    def try_nano(p: str, seed_val: Optional[int] = None) -> Optional[str]:
        if strict and lock_scene:
            neg = f"{NEGATIVE_LOCK}, {STRICT_NEGATIVE}, {SCENE_CHANGE_BAN}"
        elif strict:
            neg = f"{NEGATIVE_LOCK}, {STRICT_NEGATIVE}"
        else:
            neg = NEGATIVE_LOCK
        inputs_common = {
            "prompt": p,
            "negative_prompt": neg,
        }
        if seed_val is not None:
            inputs_common["seed"] = seed_val

        # If we have a style reference, try two-image conditions first
        if style_url:
            candidates: List[Dict[str, object]] = []
            # Common combos across popular face-replace/copy-scene models
            candidates.append({"image_input": [style_url, src_url]})
            candidates.append({"image_input": [src_url, style_url]})
            candidates.append({"image": style_url, "face_image": src_url})
            candidates.append({"image": style_url, "person_image": src_url})
            candidates.append({"image": style_url, "target_face": src_url})
            candidates.append({"image": src_url, "style_image": style_url})
            candidates.append({"source_image": style_url, "image": src_url})
            candidates.append({"background": style_url, "image": src_url})
            candidates.append({"reference": style_url, "image": src_url})
            candidates.append({"content_image": style_url, "face_image": src_url})

            # Common guidance/cfg knobs across models
            cfg_variants: List[Dict[str, object]] = [
                {},
                {"guidance_scale": 7.5},
                {"guidance": 7.5},
                {"cfg": 7.0},
                {"cfg_scale": 7.0},
                {"strength": 0.8},
                {"prompt_strength": 0.85},
                {"num_inference_steps": 28},
            ]

            for variant in candidates:
                try:
                    for cfg_extra in cfg_variants:
                        inp = dict(inputs_common)
                        inp.update(variant)
                        inp.update(cfg_extra)
                        url = replicate_generate(NANOBANANA_MODEL, inp)
                        if url == "SENSITIVE":
                            return "SENSITIVE"
                        if url:
                            print("NanoBanana OK (style+selfie variant)", variant.keys(), cfg_extra)
                            return url
                except Exception as e:
                    print("NanoBanana variant exception:", str(e)[:200])

        # 1) image_input (список) — только selfie
        try:
            for cfg_extra in [{}, {"guidance_scale": 7.5}, {"strength": 0.8}, {"num_inference_steps": 28}]:
                inp = dict(inputs_common)
                inp.update(cfg_extra)
                inp["image_input"] = [src_url]
                url = replicate_generate(NANOBANANA_MODEL, inp)
                if url == "SENSITIVE":
                    return "SENSITIVE"
                if url:
                    print("NanoBanana OK (image_input)", cfg_extra)
                    return url
        except Exception as e:
            print("NanoBanana image_input exception:", str(e)[:200])

        # 2) image (одна) — только selfie
        try:
            for cfg_extra in [{}, {"guidance_scale": 7.5}, {"strength": 0.8}, {"num_inference_steps": 28}]:
                inp = dict(inputs_common)
                inp.update(cfg_extra)
                inp["image"] = src_url
                url = replicate_generate(NANOBANANA_MODEL, inp)
                if url == "SENSITIVE":
                    return "SENSITIVE"
                if url:
                    print("NanoBanana OK (image)", cfg_extra)
                    return url
        except Exception as e2:
            print("NanoBanana image exception:", str(e2)[:200])

        return None

    gen_url = try_nano(refined, seed_val=seed)
    if gen_url == "SENSITIVE":
        print("→ Sensitive → safer variant")
        gen_url = try_nano(safer_variant(refined), seed_val=seed)

    # Если «уплыло лицо» — усилить замки и повторить 1 раз
    if (not gen_url or not str(gen_url).startswith("http")) and not strict:
        hard_lock = f"{refined}. Ultra keep identity. Absolutely same face features. {SCENE_LOCK}"
        gen_url = try_nano(hard_lock, seed_val=seed)

    if not gen_url or gen_url == "SENSITIVE" or not gen_url.startswith("http"):
        print("→ gen_url пустой/sensitive")
        return None

    nano_bytes = _download_with_retries(gen_url)
    if not nano_bytes:
        print("→ не скачали NanoBanana")
        return None

    # If model just echoed the same selfie (no change), treat as failure
    try:
        if hashlib.md5(nano_bytes).hexdigest() == hashlib.md5(img_bytes).hexdigest():
            print("→ output equals input (likely echo) — treating as failure")
            return None
    except Exception:
        pass

    # Бережный апскейл
    try:
        global ESRGAN_DISABLED
        if not ESRGAN_MODEL or ESRGAN_DISABLED or DISABLE_ESRGAN:
            return nano_bytes
        up_url = replicate_generate(ESRGAN_MODEL, {
            "image": gen_url,
            "scale": 4,
            "face_enhance": False,
            "model": "RealESRGAN_x4plus"
        })
        if up_url and up_url.startswith("http"):
            up_bytes = _download_with_retries(up_url)
            if up_bytes:
                print("→ ESRGAN x4plus OK")
                return up_bytes
        return nano_bytes
    except Exception as e:
        em = str(e)
        print("ESRGAN error:", em[:200])
        if "404" in em:
            ESRGAN_DISABLED = True
            print("→ Disable upscaler for this runtime (404)")

    return nano_bytes

async def generate_image_from_bytes_async(
    img_bytes: bytes,
    user_prompt: str,
    lang: str = "ru",
    seed: Optional[int] = None,
    strict: bool = False,
    style_bytes: Optional[bytes] = None,
    lock_scene: bool = True,
) -> Optional[bytes]:
    return await asyncio.to_thread(
        generate_image_from_bytes,
        img_bytes,
        user_prompt,
        lang,
        seed,
        strict,
        style_bytes,
        lock_scene,
    )
        

async def generate_image_with_preview_async(
    send_to: Message,
    img_bytes: bytes,
    user_prompt: str,
    lang: str = "ru",
    seed: Optional[int] = None,
    strict: bool = False,
    style_bytes: Optional[bytes] = None,
    lock_scene: bool = True,
) -> Optional[bytes]:
    """Two-phase generation: send preview (no upscale) first, then return final bytes.
    Falls back to normal generation if preview fails."""
    if blocked(user_prompt):
        print("⛔ Заблокировано фильтром")
        return None

    refined = craft_prompt_gpt(user_prompt, lang=lang, allow_refine=not strict)
    if strict and lock_scene:
        refined = f"{refined}. {SCENE_LOCK}. Exact same background, composition, lighting, color grading; only replace the face."

    src_url = s3_put_and_presign(img_bytes, key_prefix="inputs/")
    if not src_url:
        return None
    style_url: Optional[str] = None
    if strict and style_bytes:
        style_url = s3_put_and_presign(style_bytes, key_prefix="style/")

    def _inputs_common(p: str, seed_val: Optional[int]):
        if strict and lock_scene:
            neg = f"{NEGATIVE_LOCK}, {STRICT_NEGATIVE}, {SCENE_CHANGE_BAN}"
        elif strict:
            neg = f"{NEGATIVE_LOCK}, {STRICT_NEGATIVE}"
        else:
            neg = NEGATIVE_LOCK
        base = {"prompt": p, "negative_prompt": neg}
        if seed_val is not None:
            base["seed"] = seed_val
        return base

    # --- Phase 1: try to get Nano (preview) URL ---
    def _try_preview(p: str, seed_val: Optional[int]) -> Optional[str]:
        inputs_common = _inputs_common(p, seed_val)
        # style+selfie combos
        if style_url:
            candidates = [
                {"image_input": [style_url, src_url]},
                {"image_input": [src_url, style_url]},
                {"image": style_url, "face_image": src_url},
                {"image": style_url, "person_image": src_url},
                {"image": style_url, "target_face": src_url},
                {"image": src_url, "style_image": style_url},
                {"source_image": style_url, "image": src_url},
                {"background": style_url, "image": src_url},
                {"reference": style_url, "image": src_url},
                {"content_image": style_url, "face_image": src_url},
            ]
            cfg_variants: List[Dict[str, object]] = [
                {}, {"guidance_scale": 7.5}, {"guidance": 7.5}, {"cfg": 7.0}, {"cfg_scale": 7.0},
                {"strength": 0.8}, {"prompt_strength": 0.85}, {"num_inference_steps": 28},
            ]
            for variant in candidates:
                try:
                    for ce in cfg_variants:
                        inp = dict(inputs_common); inp.update(variant); inp.update(ce)
                        url = replicate_generate(NANOBANANA_MODEL, inp)
                        if url == "SENSITIVE":
                            return "SENSITIVE"
                        if url:
                            return url
                except Exception as e:
                    print("preview variant error:", str(e)[:200])
        # selfie only
        for ce in [{}, {"guidance_scale": 7.5}, {"strength": 0.8}, {"num_inference_steps": 28}]:
            try:
                inp = dict(inputs_common); inp.update(ce); inp["image_input"] = [src_url]
                url = replicate_generate(NANOBANANA_MODEL, inp)
                if url == "SENSITIVE":
                    return "SENSITIVE"
                if url:
                    return url
            except Exception as e:
                print("preview image_input error:", str(e)[:200])
        for ce in [{}, {"guidance_scale": 7.5}, {"strength": 0.8}, {"num_inference_steps": 28}]:
            try:
                inp = dict(inputs_common); inp.update(ce); inp["image"] = src_url
                url = replicate_generate(NANOBANANA_MODEL, inp)
                if url == "SENSITIVE":
                    return "SENSITIVE"
                if url:
                    return url
            except Exception as e:
                print("preview image error:", str(e)[:200])
        return None

    gen_url = _try_preview(refined, seed)
    if gen_url == "SENSITIVE":
        gen_url = _try_preview(safer_variant(refined), seed)
    if (not gen_url or not str(gen_url).startswith("http")) and not strict:
        hard = f"{refined}. Ultra keep identity. Absolutely same face features. {SCENE_LOCK}"
        gen_url = _try_preview(hard, seed)
    if not gen_url or gen_url == "SENSITIVE" or not gen_url.startswith("http"):
        print("preview url missing — fallback to normal generation")
        return await generate_image_from_bytes_async(img_bytes, user_prompt, lang, seed, strict, style_bytes, lock_scene)

    nano_bytes = _download_with_retries(gen_url)
    if not nano_bytes:
        print("preview download failed — fallback to normal generation")
        return await generate_image_from_bytes_async(img_bytes, user_prompt, lang, seed, strict, style_bytes, lock_scene)
    try:
        if hashlib.md5(nano_bytes).hexdigest() == hashlib.md5(img_bytes).hexdigest():
            print("preview equals input — treat as failure")
            return await generate_image_from_bytes_async(img_bytes, user_prompt, lang, seed, strict, style_bytes, lock_scene)
    except Exception:
        pass

    # Send preview now
    try:
        await safe_answer_photo(send_to, BufferedInputFile(nano_bytes, filename="imodel_preview.jpg"), caption="🟡 Preview")
        stats_incr("previews", 1)
    except Exception as e:
        print("send preview error:", str(e)[:160])

    # Upscale to final (may fallback to preview)
    try:
        global ESRGAN_DISABLED
        if not ESRGAN_MODEL or ESRGAN_DISABLED or DISABLE_ESRGAN:
            return nano_bytes
        up_url = replicate_generate(ESRGAN_MODEL, {"image": gen_url, "scale": 4, "face_enhance": False, "model": "RealESRGAN_x4plus"})
        if up_url and up_url.startswith("http"):
            up_bytes = _download_with_retries(up_url)
            if up_bytes:
                return up_bytes
        return nano_bytes
    except Exception as e:
        em = str(e)
        print("preview upscale error:", em[:200])
        if "404" in em:
            ESRGAN_DISABLED = True
        return nano_bytes


# ======= Автопост «до/после» (опционально) ===========
async def post_before_after_to_channel(user_id: int):
    if not GALLERY_CHANNEL_ID:
        return
    before = LAST_REF.get(user_id)
    after  = LAST_PHOTO.get(user_id)
    if not after:
        return
    lang = USER_LANG.get(user_id, LANG_DEFAULT)
    cap  = generate_instacaption(USER_LAST_PROMPT.get(user_id, ""), lang)

    if before:
        media = [
            InputMediaPhoto(type="photo", media=BufferedInputFile(before, filename="before.jpg"), caption="До"),
            InputMediaPhoto(type="photo", media=BufferedInputFile(after,  filename="after.jpg"),  caption=f"После · {cap}"),
        ]
        try:
            await bot.send_media_group(chat_id=GALLERY_CHANNEL_ID, media=media)
        except Exception as e:
            print("auto-post (album) error:", str(e)[:160])
    else:
        try:
            await bot.send_photo(
                chat_id=GALLERY_CHANNEL_ID,
                photo=BufferedInputFile(after, filename="after.jpg"),
                caption=cap
            )
        except Exception as e:
            print("auto-post (single) error:", str(e)[:160])
    stats_incr("auto_post", 1)

# ===================== UI ============================
def kb_actions(chat_id: int) -> InlineKeyboardMarkup:
    lang = L(chat_id)
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔄 " + lang.get("btn_more", "More"),   callback_data="more"),
        InlineKeyboardButton(text="💰 " + lang["btn_balance"], callback_data="balance"),
        InlineKeyboardButton(text="⭐ " + lang["btn_buy"],      callback_data="buy_open"),
    ],
    [
        InlineKeyboardButton(text=lang["menu_copy"], callback_data="copy_open"),
        InlineKeyboardButton(text=lang.get("menu_presets", "🎛 /presets"), callback_data="presets_open"),
        InlineKeyboardButton(text="✨ " + lang.get("btn_publish", "Publish"), callback_data="pub_yes"),
    ]])

def main_menu_inline(chat_id: int) -> InlineKeyboardMarkup:
    lang = L(chat_id)
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐ " + lang["btn_buy"],      callback_data="buy_open"),
            InlineKeyboardButton(text="💰 " + lang["btn_balance"],  callback_data="balance"),
        ],
        [
            InlineKeyboardButton(text=lang.get("menu_presets", "🎛 /presets"), callback_data="presets_open"),
            InlineKeyboardButton(text="📋 " + lang["menu_copy"],   callback_data="copy_open"),
            InlineKeyboardButton(text=lang.get("menu_help", "🆘 /help"),    callback_data="help_open"),
        ],
        [
            InlineKeyboardButton(text=lang.get("menu_lang", "🌐 /lang"), callback_data="lang_open"),
            InlineKeyboardButton(text=lang.get("menu_refer", "🎁 /refer"), callback_data="refer_open"),
            InlineKeyboardButton(text=lang.get("menu_invite", "👥 Invite"), callback_data="refer_open"),
        ],
    ])

def kb_help(chat_id: int) -> InlineKeyboardMarkup:
    lang = L(chat_id)
    # Localized support button + back
    support_txt = lang.get("btn_support", "📨 Support")
    back_txt = lang.get("btn_back", "⬅️ Back")
    refer_txt = lang.get("btn_refer", "👥 Referral link")
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=refer_txt, callback_data="refer_open")],
        [InlineKeyboardButton(text=support_txt, url="https://t.me/piciriga")],
        [InlineKeyboardButton(text=back_txt, callback_data="back_main")],
    ])

def kb_invite_buy(chat_id: int) -> InlineKeyboardMarkup:
    lang = L(chat_id)
    # Add direct subscription CTA row
    lng = USER_LANG.get(chat_id, LANG_DEFAULT)
    if lng.startswith("ru"):
        sub_txt = "🔒 Безлимит — от 2 € / день"
    elif lng.startswith("ro"):
        sub_txt = "🔒 Nelimitat — de la 2 €/zi"
    elif lng.startswith("de"):
        sub_txt = "🔒 Unbegrenzt — ab 2 €/Tag"
    else:
        sub_txt = "🔒 Unlimited — from €2/day"
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=sub_txt, callback_data="buy_sub_3d")],
        [InlineKeyboardButton(text=lang.get("btn_invite", "👥 Invite a friend"), callback_data="refer_open")],
        [InlineKeyboardButton(text="⭐ " + lang.get("btn_buy", "Buy"), callback_data="buy_open")],
    ])

def kb_lang_select(chat_id: int) -> InlineKeyboardMarkup:
    cur = USER_LANG.get(chat_id, LANG_DEFAULT)
    def label(code: str) -> str:
        names = {
            "ru": "🇷🇺 Русский",
            "en": "🇬🇧 English",
            "ro": "🇷🇴 Română",
            "de": "🇩🇪 Deutsch",
        }
        base = names.get(code, code.upper())
        return ("✅ " + base) if code == cur else base
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text=label("en"), callback_data="set_lang_en"),
            InlineKeyboardButton(text=label("ru"), callback_data="set_lang_ru"),
        ],
        [
            InlineKeyboardButton(text=label("ro"), callback_data="set_lang_ro"),
            InlineKeyboardButton(text=label("de"), callback_data="set_lang_de"),
        ],
    ])

# ===================== PAYMENTS (STARS) ==============
def has_credit(chat_id: int, username: Optional[str] = None) -> bool:
    if is_free_user(chat_id, username):
        return True
    return USER_CREDITS.get(chat_id, FREE_QUOTA) > 0

def maybe_send_limit_progress(uid: int):
    try:
        # Only for non-subscribed/non-admin users
        if is_free_user(uid, None):
            return
        total = max(1, int(FREE_QUOTA))
        rem = int(USER_CREDITS.get(uid, FREE_QUOTA))
        used = max(0, total - rem)
        pct = int(used * 100 / total)
        info = STATS_USERS_INFO.setdefault(uid, {})
        if 80 <= pct < 100 and info.get("limit_warn_pct") != 80:
            info["limit_warn_pct"] = 80
            users_save()
            msg = {
                "ru": L(uid)["limit_80"].format(pct=pct) + "\n" + L(uid)["unlock"],
                "en": L(uid)["limit_80"].format(pct=pct) + "\n" + L(uid)["unlock"],
                "ro": L(uid)["limit_80"].format(pct=pct) + "\n" + L(uid)["unlock"],
                "de": L(uid)["limit_80"].format(pct=pct) + "\n" + L(uid)["unlock"],
            }.get(USER_LANG.get(uid, LANG_DEFAULT), L(uid)["limit_80"].format(pct=pct))
            asyncio.create_task(safe_send_text(uid, msg))
    except Exception:
        pass

# ===================== AUTO-MESSAGES ==================
def _msg_after3(lang: str) -> str:
    if lang.startswith("ru"):
        return "Как тебе результат? 🌟 Разблокируй HD-режим!"
    if lang.startswith("ro"):
        return "Îți place rezultatul? 🌟 Deblochează modul HD!"
    if lang.startswith("de"):
        return "Wie gefällt dir das Ergebnis? 🌟 Schalte den HD‑Modus frei!"
    return "How do you like the results? 🌟 Unlock HD mode!"

def _msg_inactive12(lang: str) -> str:
    if lang.startswith("ru"):
        return "Твои фото ждут апгрейда!"
    if lang.startswith("ro"):
        return "Fotografiile tale așteaptă un upgrade!"
    if lang.startswith("de"):
        return "Deine Fotos warten auf ein Upgrade!"
    return "Your photos are waiting for an upgrade!"

def _msg_first_purchase(lang: str) -> str:
    if lang.startswith("ru"):
        return "🔥 Теперь ты в топ-100 моделей iModel!"
    if lang.startswith("ro"):
        return "🔥 Acum ești în top‑100 modele iModel!"
    if lang.startswith("de"):
        return "🔥 Du bist jetzt in den Top‑100 iModel‑Models!"
    return "🔥 You’re now in the top‑100 iModel models!"

async def maybe_trigger_after3(uid: int):
    try:
        info = STATS_USERS_INFO.get(uid)
        if not info:
            return
        total = int(info.get("gens_ok", 0)) + int(info.get("gens_copy_ok", 0))
        if total == 3 and not info.get("milestone3_sent"):
            lang = USER_LANG.get(uid, LANG_DEFAULT)
            await safe_send_text(uid, _msg_after3(lang))
            info["milestone3_sent"] = 1
            users_save()
    except Exception:
        pass

async def send_stars_invoice(chat_id: int, title: str, desc: str, payload: str, amount_stars: int):
    prices = [LabeledPrice(label=title, amount=amount_stars)]
    await bot.send_invoice(
        chat_id=chat_id,
        title=title,
        description=desc,
        payload=payload,
        provider_token="",  # Stars
        currency="XTR",
        prices=prices,
    )

@dp.message(Command("buy"))
async def cmd_buy(m: Message):
    lang = L(m.chat.id)
    # Localize subscription buttons
    lng = USER_LANG.get(m.chat.id, LANG_DEFAULT)
    if lng.startswith("ru"):
        btn_3d = "🔥 3 дня — 900★"
        btn_month = "1 месяц — 2400★"
    elif lng.startswith("ro"):
        btn_3d = "🔥 3 zile — 900★"
        btn_month = "1 lună — 2400★"
    elif lng.startswith("de"):
        btn_3d = "🔥 3 Tage — 900★"
        btn_month = "1 Monat — 2400★"
    else:
        btn_3d = "🔥 3 days — 900★"
        btn_month = "1 month — 2400★"

    rows = [
        [InlineKeyboardButton(text=lang["buy_btn_10"],  callback_data="buy_stars_10")],
        [InlineKeyboardButton(text=lang["buy_btn_30"],  callback_data="buy_stars_30")],
        [InlineKeyboardButton(text=lang["buy_btn_100"], callback_data="buy_stars_100")],
    ]
    if STRIPE_ENABLED:
        rows += [
            [InlineKeyboardButton(text="💳 Card (Stripe) — 10",  callback_data="buy_stripe_10")],
            [InlineKeyboardButton(text="💳 Card (Stripe) — 30",  callback_data="buy_stripe_30")],
            [InlineKeyboardButton(text="💳 Card (Stripe) — 100", callback_data="buy_stripe_100")],
        ]
    rows += [
        [InlineKeyboardButton(text=btn_3d, callback_data="buy_sub_3d")],
        [InlineKeyboardButton(text=btn_month, callback_data="buy_sub_month")],
        [InlineKeyboardButton(text=lang.get("btn_invite", "👥 Invite a friend"), callback_data="refer_open")],
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=rows)
    await safe_answer(m, lang["buy_title"], reply_markup=kb)

@dp.callback_query(F.data.startswith("buy_stars_"))
async def cb_buy_stars(c: CallbackQuery):
    pack = c.data.split("_")[-1]
    # subtle referral tooltip
    txt = L(c.message.chat.id).get("hint_refer_pay", "Invite a friend for free credits").format(ref_new=REF_BONUS_NEW, ref_ref=REF_BONUS_REF)
    if pack == "10":
        await send_stars_invoice(c.message.chat.id, "iModel — 10 генераций", "Пакет 10 генераций", "pack_10", 200)
    elif pack == "30":
        await send_stars_invoice(c.message.chat.id, "iModel — 30 генераций", "Пакет 30 генераций", "pack_30", 500)
    elif pack == "100":
        await send_stars_invoice(c.message.chat.id, "iModel — 100 генераций", "Пакет 100 генераций", "pack_100", 1200)
    await safe_cb_answer(c, txt)

def _stripe_price_for_pack(pack: str) -> Optional[str]:
    if pack == "10":
        return STRIPE_PRICE_10
    if pack == "30":
        return STRIPE_PRICE_30
    if pack == "100":
        return STRIPE_PRICE_100
    return None

def _stripe_pack_add(pack: str) -> int:
    return {"10": 10, "30": 30, "100": 100}.get(pack, 0)

async def _send_buy_link_stripe(chat_id: int, url: str):
    try:
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="💳 Pay securely (Stripe)", url=url)]])
        txt = {
            "ru": "Оплата картой — безопасная ссылка Stripe",
            "en": "Card payment — secure Stripe link",
            "ro": "Plata cu cardul — link Stripe securizat",
            "de": "Kartenzahlung — sicherer Stripe‑Link",
        }.get(USER_LANG.get(chat_id, LANG_DEFAULT), "Secure Stripe checkout link")
        await safe_send_text(chat_id, txt, reply_markup=kb)
    except Exception:
        pass

@dp.callback_query(F.data.startswith("buy_stripe_"))
async def cb_buy_stripe(c: CallbackQuery):
    pack = c.data.split("_")[-1]
    await safe_cb_answer(c)
    if not STRIPE_ENABLED or stripe is None:
        return await c.message.answer("Stripe is not available.")
    price_id = _stripe_price_for_pack(pack)
    if not price_id:
        return await c.message.answer("Pack not available.")
    try:
        session = stripe.checkout.Session.create(
            mode="payment",
            line_items=[{"price": price_id, "quantity": 1}],
            success_url=STRIPE_SUCCESS_URL,
            cancel_url=STRIPE_CANCEL_URL,
            client_reference_id=str(c.message.chat.id),
            metadata={"uid": str(c.message.chat.id), "pack": str(pack)},
        )
        await _send_buy_link_stripe(c.message.chat.id, session.url)
    except Exception as e:
        await c.message.answer(f"Stripe error: {str(e)[:120]}")

@dp.callback_query(F.data.startswith("buy_sub_"))
async def cb_buy_sub(c: CallbackQuery):
    kind = c.data.split("buy_sub_")[-1]
    uid = c.message.chat.id
    # Prices in Stars
    if kind == "3d":
        await send_stars_invoice(uid, "iModel — Подписка на 3 дня", "Неограниченная генерация 72 часа", "sub_3d", 900)
    elif kind == "month":
        await send_stars_invoice(uid, "iModel — Подписка на 1 месяц", "Неограниченная генерация 30 дней", "sub_month", 2400)
    await safe_cb_answer(c)

@dp.pre_checkout_query()
async def process_pre_checkout_q(pcq: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pcq.id, ok=True)

@dp.message(F.successful_payment)
async def got_payment(m: Message):
    payload = m.successful_payment.invoice_payload
    add = 0
    if payload == "pack_10": add = 10
    elif payload == "pack_30": add = 30
    elif payload == "pack_100": add = 100
    # Time subscriptions
    now = time.time()
    period = 0
    if payload == "sub_3d":
        period = 3 * 24 * 3600
    elif payload == "sub_month":
        period = 30 * 24 * 3600
    # ensure user is recorded with username for admin visibility
    _touch_user(m.chat.id, getattr(m.from_user, "username", None))
    if period > 0:
        cur = float(SUBSCR_EXPIRY.get(m.chat.id, 0.0))
        start_from = cur if cur > now else now
        SUBSCR_EXPIRY[m.chat.id] = start_from + period
        _subs_save()
        # Localized confirmation
        exp = int(SUBSCR_EXPIRY[m.chat.id])
        exp_dt = time.strftime("%Y-%m-%d %H:%M", time.gmtime(exp))
        txt = {
            "ru": f"Подписка активирована до {exp_dt} (UTC). Приятной генерации!",
            "en": f"Subscription active until {exp_dt} (UTC). Enjoy!",
            "ro": f"Abonament activ până la {exp_dt} (UTC). Spor!",
            "de": f"Abo aktiv bis {exp_dt} (UTC). Viel Spaß!",
        }.get(USER_LANG.get(m.chat.id, LANG_DEFAULT), f"Subscription active until {exp_dt} (UTC).")
        await safe_answer(m, txt)
    else:
        USER_CREDITS[m.chat.id] = USER_CREDITS.get(m.chat.id, 0) + add
        _credits_save()
        await safe_answer(m, L(m.chat.id)["bought"].format(add=add, all=USER_CREDITS[m.chat.id]))
    # Detect if this is the first purchase for this user
    try:
        prior_pay = int(STATS_USERS_INFO.get(m.chat.id, {}).get("payments", 0))
    except Exception:
        prior_pay = 0
    stats_incr("payments", 1)
    _uadd(m.chat.id, "payments", 1)
    if prior_pay == 0:
        try:
            lang = USER_LANG.get(m.chat.id, LANG_DEFAULT)
            await safe_send_text(m.chat.id, _msg_first_purchase(lang))
        except Exception:
            pass

# ===================== COMMANDS =======================
@dp.message(Command("version"))
async def cmd_version(m: Message):
    await safe_answer(m, f"{L(m.chat.id)['version'].format(ver=APP_VERSION)}")

@dp.message(Command("pricing"))
async def cmd_pricing(m: Message):
    await safe_answer(m, L(m.chat.id)["pricing"])
    await cmd_buy(m)
    # If user has zero credits, highlight Free credits option
    n = USER_CREDITS.get(m.chat.id, FREE_QUOTA)
    if n <= 0 and not is_free_user(m.chat.id, getattr(m.from_user, "username", None)):
        lang = L(m.chat.id)
        hint = lang.get("hint_refer_zero", "Invite a friend: /refer").format(ref_new=REF_BONUS_NEW, ref_ref=REF_BONUS_REF)
    await safe_answer(m, hint, reply_markup=kb_invite_buy(m.chat.id))

@dp.message(Command("audit"))
async def cmd_audit(m: Message):
    # Admin-only
    if not is_admin(m.chat.id, getattr(m.from_user, "username", None)):
        return await safe_answer(m, L(m.chat.id)["admin_only"])
    parts = (m.text or "").split()
    if len(parts) < 2:
        return await safe_answer(m, "Usage: /audit <@username|user_id> [more...]")

    def find_by_username(handle: str) -> list[int]:
        uname = handle.lstrip("@").lower()
        out = []
        for uid, info in STATS_USERS_INFO.items():
            try:
                u = (info.get("username") or "").lower()
                if u == uname:
                    out.append(int(uid))
            except Exception:
                pass
        return out

    lines = []
    now = time.time()
    for token in parts[1:]:
        uids: list[int] = []
        try:
            if token.startswith("@") or not token.isdigit():
                uids = find_by_username(token)
            else:
                uids = [int(token)] if int(token) in STATS_USERS_INFO else []
        except Exception:
            uids = []
        if not uids:
            lines.append(f"{token}: not found")
            continue
        for uid in uids:
            info = STATS_USERS_INFO.get(uid, {})
            gens = int(info.get("gens_ok", 0)) + int(info.get("gens_copy_ok", 0))
            pays = int(info.get("payments", 0))
            uname = info.get("username") or ""
            active_sub = float(SUBSCR_EXPIRY.get(uid, 0.0))
            sub_note = (f"active until {time.strftime('%Y-%m-%d %H:%M', time.gmtime(int(active_sub)))} (UTC)" if active_sub > now else "-")
            free_flags = []
            if is_admin(uid, uname):
                free_flags.append("admin")
            if uid in FREE_USERS:
                free_flags.append("whitelist")
            if active_sub > now:
                free_flags.append("subscription")
            free_str = ", ".join(free_flags) if free_flags else "no"
            bal = ("∞" if is_free_user(uid, uname) else USER_CREDITS.get(uid, FREE_QUOTA))
            ref = REF_STATS.get(uid, {"count": 0, "earned": 0})
            invited = int(ref.get("count", 0))
            earned = int(ref.get("earned", 0))
            last_seen = info.get("last_seen")
            last_note = time.strftime('%Y-%m-%d %H:%M', time.gmtime(int(last_seen))) if last_seen else "-"
            lines.append(
                f"uid={uid} @" + uname +
                f" | gens={gens} pays={pays} bal={bal}\n"
                f"   free={free_str} | sub={sub_note} | invited={invited} (+{earned}) | last={last_note}"
            )
    await safe_answer(m, "\n".join(lines))

@dp.message(Command("sub_revoke"))
async def cmd_sub_revoke(m: Message):
    if not is_admin(m.chat.id, getattr(m.from_user, "username", None)):
        return await safe_answer(m, L(m.chat.id)["admin_only"])
    parts = (m.text or "").split()
    if len(parts) != 2 or not parts[1].isdigit():
        return await safe_answer(m, "Usage: /sub_revoke <user_id>")
    uid = int(parts[1])
    SUBSCR_EXPIRY[uid] = 0.0
    _subs_save()
    await safe_answer(m, f"Revoked Premium for {uid}.")

@dp.message(Command("sub_set"))
async def cmd_sub_set(m: Message):
    if not is_admin(m.chat.id, getattr(m.from_user, "username", None)):
        return await safe_answer(m, L(m.chat.id)["admin_only"])
    parts = (m.text or "").split()
    if len(parts) != 3:
        return await safe_answer(m, "Usage: /sub_set <user_id> <days>")
    try:
        uid = int(parts[1]); days = float(parts[2])
    except Exception:
        return await safe_answer(m, "Usage: /sub_set <user_id> <days>")
    now_ts = time.time()
    cur_exp = float(SUBSCR_EXPIRY.get(uid, 0.0))
    start_from = cur_exp if cur_exp > now_ts else now_ts
    SUBSCR_EXPIRY[uid] = start_from + int(days * 24*3600)
    _subs_save()
    exp_dt = time.strftime("%Y-%m-%d %H:%M", time.gmtime(int(SUBSCR_EXPIRY[uid])))
    await safe_answer(m, f"Premium for {uid} set until {exp_dt} (UTC)")

@dp.message(Command("credits_set"))
async def cmd_credits_set(m: Message):
    if not is_admin(m.chat.id, getattr(m.from_user, "username", None)):
        return await safe_answer(m, L(m.chat.id)["admin_only"])
    parts = (m.text or "").split()
    if len(parts) != 3:
        return await safe_answer(m, "Usage: /credits_set <user_id> <amount>")
    try:
        uid = int(parts[1]); amount = int(parts[2])
    except Exception:
        return await safe_answer(m, "Usage: /credits_set <user_id> <amount>")
    ensure_user_credit(uid)
    USER_CREDITS[uid] = max(0, amount)
    _credits_save()
    await safe_answer(m, f"Credits for {uid}: {USER_CREDITS[uid]}")

@dp.message(Command("audit_top"))
async def cmd_audit_top(m: Message):
    if not is_admin(m.chat.id, getattr(m.from_user, "username", None)):
        return await safe_answer(m, L(m.chat.id)["admin_only"])
    parts = (m.text or "").split()
    topn = 20
    if len(parts) == 2 and parts[1].isdigit():
        topn = max(1, min(100, int(parts[1])))
    items = []
    now = time.time()
    for uid, info in STATS_USERS_INFO.items():
        pays = int(info.get("payments", 0))
        if pays > 0:
            continue
        gens = int(info.get("gens_ok", 0)) + int(info.get("gens_copy_ok", 0))
        if gens <= 0:
            continue
        uname = info.get("username") or ""
        sub_active = float(SUBSCR_EXPIRY.get(uid, 0.0)) > now
        items.append((gens, uid, uname, sub_active))
    items.sort(reverse=True)
    lines = ["Top generators with 0 payments:"]
    for gens, uid, uname, sub_active in items[:topn]:
        flags = []
        if is_admin(uid, uname): flags.append("admin")
        if uid in FREE_USERS: flags.append("whitelist")
        if sub_active: flags.append("subscription")
        bal = ("∞" if is_free_user(uid, uname) else USER_CREDITS.get(uid, FREE_QUOTA))
        lines.append(f"{gens} · {uid} @" + (uname or "-") + f" · bal={bal} · {','.join(flags) or 'no flags'}")
    await safe_answer(m, "\n".join(lines))

@dp.message(Command("stats"))
async def cmd_stats(m: Message):
    if not is_admin(m.chat.id, getattr(m.from_user, "username", None)):
        return await safe_answer(m, L(m.chat.id)["admin_only"])
    uptime = int(time.time() - STATS["start_ts"]) if STATS.get("start_ts") else 0
    users = len(STATS_USERS)
    lines = [
        f"📊 Stats (uptime {uptime}s)",
        f"Users: {users}",
        f"Updates: {STATS['updates']}  Messages: {STATS['messages']}  Photos: {STATS['photos']}",
        f"Blocked: {STATS['blocked']}",
        f"Gen OK: {STATS['gens_ok']}  Gen FAIL: {STATS['gens_fail']}",
        f"Copy OK: {STATS['gens_copy_ok']}  Copy FAIL: {STATS['gens_copy_fail']}",
        f"MJ prompt OK: {STATS['mj_prompt_ok']}  FAIL: {STATS['mj_prompt_fail']}",
        f"Payments: {STATS['payments']}  Promo used: {STATS['promo_used']}  Referrals: {STATS['referrals']}",
        f"Published → channel: {STATS['published_channel']}  group: {STATS['published_group']}  auto: {STATS['auto_post']}",
    ]
    await safe_answer(m, "\n".join(lines))

@dp.message(Command("copy"))
async def cmd_copy(m: Message):
    USER_COPY_MODE.add(m.chat.id)
    USER_COPY_STYLE.pop(m.chat.id, None)
    USER_COPY_PROMPT.pop(m.chat.id, None)
    await safe_answer(m, L(m.chat.id)["copy_intro"])


@dp.message(Command("start"))
async def cmd_start(m: Message):
    if m.chat.id not in USER_LANG:
        USER_LANG[m.chat.id] = locale_to_lang(getattr(m.from_user, "language_code", None))

    parts = (m.text or "").split(maxsplit=1)
    if len(parts) > 1 and parts[1].startswith("ref_"):
        try:
            ref_id = int(parts[1][4:])
            invited_id = m.chat.id
            if ref_id != invited_id and invited_id not in REF_MAP:
                REF_MAP[invited_id] = ref_id
                ensure_user_credit(invited_id)
                USER_CREDITS[invited_id] += REF_BONUS_NEW
                _credits_save()
                REF_STATS.setdefault(ref_id, {"count": 0, "earned": 0})
                REF_STATS[ref_id]["count"] += 1
                REF_STATS[ref_id]["earned"] += REF_BONUS_REF
                _refs_save()
                USER_CREDITS[ref_id] = USER_CREDITS.get(ref_id, FREE_QUOTA) + REF_BONUS_REF
                _credits_save()
                stats_incr("referrals", 1)
                stats_incr("ref_bonus_ref", REF_BONUS_REF)
                stats_incr("ref_bonus_invited", REF_BONUS_NEW)
                # Bonus: every N invited → +1 day Premium (time subscription)
                try:
                    cnt = int(REF_STATS[ref_id]["count"])
                    if REF_PREMIUM_THRESHOLD > 0 and (cnt % REF_PREMIUM_THRESHOLD == 0):
                        now_ts = time.time()
                        cur_exp = float(SUBSCR_EXPIRY.get(ref_id, 0.0))
                        start_from = cur_exp if cur_exp > now_ts else now_ts
                        SUBSCR_EXPIRY[ref_id] = start_from + 24*3600
                        _subs_save()
                        # Notify referrer
                        exp_dt = time.strftime("%Y-%m-%d %H:%M", time.gmtime(int(SUBSCR_EXPIRY[ref_id])))
                        n_str = str(REF_PREMIUM_THRESHOLD)
                        note = {
                            "ru": f"🎉 {n_str} приглашённых! +1 день Premium активирован до {exp_dt} (UTC)",
                            "en": f"🎉 {n_str} invited! +1 day Premium activated until {exp_dt} (UTC)",
                            "ro": f"🎉 {n_str} invitați! +1 zi Premium activă până la {exp_dt} (UTC)",
                            "de": f"🎉 {n_str} Einladungen! +1 Tag Premium aktiv bis {exp_dt} (UTC)",
                        }.get(USER_LANG.get(ref_id, LANG_DEFAULT), f"+1 day Premium active until {exp_dt} (UTC)")
                        try:
                            await safe_send_text(ref_id, note)
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception:
            pass

    ensure_user_credit(m.chat.id)
    USER_SEEN_TEXT.discard(m.chat.id)
    if m.chat.id not in USER_ONBOARDED:
        # Show minimal welcome with a single Start button
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=L(m.chat.id)["onboard_btn"], callback_data="onboard_go")]])
        await safe_answer(m, L(m.chat.id)["onboard_welcome"], reply_markup=kb)
        return
    await safe_answer(m, L(m.chat.id)["start"], reply_markup=main_menu_inline(m.chat.id))
    STATS_USERS.add(m.chat.id)

@dp.message(Command("help"))
async def cmd_help(m: Message):
    text = L(m.chat.id)["help"].format(ref_new=REF_BONUS_NEW, ref_ref=REF_BONUS_REF)
    await safe_answer(m, text, reply_markup=kb_help(m.chat.id))

@dp.message(Command("lang"))
async def cmd_lang(m: Message):
    await safe_answer(m, L(m.chat.id)["choose_lang"], reply_markup=kb_lang_select(m.chat.id))

@dp.message(Command("ru"))
async def cmd_ru(m: Message):
    USER_LANG[m.chat.id] = "ru"; USER_SEEN_TEXT.add(m.chat.id)
    await safe_answer(m, L(m.chat.id)["lang_ru"], reply_markup=main_menu_inline(m.chat.id))

@dp.message(Command("en"))
async def cmd_en(m: Message):
    USER_LANG[m.chat.id] = "en"; USER_SEEN_TEXT.add(m.chat.id)
    await safe_answer(m, L(m.chat.id)["lang_en"], reply_markup=main_menu_inline(m.chat.id))

@dp.message(Command("ro"))
async def cmd_ro(m: Message):
    USER_LANG[m.chat.id] = "ro"; USER_SEEN_TEXT.add(m.chat.id)
    await safe_answer(m, L(m.chat.id)["lang_ro"], reply_markup=main_menu_inline(m.chat.id))

@dp.message(Command("de"))
async def cmd_de(m: Message):
    USER_LANG[m.chat.id] = "de"; USER_SEEN_TEXT.add(m.chat.id)
    msg = T.get("de", {}).get("lang_de") or "Language set: German"
    await safe_answer(m, msg, reply_markup=main_menu_inline(m.chat.id))

@dp.callback_query(F.data.startswith("set_lang_"))
async def cb_set_lang(c: CallbackQuery):
    code = c.data.split("set_lang_")[-1]
    if code not in ("ru","en","ro","de"):
        await safe_cb_answer(c)
        return
    USER_LANG[c.message.chat.id] = code
    USER_SEEN_TEXT.add(c.message.chat.id)
    key = {
        "ru": "lang_ru",
        "en": "lang_en",
        "ro": "lang_ro",
        "de": "lang_de",
    }[code]
    await safe_cb_answer(c)
    await c.message.answer(L(c.message.chat.id)[key], reply_markup=main_menu_inline(c.message.chat.id))

@dp.message(Command("presets"))
async def cmd_presets(m: Message):
    lang = USER_LANG.get(m.chat.id, LANG_DEFAULT)
    txt = {
        "ru": "🎛 Пресеты — выберите стиль",
        "en": "🎛 Presets — choose a style",
        "ro": "🎛 Preseturi — alege stilul",
        "de": "🎛 Presets — Stil wählen",
    }.get(lang, "🎛 Presets — choose a style")
    await safe_answer(m, txt, reply_markup=kb_presets_grid(m.chat.id))

@dp.message(Command("promo"))
async def cmd_promo(m: Message):
    lang = L(m.chat.id)
    parts = (m.text or "").strip().split(maxsplit=1)
    if len(parts) < 2:
        return await safe_answer(m, lang["promo_usage"])
    code = parts[1].strip().upper()
    promo = PROMO_CODES.get(code)
    if not promo or promo.get("uses", 0) <= 0:
        return await safe_answer(m, lang["promo_bad"])
    add = int(promo.get("add", 0))
    promo["uses"] = max(0, promo["uses"] - 1)
    USER_CREDITS[m.chat.id] = USER_CREDITS.get(m.chat.id, 0) + add
    _credits_save()
    await safe_answer(m, lang["promo_ok"].format(add=add, all=USER_CREDITS[m.chat.id]))
    stats_incr("promo_used", 1)

@dp.message(Command("balance"))
async def cmd_balance(m: Message):
    free = L(m.chat.id)["balance_free"] if is_free_user(m.chat.id, getattr(m.from_user, "username", None)) else ""
    n = USER_CREDITS.get(m.chat.id, FREE_QUOTA)
    await safe_answer(m, L(m.chat.id)["balance"].format(n=n, free=free))
    try:
        exp = SUBSCR_EXPIRY.get(m.chat.id)
        if exp and exp > time.time():
            exp_dt = time.strftime("%Y-%m-%d %H:%M", time.gmtime(int(exp)))
            note = {
                "ru": f"Активная подписка до {exp_dt} (UTC)",
                "en": f"Active subscription until {exp_dt} (UTC)",
                "ro": f"Abonament activ până la {exp_dt} (UTC)",
                "de": f"Abo aktiv bis {exp_dt} (UTC)",
            }.get(USER_LANG.get(m.chat.id, LANG_DEFAULT), f"Active subscription until {exp_dt} (UTC)")
            await safe_answer(m, note)
    except Exception:
        pass
    if n <= 0 and not is_free_user(m.chat.id, getattr(m.from_user, "username", None)):
        lang = L(m.chat.id)
        hint = lang.get("hint_refer_zero", "Invite a friend: /refer").format(ref_new=REF_BONUS_NEW, ref_ref=REF_BONUS_REF)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=lang.get("btn_invite", "👥 Invite"), callback_data="refer_open")],
            [InlineKeyboardButton(text="⭐ " + lang["btn_buy"], callback_data="buy_open")],
        ])
        await safe_answer(m, hint, reply_markup=kb)

@dp.message(Command("clear"))
async def cmd_clear(m: Message):
    USER_REFS.pop(m.chat.id, None)
    USER_LAST_OUTPUT.pop(m.chat.id, None)
    USER_LAST_PROMPT.pop(m.chat.id, None)
    USER_HISTORY.pop(m.chat.id, None)
    LAST_REF.pop(m.chat.id, None)
    LAST_PHOTO.pop(m.chat.id, None)
    USER_COPY_STYLE.pop(m.chat.id, None)
    USER_COPY_MODE.discard(m.chat.id)
    await safe_answer(m, L(m.chat.id)["cleared"])

@dp.message(Command("tos"))
async def cmd_tos(m: Message):
    await safe_answer(m, L(m.chat.id)["tos"])

@dp.message(Command("privacy"))
async def cmd_privacy(m: Message):
    await safe_answer(m, L(m.chat.id)["privacy"])

@dp.message(Command("gallery"))
async def cmd_gallery(m: Message):
    hist = USER_HISTORY.get(m.chat.id, [])
    if not hist:
        return await safe_answer(m, L(m.chat.id)["gallery_empty"])
    items = hist[-GALLERY_LIMIT:]
    if len(items) == 1:
        await safe_answer_photo(m, BufferedInputFile(items[0], filename="imodel_gallery.jpg"), caption="🖼 Галерея (1)")
    else:
        media = []
        for i, b in enumerate(items):
            if i == 0:
                media.append(InputMediaPhoto(type="photo", media=BufferedInputFile(b, filename=f"g{i}.jpg"), caption=f"🖼 Галерея ({len(items)})"))
            else:
                media.append(InputMediaPhoto(type="photo", media=BufferedInputFile(b, filename=f"g{i}.jpg")))
        try:
            await bot.send_media_group(chat_id=m.chat.id, media=media)
        except Exception:
            for i, b in enumerate(items):
                cap = "🖼 Галерея" if i == 0 else None
                await safe_answer_photo(m, BufferedInputFile(b, filename=f"g{i}.jpg"), caption=cap)

@dp.message(Command("refer"))
async def cmd_refer(m: Message):
    if not BOT_USERNAME_GLOBAL:
        return await safe_answer(m, L(m.chat.id)["ref_link_fail"])
    my_id = m.chat.id
    link = f"https://t.me/{BOT_USERNAME_GLOBAL}?start=ref_{my_id}"
    st = REF_STATS.get(my_id, {"count": 0, "earned": 0})
    # Progress to next Premium day
    cnt = int(st.get("count", 0))
    thr = max(1, int(REF_PREMIUM_THRESHOLD))
    rem = (thr - (cnt % thr)) if (cnt % thr) != 0 else thr
    try:
        lng = USER_LANG.get(my_id, LANG_DEFAULT)
        if lng.startswith("ru"):
            title = "👥 Пригласи друга — получи +1 генерацию\n15 приглашённых = 1 день Premium"
            copied = "📋 Скопировать"
            openb = "🔗 Открыть"
            prog = f"До следующего Premium дня: ещё {rem}"
        elif lng.startswith("ro"):
            title = "👥 Invită un prieten — primești +1 generare\n15 invitați = 1 zi Premium"
            copied = "📋 Copiază"
            openb = "🔗 Deschide"
            prog = f"Până la următoarea zi Premium: încă {rem}"
        elif lng.startswith("de"):
            title = "👥 Lade einen Freund ein — +1 Generation\n15 Einladungen = 1 Tag Premium"
            copied = "📋 Kopieren"
            openb = "🔗 Öffnen"
            prog = f"Bis zum nächsten Premium‑Tag: noch {rem}"
        else:
            title = "👥 Invite a friend — get +1 generation\n15 invited = 1 day Premium"
            copied = "📋 Copy"
            openb = "🔗 Open"
            prog = f"To next Premium day: {rem} more"
    except Exception:
        title = "Invite friends and earn rewards"
        copied = "Copy"
        openb = "Open"
        prog = ""

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=openb, url=link)],
        [InlineKeyboardButton(text=copied, callback_data=f"ref_copy_{my_id}")],
    ])
    text = (
        f"{title}\n\n"
        f"🔗 {link}\n"
        f"👥 Invited: {int(st.get('count',0))} · 🎁 Earned: {int(st.get('earned',0))}\n"
        f"{prog}"
    )
    await safe_answer(m, text, reply_markup=kb)

# ======= INLINE callbacks =======
@dp.callback_query(F.data == "help_open")
async def cb_help(c: CallbackQuery):
    await safe_cb_answer(c)
    text = L(c.message.chat.id)["help"].format(ref_new=REF_BONUS_NEW, ref_ref=REF_BONUS_REF)
    await c.message.answer(text, reply_markup=kb_help(c.message.chat.id))

@dp.callback_query(F.data == "presets_open")
async def cb_presets(c: CallbackQuery):
    await safe_cb_answer(c)
    chat_id = c.message.chat.id
    lang = USER_LANG.get(chat_id, LANG_DEFAULT)
    txt = {
        "ru": "🎛 Пресеты — выберите стиль",
        "en": "🎛 Presets — choose a style",
        "ro": "🎛 Preseturi — alege stilul",
        "de": "🎛 Presets — Stil wählen",
    }.get(lang, "🎛 Presets — choose a style")
    await c.message.answer(txt, reply_markup=kb_presets_grid(chat_id))

@dp.callback_query(F.data == "back_main")
async def cb_back_main(c: CallbackQuery):
    await safe_cb_answer(c)
    chat_id = c.message.chat.id
    await c.message.answer(L(chat_id)["start"], reply_markup=main_menu_inline(chat_id))

@dp.callback_query(F.data == "refer_open")
async def cb_refer_open(c: CallbackQuery):
    await safe_cb_answer(c)
    await cmd_refer(c.message)

@dp.callback_query(F.data.startswith("ref_copy_"))
async def cb_ref_copy(c: CallbackQuery):
    try:
        uid = c.message.chat.id
        if not BOT_USERNAME_GLOBAL:
            return await safe_cb_answer(c)
        link = f"https://t.me/{BOT_USERNAME_GLOBAL}?start=ref_{uid}"
        await safe_cb_answer(c, "Ссылка скопирована в сообщение")
        await c.message.answer(link)
    except Exception:
        pass

@dp.callback_query(F.data.startswith("preset_"))
async def cb_preset_pick(c: CallbackQuery):
    await safe_cb_answer(c)
    chat_id = c.message.chat.id
    try:
        idx = int(c.data.split("preset_")[-1])
    except Exception:
        return
    if idx < 0 or idx >= len(PRESETS):
        return
    preset = PRESETS[idx]
    refs = USER_REFS.get(chat_id, [])
    # If no selfie yet — remember preset and prompt for a selfie
    if not refs:
        USER_PRESET_PENDING[chat_id] = idx
        lang = USER_LANG.get(chat_id, LANG_DEFAULT)
        txt = {
            "ru": f"✅ Выбрано: {preset.label_ru}\nПришлите селфи — сразу сгенерирую.",
            "en": f"✅ Selected: {preset.label_en}\nSend a selfie — I will generate immediately.",
            "ro": f"✅ Selectat: {preset.label_en}\nTrimite un selfie — generez imediat.",
            "de": f"✅ Ausgewählt: {preset.label_en}\nSende ein Selfie — ich generiere sofort.",
        }.get(lang, f"Selected: {preset.label_en}. Send a selfie.")
        await c.message.answer(txt)
        return
    # Have a reference → generate now
    if not has_credit(chat_id, getattr(c.from_user, "username", None)):
        return await c.message.answer(L(chat_id)["unlock"], reply_markup=kb_invite_buy(chat_id))
    msg = await c.message.answer(L(chat_id)["gen"])
    ref = refs[-1]
    seed_int = ((hash(chat_id) % 10_000_000) + idx)
    result = await (generate_image_with_preview_async(
        c.message,
        ref, preset.prompt, lang=USER_LANG.get(chat_id, LANG_DEFAULT),
        seed=seed_int) if PREVIEW_FIRST else generate_image_from_bytes_async(
        ref, preset.prompt, lang=USER_LANG.get(chat_id, LANG_DEFAULT),
        seed=seed_int))
    if not result:
        stats_incr("gens_fail", 1)
        _uadd(chat_id, "gens_fail", 1)
        return await safe_edit_text(msg, L(chat_id)["fail"])
    if not is_free_user(chat_id, getattr(c.from_user, "username", None)):
        USER_CREDITS[chat_id] -= 1
        _credits_save()
        maybe_send_limit_progress(chat_id)
    USER_LAST_OUTPUT[chat_id] = result
    USER_LAST_PROMPT[chat_id] = preset.prompt
    LAST_PHOTO[chat_id] = result
    stats_incr("gens_ok", 1)
    _uadd(chat_id, "gens_ok", 1)
    await maybe_trigger_after3(chat_id)
    hist = USER_HISTORY.setdefault(chat_id, [])
    hist.append(result)
    if len(hist) > GALLERY_LIMIT:
        del hist[:-GALLERY_LIMIT]
    await msg.delete()
    cap = {
        "ru": f"✅ {preset.label_ru}",
        "en": f"✅ {preset.label_en}",
        "ro": "✅ Preset",
        "de": "✅ Preset",
    }.get(USER_LANG.get(chat_id, LANG_DEFAULT), "✅ Preset")
    await safe_answer_photo(
        c.message,
        BufferedInputFile(result, filename="imodel_result.jpg"),
        caption=cap,
        reply_markup=kb_actions(chat_id),
    )

@dp.callback_query(F.data == "promo_open")
async def cb_promo(c: CallbackQuery):
    await safe_cb_answer(c)
    await c.message.answer(L(c.message.chat.id)["promo_usage"])

@dp.callback_query(F.data == "lang_open")
async def cb_lang(c: CallbackQuery):
    await safe_cb_answer(c)
    await c.message.answer(L(c.message.chat.id)["choose_lang"], reply_markup=kb_lang_select(c.message.chat.id))

@dp.callback_query(F.data == "pricing_open")
async def cb_pricing(c: CallbackQuery):
    await safe_cb_answer(c)
    await c.message.answer(L(c.message.chat.id)["pricing"])
    await cmd_buy(c.message)
    n = USER_CREDITS.get(c.message.chat.id, FREE_QUOTA)
    if n <= 0 and not is_free_user(c.message.chat.id, getattr(c.from_user, "username", None)):
        lang = L(c.message.chat.id)
        hint = lang.get("hint_refer_zero", "Invite a friend: /refer").format(ref_new=REF_BONUS_NEW, ref_ref=REF_BONUS_REF)
        await c.message.answer(hint, reply_markup=kb_invite_buy(c.message.chat.id))

@dp.callback_query(F.data == "onboard_go")
async def cb_onboard_go(c: CallbackQuery):
    chat_id = c.message.chat.id
    USER_ONBOARDED.add(chat_id)
    await safe_cb_answer(c)
    await c.message.answer(L(chat_id)["start"], reply_markup=main_menu_inline(chat_id))


@dp.callback_query(F.data == "balance")
async def cb_balance(c: CallbackQuery):
    chat_id = c.message.chat.id
    await safe_cb_answer(c)
    n = USER_CREDITS.get(chat_id, FREE_QUOTA)
    free_note = L(chat_id)["balance_free"] if is_free_user(chat_id, getattr(c.from_user, "username", None)) else ""
    await c.message.answer(L(chat_id)["balance"].format(n=n, free=free_note))

@dp.callback_query(F.data == "buy_open")
async def cb_buy_open(c: CallbackQuery):
    await safe_cb_answer(c)
    await cmd_buy(c.message)

@dp.callback_query(F.data == "copy_open")
async def cb_copy_open(c: CallbackQuery):
    USER_COPY_MODE.add(c.message.chat.id)
    USER_COPY_STYLE.pop(c.message.chat.id, None)
    await safe_cb_answer(c)
    await c.message.answer(L(c.message.chat.id)["copy_intro"])

@dp.callback_query(F.data == "pub_yes")
async def cb_pub_yes(c: CallbackQuery):
    if not GALLERY_CHANNEL_ID:
        await safe_cb_answer(c)
        return await c.message.answer("Канал не настроен.")
    before = LAST_REF.get(c.message.chat.id)
    after  = LAST_PHOTO.get(c.message.chat.id)
    if not after:
        await safe_cb_answer(c)
        return await c.message.answer("Нет результата для публикации.")
    imgs = []
    if before:
        imgs.append(before)
    imgs.append(after)
    if len(imgs) == 1:
        try:
            await bot.send_photo(
                chat_id=GALLERY_CHANNEL_ID,
                photo=BufferedInputFile(imgs[0], filename="after.jpg"),
                caption=generate_instacaption(USER_LAST_PROMPT.get(c.message.chat.id, ""), USER_LANG.get(c.message.chat.id, LANG_DEFAULT))
            )
        except Exception as e:
            print("channel single photo error:", str(e)[:160])
    else:
        media = []
        for i, b in enumerate(imgs):
            cap = "До / После ✨" if i == 1 else None
            if i == 0:
                media.append(InputMediaPhoto(type="photo", media=BufferedInputFile(b, filename="before.jpg"), caption="До"))
            else:
                media.append(InputMediaPhoto(type="photo", media=BufferedInputFile(b, filename="after.jpg"), caption=cap))
        try:
            await bot.send_media_group(chat_id=GALLERY_CHANNEL_ID, media=media)
        except Exception as e:
            print("channel media group error:", str(e)[:160])
    stats_incr("published_channel", 1)
    _uadd(c.message.chat.id, "published", 1)
    await safe_cb_answer(c, "Опубликовано")

@dp.callback_query(F.data == "pub_group")
async def cb_pub_group(c: CallbackQuery):
    if not PUBLISH_GROUP_ID:
        await safe_cb_answer(c)
        return await c.message.answer("Группа не настроена.")
    before = LAST_REF.get(c.message.chat.id)
    after  = LAST_PHOTO.get(c.message.chat.id)
    if not after:
        await safe_cb_answer(c)
        return await c.message.answer("Нет результата для публикации.")
    imgs = []
    if before:
        imgs.append(before)
    imgs.append(after)
    if len(imgs) == 1:
        try:
            await bot.send_photo(
                chat_id=PUBLISH_GROUP_ID,
                photo=BufferedInputFile(imgs[0], filename="after.jpg"),
                caption=generate_instacaption(USER_LAST_PROMPT.get(c.message.chat.id, ""), USER_LANG.get(c.message.chat.id, LANG_DEFAULT))
            )
        except Exception as e:
            print("group single photo error:", str(e)[:160])
    else:
        media = []
        for i, b in enumerate(imgs):
            cap = "До / После ✨" if i == 1 else None
            if i == 0:
                media.append(InputMediaPhoto(type="photo", media=BufferedInputFile(b, filename="before.jpg"), caption="До"))
            else:
                media.append(InputMediaPhoto(type="photo", media=BufferedInputFile(b, filename="after.jpg"), caption=cap))
        try:
            await bot.send_media_group(chat_id=PUBLISH_GROUP_ID, media=media)
        except Exception as e:
            print("group media group error:", str(e)[:160])
    stats_incr("published_group", 1)
    _uadd(c.message.chat.id, "published", 1)
    await safe_cb_answer(c, "Опубликовано в группе")

# ===================== FLOW: PHOTO ====================
@dp.message(F.photo)
async def on_photo(m: Message):
    if m.chat.id not in USER_LANG:
        USER_LANG[m.chat.id] = locale_to_lang(getattr(m.from_user, "language_code", None))

    f = await bot.get_file(m.photo[-1].file_id)
    b = await bot.download_file(f.file_path)
    img_bytes = b.read()
    stats_incr("photos", 1)
    STATS_USERS.add(m.chat.id)
    _touch_user(m.chat.id, getattr(m.from_user, "username", None))
    _uadd(m.chat.id, "photos", 1)

    # ----- Copy Mode -----
    if m.chat.id in USER_COPY_MODE:
        if m.chat.id not in USER_COPY_STYLE:
            # это style-reference
            USER_COPY_STYLE[m.chat.id] = img_bytes
            # Никаких предпросмотров промпта — просто просим селфи
            await safe_answer(m, L(m.chat.id)["copy_style_ok"])
            return
        else:
            # это селфи → генерим 1:1 сцену
            style_bytes = USER_COPY_STYLE.get(m.chat.id)
            if not style_bytes:
                return await safe_answer(m, L(m.chat.id)["copy_need_style"])

            # 1) Берём уже подготовленный/отредактированный пользователем промпт, либо пробуем сгенерировать
            scene_spec = USER_COPY_PROMPT.get(m.chat.id)
            if not scene_spec:
                scene_spec = craft_mj_prompt_from_image(style_bytes)
            if not scene_spec:
                scene_spec = craft_scene_spec_from_image(style_bytes) or "person, same scene."
            USER_REFS.setdefault(m.chat.id, [])
            USER_REFS[m.chat.id] = (USER_REFS[m.chat.id] + [img_bytes])[-4:]
            LAST_REF[m.chat.id] = img_bytes  # «до»

            ensure_user_credit(m.chat.id)
            if not has_credit(m.chat.id, getattr(m.from_user, "username", None)):
                return await safe_answer(m, L(m.chat.id)["unlock"], reply_markup=kb_invite_buy(m.chat.id))

            wait = await safe_answer(m, L(m.chat.id)["gen"])
            seed = (hashlib.md5(style_bytes).hexdigest())
            seed_int = int(seed[:8], 16)

            # строгий режим: жёсткая сцена + identity lock + negative
            # 2) Генерим по selfie + текстовому промпту (БЕЗ передачи style-image в модель)
            final_bytes = await (generate_image_with_preview_async(
                img_bytes,
                scene_spec,
                lang=USER_LANG.get(m.chat.id, LANG_DEFAULT),
                seed=seed_int,
                strict=True,
                style_bytes=None,
                lock_scene=False,
            ) if PREVIEW_FIRST else generate_image_from_bytes_async(
                img_bytes,
                scene_spec,
                lang=USER_LANG.get(m.chat.id, LANG_DEFAULT),
                seed=seed_int,
                strict=True,
                style_bytes=None,
                lock_scene=False,
            ))
            if not final_bytes:
                # вторая попытка: ещё жёстче
                final_bytes = await (generate_image_with_preview_async(
                    img_bytes,
                    scene_spec + ". Keep face absolutely unchanged, do not beautify, do not reshape.",
                    lang=USER_LANG.get(m.chat.id, LANG_DEFAULT),
                    seed=seed_int,
                    strict=True,
                    style_bytes=None,
                    lock_scene=False,
                ) if PREVIEW_FIRST else generate_image_from_bytes_async(
                    img_bytes,
                    scene_spec + ". Keep face absolutely unchanged, do not beautify, do not reshape.",
                    lang=USER_LANG.get(m.chat.id, LANG_DEFAULT),
                    seed=seed_int,
                    strict=True,
                    style_bytes=None,
                    lock_scene=False,
                ))
                if not final_bytes:
                    if wait: await safe_edit_text(wait, L(m.chat.id)["fail"])
                    stats_incr("gens_copy_fail", 1)
                    _uadd(m.chat.id, "gens_copy_fail", 1)
                    return

            if not is_free_user(m.chat.id, getattr(m.from_user, "username", None)):
                USER_CREDITS[m.chat.id] -= 1
                _credits_save()
                maybe_send_limit_progress(m.chat.id)
            USER_LAST_OUTPUT[m.chat.id] = final_bytes
            USER_LAST_PROMPT[m.chat.id] = scene_spec
            LAST_PHOTO[m.chat.id] = final_bytes
            stats_incr("gens_copy_ok", 1)
            _uadd(m.chat.id, "gens_copy_ok", 1)
            await maybe_trigger_after3(m.chat.id)

            # история
            hist = USER_HISTORY.setdefault(m.chat.id, [])
            hist.append(final_bytes)
            if len(hist) > GALLERY_LIMIT:
                del hist[:-GALLERY_LIMIT]

            if wait: await wait.delete()
            await safe_answer_photo(
                m,
                BufferedInputFile(final_bytes, filename="imodel_result.jpg"),
                caption=L(m.chat.id)["copy_done"],
                reply_markup=kb_actions(m.chat.id),
            )
            await maybe_send_referral_hint(m.chat.id)

            # выключаем режим
            USER_COPY_STYLE.pop(m.chat.id, None)
            USER_COPY_MODE.discard(m.chat.id)

            # авто-пост
            if AUTO_POST and GALLERY_CHANNEL_ID:
                try:
                    await post_before_after_to_channel(m.chat.id)
                except Exception as e:
                    print("AUTO_POST error:", str(e)[:160])
            return

    # ----- Обычный режим -----
    USER_REFS.setdefault(m.chat.id, [])
    USER_REFS[m.chat.id] = (USER_REFS[m.chat.id] + [img_bytes])[-4:]
    LAST_REF[m.chat.id] = img_bytes

    caption = (m.caption or "").strip()
    if not caption:
        # If a preset was chosen earlier, auto-generate using it
        if m.chat.id in USER_PRESET_PENDING:
            idx = USER_PRESET_PENDING.pop(m.chat.id)
            if 0 <= idx < len(PRESETS):
                preset = PRESETS[idx]
                if not has_credit(m.chat.id, getattr(m.from_user, "username", None)):
                    return await safe_answer(m, L(m.chat.id)["unlock"], reply_markup=kb_invite_buy(m.chat.id))
                wait = await safe_answer(m, L(m.chat.id)["gen"])
                seed_int = ((hash(m.chat.id) % 10_000_000) + idx)
                final_bytes = await (generate_image_with_preview_async(
                    img_bytes, preset.prompt, lang=USER_LANG.get(m.chat.id, LANG_DEFAULT),
                    seed=seed_int) if PREVIEW_FIRST else generate_image_from_bytes_async(
                    img_bytes, preset.prompt, lang=USER_LANG.get(m.chat.id, LANG_DEFAULT),
                    seed=seed_int))
                if not final_bytes:
                    if wait: await safe_edit_text(wait, L(m.chat.id)["fail"])
                    stats_incr("gens_fail", 1)
                    _uadd(m.chat.id, "gens_fail", 1)
                    return
                if not is_free_user(m.chat.id, getattr(m.from_user, "username", None)):
                    USER_CREDITS[m.chat.id] -= 1
                    _credits_save()
                    maybe_send_limit_progress(m.chat.id)
                USER_LAST_OUTPUT[m.chat.id] = final_bytes
                USER_LAST_PROMPT[m.chat.id] = preset.prompt
                LAST_PHOTO[m.chat.id] = final_bytes
                stats_incr("gens_ok", 1)
                _uadd(m.chat.id, "gens_ok", 1)
                await maybe_trigger_after3(m.chat.id)
                hist = USER_HISTORY.setdefault(m.chat.id, [])
                hist.append(final_bytes)
                if len(hist) > GALLERY_LIMIT:
                    del hist[:-GALLERY_LIMIT]
                if wait: await wait.delete()
                cap = {
                    "ru": f"✅ {preset.label_ru}",
                    "en": f"✅ {preset.label_en}",
                }.get(USER_LANG.get(m.chat.id, LANG_DEFAULT), "✅ Preset")
                await safe_answer_photo(
                    m,
                    BufferedInputFile(final_bytes, filename="imodel_result.jpg"),
                    caption=cap,
                    reply_markup=kb_actions(m.chat.id),
                )
                await maybe_send_referral_hint(m.chat.id)
                if AUTO_POST and GALLERY_CHANNEL_ID:
                    try:
                        await post_before_after_to_channel(m.chat.id)
                    except Exception as e:
                        print("AUTO_POST error:", str(e)[:160])
                return
        return await safe_answer(m, L(m.chat.id)["photo_ok"])
    if blocked(caption):
        stats_incr("blocked", 1)
        return await safe_answer(m, L(m.chat.id)["blocked"])

    ensure_user_credit(m.chat.id)
    if not has_credit(m.chat.id, getattr(m.from_user, "username", None)):
        return await safe_answer(m, L(m.chat.id)["unlock"], reply_markup=kb_invite_buy(m.chat.id))

    wait = await safe_answer(m, L(m.chat.id)["gen"])
    seed_int = (hash(m.chat.id) % 10_000_000)
    final_bytes = await (generate_image_with_preview_async(
        img_bytes, caption, lang=USER_LANG.get(m.chat.id, LANG_DEFAULT),
        seed=seed_int) if PREVIEW_FIRST else generate_image_from_bytes_async(
        img_bytes, caption, lang=USER_LANG.get(m.chat.id, LANG_DEFAULT),
        seed=seed_int))
    if not final_bytes:
        if wait: await safe_edit_text(wait, L(m.chat.id)["fail"])
        stats_incr("gens_fail", 1)
        _uadd(m.chat.id, "gens_fail", 1)
        return

    if not is_free_user(m.chat.id, getattr(m.from_user, "username", None)):
        USER_CREDITS[m.chat.id] -= 1
        _credits_save()
        maybe_send_limit_progress(m.chat.id)
    USER_LAST_OUTPUT[m.chat.id] = final_bytes
    USER_LAST_PROMPT[m.chat.id] = caption
    LAST_PHOTO[m.chat.id] = final_bytes
    stats_incr("gens_ok", 1)
    _uadd(m.chat.id, "gens_ok", 1)
    await maybe_trigger_after3(m.chat.id)

    hist = USER_HISTORY.setdefault(m.chat.id, [])
    hist.append(final_bytes)
    if len(hist) > GALLERY_LIMIT:
        del hist[:-GALLERY_LIMIT]

    if wait: await wait.delete()
    await safe_answer_photo(
        m,
        BufferedInputFile(final_bytes, filename="imodel_result.jpg"),
        caption="✅",
        reply_markup=kb_actions(m.chat.id),
    )
    await maybe_send_referral_hint(m.chat.id)

    if AUTO_POST and GALLERY_CHANNEL_ID:
        try:
            await post_before_after_to_channel(m.chat.id)
        except Exception as e:
            print("AUTO_POST error:", str(e)[:160])

# ===================== FLOW: TEXT =====================
@dp.message(F.text & ~F.text.startswith("/"))
async def on_prompt(m: Message):
    # Если включён Copy Mode и пришёл текст — трактуем как ручное редактирование промпта для копирования сцены
    if m.chat.id in USER_COPY_MODE:
        USER_COPY_PROMPT[m.chat.id] = m.text.strip()
        await safe_answer(m, "Промпт обновлён. Теперь пришлите селфи.")
        return
    stats_incr("messages", 1)
    _touch_user(m.chat.id, getattr(m.from_user, "username", None))
    _uadd(m.chat.id, "messages", 1)
    text = m.text.strip()
    if m.chat.id not in USER_LANG:
        USER_LANG[m.chat.id] = locale_to_lang(getattr(m.from_user, "language_code", None))
    if m.chat.id not in USER_SEEN_TEXT:
        USER_SEEN_TEXT.add(m.chat.id)
        if USER_LANG.get(m.chat.id, LANG_DEFAULT) == LANG_DEFAULT:
            USER_LANG[m.chat.id] = detect_lang(text)

    if blocked(text):
        stats_incr("blocked", 1)
        _uadd(m.chat.id, "blocked", 1)
        return await safe_answer(m, L(m.chat.id)["blocked"])

    refs = USER_REFS.get(m.chat.id, [])
    if not refs:
        return await safe_answer(m, L(m.chat.id)["need_photo"])

    ensure_user_credit(m.chat.id)
    if not has_credit(m.chat.id, getattr(m.from_user, "username", None)):
        return await safe_answer(m, L(m.chat.id)["unlock"], reply_markup=kb_invite_buy(m.chat.id))

    wait = await safe_answer(m, L(m.chat.id)["gen"])
    ref = refs[-1]
    seed_int = (hash(m.chat.id) % 10_000_000)
    final_bytes = await (generate_image_with_preview_async(
        ref, text, lang=USER_LANG.get(m.chat.id, LANG_DEFAULT),
        seed=seed_int) if PREVIEW_FIRST else generate_image_from_bytes_async(
        ref, text, lang=USER_LANG.get(m.chat.id, LANG_DEFAULT),
        seed=seed_int))
    if not final_bytes:
        if wait: await safe_edit_text(wait, L(m.chat.id)["fail"])
        stats_incr("gens_fail", 1)
        _uadd(m.chat.id, "gens_fail", 1)
        return

    if not is_free_user(m.chat.id, getattr(m.from_user, "username", None)):
        USER_CREDITS[m.chat.id] -= 1
        _credits_save()
    USER_LAST_OUTPUT[m.chat.id] = final_bytes
    USER_LAST_PROMPT[m.chat.id] = text
    LAST_PHOTO[m.chat.id] = final_bytes
    stats_incr("gens_ok", 1)
    _uadd(m.chat.id, "gens_ok", 1)

    hist = USER_HISTORY.setdefault(m.chat.id, [])
    hist.append(final_bytes)
    if len(hist) > GALLERY_LIMIT:
        del hist[:-GALLERY_LIMIT]

    if wait: await wait.delete()
    await safe_answer_photo(
        m,
        BufferedInputFile(final_bytes, filename="imodel_result.jpg"),
        caption="✅",
        reply_markup=kb_actions(m.chat.id),
    )

    if AUTO_POST and GALLERY_CHANNEL_ID:
        try:
            await post_before_after_to_channel(m.chat.id)
        except Exception as e:
            print("AUTO_POST error:", str(e)[:160])

# ===================== INLINE BUTTONS =================
@dp.callback_query(F.data == "more")
async def cb_more(c: CallbackQuery):
    chat_id = c.message.chat.id
    refs = USER_REFS.get(chat_id, [])
    base_prompt = USER_LAST_PROMPT.get(chat_id)
    if not refs or not base_prompt:
        await safe_cb_answer(c)
        return await c.message.answer(L(chat_id)["need_photo"])

    ensure_user_credit(chat_id)
    if not has_credit(chat_id, getattr(c.from_user, "username", None)):
        await safe_cb_answer(c)
        return await c.message.answer(L(chat_id)["unlock"], reply_markup=kb_invite_buy(chat_id))

    await safe_cb_answer(c)
    msg = await c.message.answer(L(chat_id)["gen"])
    ref = refs[-1]
    # тот же промпт, seed + 1 (минимальная вариативность, лицо стабильное)
    seed_int = ((hash(chat_id) % 10_000_000) + 1)
    result = await (generate_image_with_preview_async(
        c.message,
        ref, base_prompt, lang=USER_LANG.get(chat_id, LANG_DEFAULT),
        seed=seed_int) if PREVIEW_FIRST else generate_image_from_bytes_async(
        ref, base_prompt, lang=USER_LANG.get(chat_id, LANG_DEFAULT),
        seed=seed_int))
    if not result:
        STATS["gens_fail"] += 1
        _uadd(chat_id, "gens_fail", 1)
        return await safe_edit_text(msg, L(chat_id)["fail"])

    if not is_free_user(chat_id, getattr(c.from_user, "username", None)):
        USER_CREDITS[chat_id] -= 1
        _credits_save()
    USER_LAST_OUTPUT[chat_id] = result
    USER_LAST_PROMPT[chat_id] = base_prompt
    LAST_PHOTO[chat_id] = result
    STATS["gens_ok"] += 1
    _uadd(chat_id, "gens_ok", 1)
    await maybe_trigger_after3(chat_id)

    hist = USER_HISTORY.setdefault(chat_id, [])
    hist.append(result)
    if len(hist) > GALLERY_LIMIT:
        del hist[:-GALLERY_LIMIT]

    await msg.delete()
    await safe_answer_photo(
        c.message,
        BufferedInputFile(result, filename="imodel_result.jpg"),
        caption="✅",
        reply_markup=kb_actions(chat_id),
    )
    await maybe_send_referral_hint(chat_id)


async def ensure_webhook():
    """Idempotent webhook setup with flood-control handling."""
    try:
        info = await bot.get_webhook_info()
        if info and getattr(info, "url", "") == WEBHOOK_URL:
            # Already set to the same URL — avoid hitting flood limits
            print("Webhook already set → skip set_webhook()")
            return
    except Exception as e:
        print("get_webhook_info error:", str(e)[:160])

    backoff = [0, 1, 2, 5]
    for i, delay in enumerate(backoff, start=1):
        if delay:
            await asyncio.sleep(delay)
        try:
            await bot.set_webhook(
                url=WEBHOOK_URL,
                drop_pending_updates=False,
                secret_token=WEBHOOK_SECRET,
            )
            print("Webhook set OK")
            return
        except TelegramRetryAfter as e:
            # Respect Telegram flood-control
            wait_for = getattr(e, "retry_after", 1) or 1
            print(f"TelegramRetryAfter: wait {wait_for}s")
            await asyncio.sleep(wait_for + 1)
        except Exception as e:
            print(f"set_webhook attempt {i} failed:", str(e)[:200])
            if i == len(backoff):
                raise
    
# ===================== WEBHOOK ========================
@app.on_event("startup")
async def on_startup():
    print(f"=== {APP_VERSION} ===")
    # Load persisted stats/users
    try:
        stats_load()
        print("Loaded persisted stats.")
    except Exception as e:
        print("Stats load error:", str(e)[:160])
    print("ADMINS (IDs):", ADMIN_IDS)
    print("ADMINS (usernames):", ADMIN_USERNAMES)
    if GALLERY_CHANNEL_ID:
        print("Gallery channel:", GALLERY_CHANNEL_ID, "AUTO_POST:", AUTO_POST)
    if PUBLISH_GROUP_ID:
        print("Publish group:", PUBLISH_GROUP_ID)
    print("Models → main:", NANOBANANA_MODEL or "<unset>", "| upscaler:", ESRGAN_MODEL or "<unset>")

    me = await bot.get_me()
    global BOT_USERNAME_GLOBAL
    BOT_USERNAME_GLOBAL = me.username

    if BOT_TOKEN and WEBHOOK_BASE and not DISABLE_WEBHOOK:
        await ensure_webhook()
        print("✅ Вебхук установлен")
    elif DISABLE_WEBHOOK:
        print("⚠️ Вебхук отключён (DISABLE_WEBHOOK=1)")
    else:
        print("⚠️ Нет BOT_TOKEN или WEBHOOK_BASE")

    await bot.set_my_commands(
        commands=[
            BotCommand(command="start",   description="Начать"),
            BotCommand(command="buy",     description="Купить звёздами"),
            BotCommand(command="promo",   description="Промокод"),
            BotCommand(command="balance", description="Баланс"),
            BotCommand(command="presets", description="Идеи описаний"),
            BotCommand(command="lang",    description="Сменить язык"),
            BotCommand(command="gallery", description="Моя галерея"),
            BotCommand(command="refer",   description="Реферальная ссылка"),
            BotCommand(command="pricing", description="Тарифы"),
            BotCommand(command="copy",    description="Скопировать фото"),
            BotCommand(command="help",    description="Помощь"),
            BotCommand(command="clear",   description="Очистить память"),
            BotCommand(command="version", description="Версия"),
        ],
        scope=BotCommandScopeDefault()
    )
    # Background nudges
    try:
        if NUDGE_ENABLED:
            asyncio.create_task(nudge_loop())
            print("Nudge loop started")
    except Exception as e:
        print("Nudge loop error on startup:", str(e)[:160])
@app.on_event("shutdown")
async def on_shutdown():
    print("🛑 Shutting down...")
    try:
        if not DISABLE_WEBHOOK:
            await bot.delete_webhook()
    finally:
        await bot.session.close()
    if not DISABLE_WEBHOOK:
        print("✅ Webhook removed")

@app.post("/")
async def telegram_webhook(request: Request):
    hdr = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    q = request.query_params.get("secret")
    if not ((hdr and hdr == WEBHOOK_SECRET) or (q and q == WEBHOOK_SECRET)):
        return JSONResponse({"status": "forbidden"}, status_code=403)
    data = await request.json()
    try:
        stats_incr("updates", 1)
        t = data.get("message", {}) or data.get("edited_message", {}) or data.get("callback_query", {})
        chat = (t.get("chat") or t.get("message", {}).get("chat") or {})
        print("[webhook] update received:", {
            "keys": list(data.keys())[:3],
            "chat_id": chat.get("id"),
            "from": (t.get("from") or {}).get("id"),
            "type": t.get("text", "<media>") if isinstance(t, dict) else "<unknown>",
        })
        user_obj = (t.get("from") or {})
        uid = user_obj.get("id")
        uname = user_obj.get("username")
        if isinstance(uid, int):
            STATS_USERS.add(uid)
            _touch_user(uid, uname)
    except Exception:
        pass
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}

@app.get("/")
async def root_health():
    return {"ok": True, "version": APP_VERSION}

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.get("/thanks")
async def thanks():
    return HTMLResponse("<html><body><h3>✅ Payment successful</h3><p>You can return to Telegram now.</p></body></html>")

@app.get("/cancel")
async def cancel():
    return HTMLResponse("<html><body><h3>Payment canceled</h3><p>You can try again from the bot.</p></body></html>")

@app.get("/metrics")
async def http_metrics(request: Request):
    if (not METRICS_SECRET) or (request.query_params.get("secret") != METRICS_SECRET):
        return JSONResponse({"status": "forbidden"}, status_code=403)
    resp = dict(STATS)
    # Persisted users count (survives restarts)
    resp["users"] = len(STATS_USERS_INFO)
    resp["uptime_sec"] = int(time.time() - STATS["start_ts"]) if STATS.get("start_ts") else 0
    return resp

@app.post("/stripe/webhook")
async def stripe_webhook(request: Request):
    if not STRIPE_ENABLED or stripe is None or not STRIPE_WEBHOOK_SECRET:
        return JSONResponse({"status": "disabled"}, status_code=200)
    try:
        payload = await request.body()
        sig = request.headers.get("Stripe-Signature")
        event = stripe.Webhook.construct_event(payload, sig, STRIPE_WEBHOOK_SECRET)
    except Exception as e:
        return JSONResponse({"status": "bad signature", "error": str(e)[:160]}, status_code=400)

    try:
        et = event.get("type")
        data = event.get("data", {}).get("object", {})
        if et == "checkout.session.completed":
            paid = str(data.get("payment_status", "")).lower() == "paid"
            meta = data.get("metadata", {}) or {}
            uid = int(meta.get("uid") or (data.get("client_reference_id") or 0))
            pack = str(meta.get("pack") or "")
            add = _stripe_pack_add(pack)
            if paid and uid and add > 0:
                ensure_user_credit(uid)
                USER_CREDITS[uid] = USER_CREDITS.get(uid, 0) + add
                _credits_save()
                stats_incr("payments", 1)
                _uadd(uid, "payments", 1)
                # Notify user
                try:
                    lang = L(uid)
                    await safe_send_text(uid, lang["bought"].format(add=add, all=USER_CREDITS.get(uid, 0)))
                except Exception:
                    pass
        return {"ok": True}
    except Exception as e:
        return JSONResponse({"status": "error", "error": str(e)[:160]}, status_code=500)

@app.get("/admin")
async def admin_panel(request: Request):
    if (not ADMIN_PANEL_SECRET) or (request.query_params.get("secret") != ADMIN_PANEL_SECRET):
        return JSONResponse({"status": "forbidden"}, status_code=403)
    now = time.time()
    # Use persisted user info to avoid reset after restarts
    users_total = len(STATS_USERS_INFO)
    users_all_time = users_total
    users_active_30d = sum(1 for u in STATS_USERS_INFO.values() if now - float(u.get("last_seen", 0)) <= 30*86400)
    users_active_24h = sum(1 for u in STATS_USERS_INFO.values() if now - float(u.get("last_seen", 0)) <= 86400)
    users_active_5m = sum(1 for u in STATS_USERS_INFO.values() if now - float(u.get("last_seen", 0)) <= 300)
    sessions_total = sum(int(u.get("sessions", 0)) for u in STATS_USERS_INFO.values())
    active_seconds_total = sum(float(u.get("active_seconds", 0.0)) for u in STATS_USERS_INFO.values())
    avg_session_sec = int(active_seconds_total / sessions_total) if sessions_total else 0
    total_processed = STATS.get("gens_ok", 0) + STATS.get("gens_copy_ok", 0)

    # Time range helpers from daily buckets
    def sum_daily(keys: List[str], days: int) -> int:
        if days <= 0:
            return 0
        out = 0
        now_ts = time.time()
        for d in range(days):
            dk = _date_key(now_ts - d * 86400)
            day_map = STATS_DAILY.get(dk) or {}
            for k in keys:
                out += int(day_map.get(k, 0))
        return out
    def range_metrics(days: int) -> Dict[str, int]:
        return {
            "processed": sum_daily(["gens_ok", "gens_copy_ok"], days),
            "messages": sum_daily(["messages"], days),
            "photos": sum_daily(["photos"], days),
            "blocked": sum_daily(["blocked"], days),
            "payments": sum_daily(["payments"], days),
            "referrals": sum_daily(["referrals"], days),
            "ref_bonus_ref": sum_daily(["ref_bonus_ref"], days),
            "ref_bonus_invited": sum_daily(["ref_bonus_invited"], days),
        }
    day_m = range_metrics(1)
    week_m = range_metrics(7)
    month_m = range_metrics(30)

    # Helpers
    def fmt_sec(s):
        h = s // 3600; m = (s % 3600) // 60; sc = s % 60
        return f"{h:02d}:{m:02d}:{sc:02d}"
    def time_ago(ts: float) -> str:
        if not ts:
            return "—"
        d = max(0, int(now - ts))
        if d < 60:
            return f"{d}s ago"
        if d < 3600:
            return f"{d//60}m ago"
        if d < 86400:
            return f"{d//3600}h ago"
        return f"{d//86400}d ago"
    def uname_or_id(uid: int, username: Optional[str]) -> str:
        if username:
            return f"@{username}"
        return str(uid)
    def balance_str(uid: int, username: Optional[str]) -> str:
        if is_free_user(uid, username):
            return "∞"
        return str(USER_CREDITS.get(uid, FREE_QUOTA))

    # Top users by generations and time
    items = []
    for uid, u in STATS_USERS_INFO.items():
        refst = REF_STATS.get(uid, {})
        items.append({
            "uid": uid,
            "username": u.get("username") or str(uid),
            "gens": int(u.get("gens_ok", 0)) + int(u.get("gens_copy_ok", 0)),
            "time": int(float(u.get("active_seconds", 0.0))),
            "sessions": int(u.get("sessions", 0)),
            "last_seen": float(u.get("last_seen", 0.0)),
            "payments": int(u.get("payments", 0)),
            "balance": USER_CREDITS.get(uid, FREE_QUOTA),
            "lang": USER_LANG.get(uid, LANG_DEFAULT),
            "invited": int(refst.get("count", 0)),
            "ref_earned": int(refst.get("earned", 0)),
        })
    top_gens = sorted(items, key=lambda x: x["gens"], reverse=True)[:10]
    top_time = sorted(items, key=lambda x: x["time"], reverse=True)[:10]

    # Buyers and Online lists
    buyers = [
        i for i in items
        if (i.get("payments", 0) > 0) or (not is_free_user(i["uid"], i.get("username")) and int(i.get("balance", 0)) > FREE_QUOTA)
    ]
    buyers_sorted = sorted(buyers, key=lambda x: (x["payments"], x["gens"]), reverse=True)[:50]
    online_now = [i for i in items if now - float(i.get("last_seen", 0)) <= 300]
    online_sorted = sorted(online_now, key=lambda x: x.get("last_seen", 0), reverse=True)

    # Referrals
    ref_items = []
    for rid, st in REF_STATS.items():
        ref_items.append({"uid": rid, "count": st.get("count", 0), "earned": st.get("earned", 0)})
    top_ref = sorted(ref_items, key=lambda x: x["count"], reverse=True)[:10]

    html = f"""
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>iModel — Admin</title>
  <style>
    :root {{ --bg:#0f1115; --card:#151922; --accent:#7aa2f7; --muted:#9aa4b2; --ok:#24c38b; --fail:#e56565; }}
    * {{ box-sizing: border-box; }}
    body {{ margin:0; font: 14px/1.45 -apple-system,BlinkMacSystemFont,Segoe UI,Roboto,Helvetica,Arial; background:var(--bg); color:#e6edf3; }}
    header {{ padding:16px 24px; border-bottom:1px solid #202636; }}
    h1 {{ font-size:18px; margin:0; }}
    .wrap {{ padding:20px; max-width:1100px; margin:0 auto; }}
    .grid {{ display:grid; grid-template-columns: repeat(4,1fr); gap:14px; }}
    .card {{ background:var(--card); border:1px solid #202636; border-radius:10px; padding:14px; }}
    .kpi .v {{ font-size:22px; font-weight:600; }}
    .muted {{ color:var(--muted); }}
    .ok {{ color:var(--ok); }}
    .fail {{ color:var(--fail); }}
    table {{ width:100%; border-collapse:collapse; }}
    th,td {{ padding:8px 10px; border-bottom:1px solid #242a3a; text-align:left; }}
    th {{ color:#aab4c2; font-weight:600; font-size:12px; text-transform:uppercase; letter-spacing:.04em; }}
    .section {{ margin-top:18px; }}
    .pill {{ display:inline-block; padding:2px 6px; border-radius:6px; background:#202636; color:#b8c2d1; font-size:12px; }}
  </style>
  </head>
  <body>
    <header><h1>iModel — Admin Panel</h1></header>
    <div class="wrap">
      <div class="grid kpi" style="grid-template-columns: repeat(3,1fr);">
        <div class="card"><div class="muted">Day</div><div class="v">{day_m['processed']}</div><div class="muted">msg {day_m['messages']} · photo {day_m['photos']} · pay {day_m['payments']}</div></div>
        <div class="card"><div class="muted">Week</div><div class="v">{week_m['processed']}</div><div class="muted">msg {week_m['messages']} · photo {week_m['photos']} · pay {week_m['payments']}</div></div>
        <div class="card"><div class="muted">Month</div><div class="v">{month_m['processed']}</div><div class="muted">msg {month_m['messages']} · photo {month_m['photos']} · pay {month_m['payments']}</div></div>
      </div>

      <div class="grid kpi" style="grid-template-columns: repeat(4,1fr); margin-top:14px;">
        <div class="card"><div class="muted">Referrals · Day</div><div class="v">{day_m['referrals']}</div><div class="muted">earned {day_m['ref_bonus_ref']} · new {day_m['ref_bonus_invited']}</div></div>
        <div class="card"><div class="muted">Referrals · Week</div><div class="v">{week_m['referrals']}</div><div class="muted">earned {week_m['ref_bonus_ref']} · new {week_m['ref_bonus_invited']}</div></div>
        <div class="card"><div class="muted">Referrals · Month</div><div class="v">{month_m['referrals']}</div><div class="muted">earned {month_m['ref_bonus_ref']} · new {month_m['ref_bonus_invited']}</div></div>
        <div class="card"><div class="muted">Referrals · All</div><div class="v">{STATS.get('referrals',0)}</div><div class="muted">earned {STATS.get('ref_bonus_ref',0)} · new {STATS.get('ref_bonus_invited',0)}</div></div>
      </div>
      <div class="grid kpi">
        <div class="card"><div class="muted">Users total</div><div class="v">{users_total}</div><div class="muted">Active 24h: {users_active_24h} · Now: {users_active_5m}</div></div>
        <div class="card"><div class="muted">Sessions</div><div class="v">{sessions_total}</div><div class="muted">Avg length: {fmt_sec(avg_session_sec)}</div></div>
        <div class="card"><div class="muted">Processed</div><div class="v ok">{total_processed}</div><div class="muted">OK: {STATS.get('gens_ok',0)} · Copy OK: {STATS.get('gens_copy_ok',0)}</div></div>
        <div class="card"><div class="muted">Blocked</div><div class="v fail">{STATS.get('blocked',0)}</div><div class="muted">Updates: {STATS.get('updates',0)}</div></div>
      </div>
      <div class="grid kpi" style="grid-template-columns: repeat(2,1fr); margin-top:14px;">
        <div class="card"><div class="muted">Users (all time)</div><div class="v">{users_all_time}</div></div>
        <div class="card"><div class="muted">Active 30d</div><div class="v">{users_active_30d}</div></div>
      </div>

      <div class="grid section">
        <div class="card" style="grid-column: span 2;">
          <div class="muted">Top by generations</div>
          <table><tr><th>User</th><th>Gens</th><th>Sessions</th></tr>
            {''.join(f'<tr><td>@{i["username"]}</td><td>{i["gens"]}</td><td>{i["sessions"]}</td></tr>' for i in top_gens)}
          </table>
        </div>
        <div class="card" style="grid-column: span 2;">
          <div class="muted">Top by active time</div>
          <table><tr><th>User</th><th>Time</th><th>Sessions</th></tr>
            {''.join(f'<tr><td>@{i["username"]}</td><td>{fmt_sec(i["time"])}</td><td>{i["sessions"]}</td></tr>' for i in top_time)}
          </table>
        </div>
      </div>

      <div class="grid section">
        <div class="card" style="grid-column: span 2;">
          <div class="muted">Referrals</div>
          <table><tr><th>User</th><th>Invited</th><th>Earned</th></tr>
            {''.join(f'<tr><td>{r["uid"]}</td><td>{r["count"]}</td><td>{r["earned"]}</td></tr>' for r in top_ref)}
          </table>
        </div>
        <div class="card" style="grid-column: span 2;">
          <div class="muted">Financial</div>
          <div>Payments: <b>{STATS.get('payments',0)}</b> · Promo used: <b>{STATS.get('promo_used',0)}</b></div>
          <div class="muted" style="margin-top:8px;">Published → channel: {STATS.get('published_channel',0)} · group: {STATS.get('published_group',0)} · auto: {STATS.get('auto_post',0)}</div>
        </div>
      </div>

      <div class="section">
        <div class="card">
          <div class="muted">Online now ({len(online_sorted)})</div>
          <table>
            <tr><th>User</th><th>Lang</th><th>Gens</th><th>Balance</th><th>Sessions</th><th>Last seen</th></tr>
            {''.join(
              f'<tr>'
              f'<td>{uname_or_id(i["uid"], i["username"])}</td>'
              f'<td>{i.get("lang","-")}</td>'
              f'<td>{i["gens"]}</td>'
              f'<td>{("∞" if is_free_user(i["uid"], i["username"]) else USER_CREDITS.get(i["uid"], FREE_QUOTA))}</td>'
              f'<td>{i["sessions"]}</td>'
              f'<td>{time_ago(i.get("last_seen",0))}</td>'
              f'</tr>' for i in online_sorted)
            }
          </table>
        </div>
      </div>

      <div class="section">
        <div class="card">
          <div class="muted">Buyers (payments > 0)</div>
          <table>
            <tr><th>User</th><th>Lang</th><th>Payments</th><th>Invited</th><th>Earned</th><th>Gens</th><th>Balance</th><th>Sessions</th><th>Last seen</th></tr>
            {''.join(
              f'<tr>'
              f'<td>{uname_or_id(i["uid"], i["username"])}</td>'
              f'<td>{i.get("lang","-")}</td>'
              f'<td>{i.get("payments",0)}</td>'
              f'<td>{i.get("invited",0)}</td>'
              f'<td>{i.get("ref_earned",0)}</td>'
              f'<td>{i["gens"]}</td>'
              f'<td>{("∞" if is_free_user(i["uid"], i["username"]) else USER_CREDITS.get(i["uid"], FREE_QUOTA))}</td>'
              f'<td>{i["sessions"]}</td>'
              f'<td>{time_ago(i.get("last_seen",0))}</td>'
              f'</tr>' for i in buyers_sorted)
            }
          </table>
        </div>
      </div>
    </div>
  </body>
  </html>
    """
    return HTMLResponse(content=html)


@api.on_event("shutdown")
async def on_shutdown():
    try:
        await bot.session.close()
    except Exception:
        pass
    

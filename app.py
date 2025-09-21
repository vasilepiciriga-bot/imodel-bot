# app.py — iModel v2.6.0
# Copy-mode v2 (Scene Lock) + Identity Lock ++ Negative + Stable Seed
# Остальное: AutoLang + GPT refine + S3 + Replicate (NanoBanana + RealESRGAN_x4plus)
# Stars + Whitelist/Admin unlimited + Promo + 3 langs + pricing + gallery + refer
# Безопасные отправки; Видео/анимация отключены. Доставка — байты.

import os
import re
import time
import uuid
import base64
import random
import hashlib
import asyncio
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


REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")
os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_MODEL_VISION = os.getenv("OPENAI_MODEL_VISION", OPENAI_MODEL)

# Filter toggles
ALLOW_NSFW   = os.getenv("ALLOW_NSFW", "0") == "1"
ALLOW_CELEBS = os.getenv("ALLOW_CELEBS", "1") == "1"

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
}
STATS_USERS: Set[int] = set()
STATS_USERS_INFO: Dict[int, Dict[str, object]] = {}

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

def _uadd(uid: int, key: str, n: int = 1):
    info = STATS_USERS_INFO.get(uid)
    if not info:
        _touch_user(uid)
        info = STATS_USERS_INFO.get(uid)
    try:
        info[key] = int(info.get(key, 0)) + n
    except Exception:
        info[key] = n

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

# Replicate models
NANOBANANA_MODEL = os.getenv("NANOBANANA_MODEL", "google/nano-banana")
ESRGAN_MODEL     = os.getenv("ESRGAN_MODEL", "nightmareai/real-esrgan")  # x4plus via params
ESRGAN_DISABLED  = False  # auto-disable on first 404

# Language / quotas
LANG_DEFAULT = os.getenv("LANG_DEFAULT", "ru")
FREE_QUOTA   = int(os.getenv("FREE_QUOTA", "5"))

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
ADMIN_USERNAMES_RAW = os.getenv("ADMIN_USERNAMES", "@piciriga,@MarkBeth_beauty")
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

# публикация до/после
LAST_REF: Dict[int, bytes]   = {}
LAST_PHOTO: Dict[int, bytes] = {}

# Copy Mode
USER_COPY_MODE: Set[int]         = set()
USER_COPY_STYLE: Dict[int, bytes]= {}
USER_COPY_PROMPT: Dict[int, str] = {}

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
REF_BONUS_NEW  = int(os.getenv("REF_BONUS_NEW", "3"))
REF_BONUS_REF  = int(os.getenv("REF_BONUS_REF", "3"))
REF_MAP: Dict[int, int] = {}
REF_STATS: Dict[int, Dict[str, int]] = {}

BOT_USERNAME_GLOBAL = None

# ===================== I18N =========================
T = {
    "ru": {
        "start": "👋 Добро пожаловать в iModel — профессиональный фотогенератор.\n\nКак это работает:\n1) Пришлите 1–4 селфи (хороший свет помогает)\n2) Опишите сцену или включите «Скопировать» (/copy)\n3) Получите готовый результат.\n\nБыстрые команды: /help · /presets · /buy · /pricing · /promo · /balance · /gallery · /refer · /lang · /copy",
        "help": "📘 Советы:\n• 1–4 селфи без сильных фильтров\n• Опишите место, свет, стиль, кадрирование\n• Для точной копии сцены — /copy (сначала образец, затем селфи)",
        "need_photo": "Сначала пришли фото лица.",
        "photo_ok": "Фото получено ✅ Теперь опишите сцену или используйте /presets.",
        "gen": "Генерирую… ⏳",
        "fail": "Не удалось сгенерировать. Попробуйте изменить описание или фото.",
        "ready": "Готово ✅",
        "credits_none": "Нет кредитов. Используй /buy или /promo.",
        "choose_lang": "Выбери язык:\n/ru  /en  /ro",
        "lang_ru": "Язык установлен: Русский",
        "lang_en": "Язык установлен: Английский",
        "lang_ro": "Язык установлен: Румынский",
        "presets": "Идеи сцен:\n• Студия: портрет, мягкий свет, тёмный фон\n• Улица: закат, боке, 85мм\n• Интерьер: кафе, тёплый свет, винтаж\n• Природа: лес, рассеянный свет, «плёнка»",
        "blocked": "⛔ Запрос запрещён.",
        "btn_balance": "Баланс",
        "btn_buy": "Купить",
        "btn_more": "Ещё вариант",
        "btn_publish": "Опубликовать",
        "btn_publish_group": "В группу",
        "menu_presets": "🎛 Пресеты",
        "menu_help": "🆘 Помощь",
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
        "start": "👋 Welcome to iModel — professional photo generation.\n\nHow it works:\n1) Send 1–4 selfies (good lighting helps)\n2) Describe the scene or use Copy Mode (/copy)\n3) Get the result.\n\nQuick commands: /help · /presets · /buy · /pricing · /promo · /balance · /gallery · /refer · /lang · /copy",
        "help": "📘 Tips:\n• 1–4 selfies, minimal filters/makeup\n• Describe location, light, style, framing\n• For exact scene copy — /copy (style first, then selfie)",
        "need_photo": "Please send a face photo first.",
        "photo_ok": "Photo received ✅ Now describe the scene or use /presets.",
        "gen": "Working… ⏳",
        "fail": "Generation failed. Try adjusting your description or selfie.",
        "ready": "Done ✅",
        "credits_none": "No credits. Use /buy or /promo.",
        "choose_lang": "Choose language:\n/ru  /en  /ro",
        "lang_ru": "Language set: Russian",
        "lang_en": "Language set: English",
        "lang_ro": "Language set: Romanian",
        "presets": "Scene ideas:\n• Studio: portrait, soft light, dark backdrop\n• Outdoor: sunset, bokeh, 85mm\n• Interior: cafe, warm tones, vintage\n• Nature: forest, diffused light, film look",
        "blocked": "⛔ Request blocked.",
        "btn_balance": "Balance",
        "btn_buy": "Buy",
        "btn_more": "More",
        "btn_publish": "Publish",
        "btn_publish_group": "To group",
        "menu_presets": "🎛 Presets",
        "menu_help": "🆘 Help",
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
        "start": "👋 Bine ai venit la iModel — generare foto profesională.\n\nCum funcționează:\n1) Trimite 1–4 selfie‑uri (lumina bună ajută)\n2) Descrie scena sau folosește „Copiază” (/copy)\n3) Primești rezultatul.\n\nComenzi rapide: /help · /presets · /buy · /pricing · /promo · /balance · /gallery · /refer · /lang · /copy",
        "help": "📘 Sfaturi:\n• 1–4 selfie‑uri, minim filtre/machiaj\n• Descrie scena: locație, lumină, stil, încadrare\n• Pentru copiere exactă — /copy (stil apoi selfie)",
        "need_photo": "Trimite o poză cu fața mai întâi.",
        "photo_ok": "Poză primită ✅ Acum descrie scena sau folosește /presets.",
        "gen": "Generez… ⏳",
        "fail": "Nu am reușit. Încearcă altă descriere sau alt selfie.",
        "ready": "Gata ✅",
        "credits_none": "Nu mai ai credite. /buy sau /promo.",
        "choose_lang": "Alege limba:\n/ru  /en  /ro",
        "lang_ru": "Limba setată: Rusă",
        "lang_en": "Limba setată: Engleză",
        "lang_ro": "Limba setată: Română",
        "presets": "Idei de scenă:\n• Studio: portret, lumină moale, fundal închis\n• Exterior: apus, bokeh, 85mm\n• Interior: cafenea, tonuri calde, vintage\n• Natură: pădure, lumină difuză, aspect film",
        "blocked": "⛔ Cerere blocată.",
        "btn_balance": "Sold",
        "btn_buy": "Cumpără",
        "btn_more": "Încă una",
        "btn_publish": "Publică",
        "btn_publish_group": "În grup",
        "menu_presets": "🎛 Preseturi",
        "menu_help": "🆘 Ajutor",
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
        print("S3 presigned url:", url[:110], "...")
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

def replicate_generate(model: str, inputs: dict) -> Optional[str]:
    try:
        pred = replicate.predictions.create(model=model, input=inputs)
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
        print("replicate.predictions.create error:", em[:200])
        if "sensitive" in em.lower():
            return "SENSITIVE"

    try:
        out = replicate.run(model, input=inputs)
        url = _extract_first_url(out)
        if url:
            return url
    except Exception as e2:
        em2 = str(e2)
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
            STATS["mj_prompt_ok"] += 1
        except Exception:
            STATS["mj_prompt_ok"] += 1
        return line
    except Exception as e:
        print("Vision MJ prompt error:", str(e)[:200])
        STATS["mj_prompt_fail"] += 1
        return None

# ===== Короткий caption (для канала) =================
def generate_instacaption(user_prompt: str, lang: str = "ru") -> str:
    # (как раньше) — опущено ради краткости
    salts = ["Soft light. Sharp story.", "A little magic, a lot of you.", "Subtle glow, bold vibe."]
    return random.choice(salts)

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
        if not ESRGAN_MODEL or ESRGAN_DISABLED:
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
    STATS["auto_post"] += 1

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
        InlineKeyboardButton(text="✨ " + lang.get("btn_publish", "Publish"), callback_data="pub_yes"),
        InlineKeyboardButton(text="👥 " + lang.get("btn_publish_group", "To group"), callback_data="pub_group"),
    ]])

def main_menu_inline(chat_id: int) -> InlineKeyboardMarkup:
    lang = L(chat_id)
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐ " + lang["btn_buy"],      callback_data="buy_open"),
            InlineKeyboardButton(text="💰 " + lang["btn_balance"],  callback_data="balance"),
            InlineKeyboardButton(text=lang.get("menu_pricing", "💎 /pricing"),                callback_data="pricing_open"),
        ],
        [
            InlineKeyboardButton(text=lang.get("menu_presets", "🎛 /presets"), callback_data="presets_open"),
            InlineKeyboardButton(text="📋 " + lang["menu_copy"],   callback_data="copy_open"),
            InlineKeyboardButton(text=lang.get("menu_help", "🆘 /help"),    callback_data="help_open"),
        ],
    ])

# ===================== PAYMENTS (STARS) ==============
def has_credit(chat_id: int, username: Optional[str] = None) -> bool:
    if is_free_user(chat_id, username):
        return True
    return USER_CREDITS.get(chat_id, FREE_QUOTA) > 0

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
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=lang["buy_btn_10"],  callback_data="buy_stars_10")],
        [InlineKeyboardButton(text=lang["buy_btn_30"],  callback_data="buy_stars_30")],
        [InlineKeyboardButton(text=lang["buy_btn_100"], callback_data="buy_stars_100")],
    ])
    await safe_answer(m, lang["buy_title"], reply_markup=kb)

@dp.callback_query(F.data.startswith("buy_stars_"))
async def cb_buy_stars(c: CallbackQuery):
    pack = c.data.split("_")[-1]
    if pack == "10":
        await send_stars_invoice(c.message.chat.id, "iModel — 10 генераций", "Пакет 10 генераций", "pack_10", 200)
    elif pack == "30":
        await send_stars_invoice(c.message.chat.id, "iModel — 30 генераций", "Пакет 30 генераций", "pack_30", 500)
    elif pack == "100":
        await send_stars_invoice(c.message.chat.id, "iModel — 100 генераций", "Пакет 100 генераций", "pack_100", 1200)
    await c.answer()

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
    USER_CREDITS[m.chat.id] = USER_CREDITS.get(m.chat.id, 0) + add
    await safe_answer(m, L(m.chat.id)["bought"].format(add=add, all=USER_CREDITS[m.chat.id]))
    STATS["payments"] += 1
    _uadd(m.chat.id, "payments", 1)

# ===================== COMMANDS =======================
@dp.message(Command("version"))
async def cmd_version(m: Message):
    await safe_answer(m, f"{L(m.chat.id)['version'].format(ver=APP_VERSION)}")

@dp.message(Command("pricing"))
async def cmd_pricing(m: Message):
    await safe_answer(m, L(m.chat.id)["pricing"])
    await cmd_buy(m)

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
                USER_CREDITS.setdefault(invited_id, FREE_QUOTA)
                USER_CREDITS[invited_id] += REF_BONUS_NEW
                REF_STATS.setdefault(ref_id, {"count": 0, "earned": 0})
                REF_STATS[ref_id]["count"] += 1
                REF_STATS[ref_id]["earned"] += REF_BONUS_REF
                USER_CREDITS[ref_id] = USER_CREDITS.get(ref_id, FREE_QUOTA) + REF_BONUS_REF
                STATS["referrals"] += 1
        except Exception:
            pass

    USER_CREDITS.setdefault(m.chat.id, FREE_QUOTA)
    USER_SEEN_TEXT.discard(m.chat.id)
    await safe_answer(m, L(m.chat.id)["start"], reply_markup=main_menu_inline(m.chat.id))
    STATS_USERS.add(m.chat.id)

@dp.message(Command("help"))
async def cmd_help(m: Message):
    await safe_answer(m, L(m.chat.id)["help"])

@dp.message(Command("lang"))
async def cmd_lang(m: Message):
    await safe_answer(m, L(m.chat.id)["choose_lang"])

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

@dp.message(Command("presets"))
async def cmd_presets(m: Message):
    await safe_answer(m, L(m.chat.id)["presets"])

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
    await safe_answer(m, lang["promo_ok"].format(add=add, all=USER_CREDITS[m.chat.id]))
    STATS["promo_used"] += 1

@dp.message(Command("balance"))
async def cmd_balance(m: Message):
    free = L(m.chat.id)["balance_free"] if is_free_user(m.chat.id, getattr(m.from_user, "username", None)) else ""
    n = USER_CREDITS.get(m.chat.id, FREE_QUOTA)
    await safe_answer(m, L(m.chat.id)["balance"].format(n=n, free=free))

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
    await safe_answer(
        m,
        "👥 Пригласи друзей и получай бонусные генерации!\n"
        f"Твоя ссылка: {link}\n\n"
        f"Приглашено: {st['count']}\n"
        f"Получено бонусов: {st['earned']} генераций"
    )

# ======= INLINE callbacks =======
@dp.callback_query(F.data == "help_open")
async def cb_help(c: CallbackQuery):
    await c.answer()
    await c.message.answer(L(c.message.chat.id)["help"])

@dp.callback_query(F.data == "presets_open")
async def cb_presets(c: CallbackQuery):
    await c.answer()
    await c.message.answer(L(c.message.chat.id)["presets"])

@dp.callback_query(F.data == "promo_open")
async def cb_promo(c: CallbackQuery):
    await c.answer()
    await c.message.answer(L(c.message.chat.id)["promo_usage"])

@dp.callback_query(F.data == "lang_open")
async def cb_lang(c: CallbackQuery):
    await c.answer()
    await c.message.answer(L(c.message.chat.id)["choose_lang"])

@dp.callback_query(F.data == "pricing_open")
async def cb_pricing(c: CallbackQuery):
    await c.answer()
    await c.message.answer(L(c.message.chat.id)["pricing"])
    await cmd_buy(c.message)

@dp.callback_query(F.data == "balance")
async def cb_balance(c: CallbackQuery):
    chat_id = c.message.chat.id
    await c.answer()
    n = USER_CREDITS.get(chat_id, FREE_QUOTA)
    free_note = L(chat_id)["balance_free"] if is_free_user(chat_id, getattr(c.from_user, "username", None)) else ""
    await c.message.answer(L(chat_id)["balance"].format(n=n, free=free_note))

@dp.callback_query(F.data == "buy_open")
async def cb_buy_open(c: CallbackQuery):
    await c.answer()
    await cmd_buy(c.message)

@dp.callback_query(F.data == "copy_open")
async def cb_copy_open(c: CallbackQuery):
    USER_COPY_MODE.add(c.message.chat.id)
    USER_COPY_STYLE.pop(c.message.chat.id, None)
    await c.answer()
    await c.message.answer(L(c.message.chat.id)["copy_intro"])

@dp.callback_query(F.data == "pub_yes")
async def cb_pub_yes(c: CallbackQuery):
    if not GALLERY_CHANNEL_ID:
        await c.answer()
        return await c.message.answer("Канал не настроен.")
    before = LAST_REF.get(c.message.chat.id)
    after  = LAST_PHOTO.get(c.message.chat.id)
    if not after:
        await c.answer()
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
    STATS["published_channel"] += 1
    _uadd(c.message.chat.id, "published", 1)
    await c.answer("Опубликовано")

@dp.callback_query(F.data == "pub_group")
async def cb_pub_group(c: CallbackQuery):
    if not PUBLISH_GROUP_ID:
        await c.answer()
        return await c.message.answer("Группа не настроена.")
    before = LAST_REF.get(c.message.chat.id)
    after  = LAST_PHOTO.get(c.message.chat.id)
    if not after:
        await c.answer()
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
    STATS["published_group"] += 1
    _uadd(c.message.chat.id, "published", 1)
    await c.answer("Опубликовано в группе")

# ===================== FLOW: PHOTO ====================
@dp.message(F.photo)
async def on_photo(m: Message):
    if m.chat.id not in USER_LANG:
        USER_LANG[m.chat.id] = locale_to_lang(getattr(m.from_user, "language_code", None))

    f = await bot.get_file(m.photo[-1].file_id)
    b = await bot.download_file(f.file_path)
    img_bytes = b.read()
    STATS["photos"] += 1
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

            USER_CREDITS.setdefault(m.chat.id, FREE_QUOTA)
            if not has_credit(m.chat.id, getattr(m.from_user, "username", None)):
                return await safe_answer(m, L(m.chat.id)["credits_none"])

            wait = await safe_answer(m, L(m.chat.id)["gen"])
            seed = (hashlib.md5(style_bytes).hexdigest())
            seed_int = int(seed[:8], 16)

            # строгий режим: жёсткая сцена + identity lock + negative
            # 2) Генерим по selfie + текстовому промпту (БЕЗ передачи style-image в модель)
            final_bytes = generate_image_from_bytes(
                img_bytes,
                scene_spec,
                lang=USER_LANG.get(m.chat.id, LANG_DEFAULT),
                seed=seed_int,
                strict=True,
                style_bytes=None,
                lock_scene=False,
            )
            if not final_bytes:
                # вторая попытка: ещё жёстче
                final_bytes = generate_image_from_bytes(
                    img_bytes,
                    scene_spec + ". Keep face absolutely unchanged, do not beautify, do not reshape.",
                    lang=USER_LANG.get(m.chat.id, LANG_DEFAULT),
                    seed=seed_int,
                    strict=True,
                    style_bytes=None,
                    lock_scene=False,
                )
                if not final_bytes:
                    if wait: await safe_edit_text(wait, L(m.chat.id)["fail"])
                    STATS["gens_copy_fail"] += 1
                    _uadd(m.chat.id, "gens_copy_fail", 1)
                    return

            if not is_free_user(m.chat.id, getattr(m.from_user, "username", None)):
                USER_CREDITS[m.chat.id] -= 1
            USER_LAST_OUTPUT[m.chat.id] = final_bytes
            USER_LAST_PROMPT[m.chat.id] = scene_spec
            LAST_PHOTO[m.chat.id] = final_bytes
            STATS["gens_copy_ok"] += 1
            _uadd(m.chat.id, "gens_copy_ok", 1)

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
        return await safe_answer(m, L(m.chat.id)["photo_ok"])
    if blocked(caption):
        STATS["blocked"] += 1
        return await safe_answer(m, L(m.chat.id)["blocked"])

    USER_CREDITS.setdefault(m.chat.id, FREE_QUOTA)
    if not has_credit(m.chat.id, getattr(m.from_user, "username", None)):
        return await safe_answer(m, L(m.chat.id)["credits_none"])

    wait = await safe_answer(m, L(m.chat.id)["gen"])
    seed_int = (hash(m.chat.id) % 10_000_000)
    final_bytes = generate_image_from_bytes(
        img_bytes, caption, lang=USER_LANG.get(m.chat.id, LANG_DEFAULT),
        seed=seed_int
    )
    if not final_bytes:
        if wait: await safe_edit_text(wait, L(m.chat.id)["fail"])
        STATS["gens_fail"] += 1
        _uadd(m.chat.id, "gens_fail", 1)
        return

    if not is_free_user(m.chat.id, getattr(m.from_user, "username", None)):
        USER_CREDITS[m.chat.id] -= 1
    USER_LAST_OUTPUT[m.chat.id] = final_bytes
    USER_LAST_PROMPT[m.chat.id] = caption
    LAST_PHOTO[m.chat.id] = final_bytes
    STATS["gens_ok"] += 1
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

# ===================== FLOW: TEXT =====================
@dp.message(F.text & ~F.text.startswith("/"))
async def on_prompt(m: Message):
    # Если включён Copy Mode и пришёл текст — трактуем как ручное редактирование промпта для копирования сцены
    if m.chat.id in USER_COPY_MODE:
        USER_COPY_PROMPT[m.chat.id] = m.text.strip()
        await safe_answer(m, "Промпт обновлён. Теперь пришлите селфи.")
        return
    STATS["messages"] += 1
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
        STATS["blocked"] += 1
        _uadd(m.chat.id, "blocked", 1)
        return await safe_answer(m, L(m.chat.id)["blocked"])

    refs = USER_REFS.get(m.chat.id, [])
    if not refs:
        return await safe_answer(m, L(m.chat.id)["need_photo"])

    USER_CREDITS.setdefault(m.chat.id, FREE_QUOTA)
    if not has_credit(m.chat.id, getattr(m.from_user, "username", None)):
        return await safe_answer(m, L(m.chat.id)["credits_none"])

    wait = await safe_answer(m, L(m.chat.id)["gen"])
    ref = refs[-1]
    seed_int = (hash(m.chat.id) % 10_000_000)
    final_bytes = generate_image_from_bytes(
        ref, text, lang=USER_LANG.get(m.chat.id, LANG_DEFAULT),
        seed=seed_int
    )
    if not final_bytes:
        if wait: await safe_edit_text(wait, L(m.chat.id)["fail"])
        STATS["gens_fail"] += 1
        _uadd(m.chat.id, "gens_fail", 1)
        return

    if not is_free_user(m.chat.id, getattr(m.from_user, "username", None)):
        USER_CREDITS[m.chat.id] -= 1
    USER_LAST_OUTPUT[m.chat.id] = final_bytes
    USER_LAST_PROMPT[m.chat.id] = text
    LAST_PHOTO[m.chat.id] = final_bytes
    STATS["gens_ok"] += 1
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
        await c.answer()
        return await c.message.answer(L(chat_id)["need_photo"])

    USER_CREDITS.setdefault(chat_id, FREE_QUOTA)
    if not has_credit(chat_id, getattr(c.from_user, "username", None)):
        await c.answer()
        return await c.message.answer(L(chat_id)["credits_none"])

    await c.answer()
    msg = await c.message.answer(L(chat_id)["gen"])
    ref = refs[-1]
    # тот же промпт, seed + 1 (минимальная вариативность, лицо стабильное)
    seed_int = ((hash(chat_id) % 10_000_000) + 1)
    result = generate_image_from_bytes(
        ref, base_prompt, lang=USER_LANG.get(chat_id, LANG_DEFAULT),
        seed=seed_int
    )
    if not result:
        STATS["gens_fail"] += 1
        _uadd(chat_id, "gens_fail", 1)
        return await safe_edit_text(msg, L(chat_id)["fail"])

    if not is_free_user(chat_id, getattr(c.from_user, "username", None)):
        USER_CREDITS[chat_id] -= 1
    USER_LAST_OUTPUT[chat_id] = result
    USER_LAST_PROMPT[chat_id] = base_prompt
    LAST_PHOTO[chat_id] = result
    STATS["gens_ok"] += 1
    _uadd(chat_id, "gens_ok", 1)

    hist = USER_HISTORY.setdefault(chat_id, [])
    hist.append(result)
    if len(hist) > GALLERY_LIMIT:
        del hist[:-GALLERY_LIMIT]

    await msg.delete()
    await c.message.answer_photo(
        photo=BufferedInputFile(result, filename="imodel_result.jpg"),
        caption="✅",
        reply_markup=kb_actions(chat_id),
    )


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

    if BOT_TOKEN and WEBHOOK_BASE:
        await ensure_webhook()
        print(f"✅ Вебхук установлен: {WEBHOOK_URL}")
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
@app.on_event("shutdown")
async def on_shutdown():
    print("🛑 Shutting down...")
    try:
        await bot.delete_webhook()
    finally:
        await bot.session.close()
    print("✅ Webhook removed")

@app.post("/")
async def telegram_webhook(request: Request):
    if request.query_params.get("secret") != WEBHOOK_SECRET:
        return JSONResponse({"status": "forbidden"}, status_code=403)
    data = await request.json()
    try:
        STATS["updates"] += 1
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

@app.get("/metrics")
async def http_metrics(request: Request):
    if METRICS_SECRET and request.query_params.get("secret") != METRICS_SECRET:
        return JSONResponse({"status": "forbidden"}, status_code=403)
    resp = dict(STATS)
    resp["users"] = len(STATS_USERS)
    resp["uptime_sec"] = int(time.time() - STATS["start_ts"]) if STATS.get("start_ts") else 0
    return resp

@app.get("/admin")
async def admin_panel(request: Request):
    if ADMIN_PANEL_SECRET and request.query_params.get("secret") != ADMIN_PANEL_SECRET:
        return JSONResponse({"status": "forbidden"}, status_code=403)
    now = time.time()
    users_total = len(STATS_USERS)
    users_active_24h = sum(1 for u in STATS_USERS_INFO.values() if now - float(u.get("last_seen", 0)) <= 86400)
    users_active_5m = sum(1 for u in STATS_USERS_INFO.values() if now - float(u.get("last_seen", 0)) <= 300)
    sessions_total = sum(int(u.get("sessions", 0)) for u in STATS_USERS_INFO.values())
    active_seconds_total = sum(float(u.get("active_seconds", 0.0)) for u in STATS_USERS_INFO.values())
    avg_session_sec = int(active_seconds_total / sessions_total) if sessions_total else 0
    total_processed = STATS.get("gens_ok", 0) + STATS.get("gens_copy_ok", 0)

    # Top users by generations and time
    items = []
    for uid, u in STATS_USERS_INFO.items():
        items.append({
            "uid": uid,
            "username": u.get("username") or str(uid),
            "gens": int(u.get("gens_ok", 0)) + int(u.get("gens_copy_ok", 0)),
            "time": int(float(u.get("active_seconds", 0.0))),
            "sessions": int(u.get("sessions", 0)),
        })
    top_gens = sorted(items, key=lambda x: x["gens"], reverse=True)[:10]
    top_time = sorted(items, key=lambda x: x["time"], reverse=True)[:10]

    # Referrals
    ref_items = []
    for rid, st in REF_STATS.items():
        ref_items.append({"uid": rid, "count": st.get("count", 0), "earned": st.get("earned", 0)})
    top_ref = sorted(ref_items, key=lambda x: x["count"], reverse=True)[:10]

    def fmt_sec(s):
        h = s // 3600; m = (s % 3600) // 60; sc = s % 60
        return f"{h:02d}:{m:02d}:{sc:02d}"

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
  </style>
  </head>
  <body>
    <header><h1>iModel — Admin Panel</h1></header>
    <div class="wrap">
      <div class="grid kpi">
        <div class="card"><div class="muted">Users total</div><div class="v">{users_total}</div><div class="muted">Active 24h: {users_active_24h} · Now: {users_active_5m}</div></div>
        <div class="card"><div class="muted">Sessions</div><div class="v">{sessions_total}</div><div class="muted">Avg length: {fmt_sec(avg_session_sec)}</div></div>
        <div class="card"><div class="muted">Processed</div><div class="v ok">{total_processed}</div><div class="muted">OK: {STATS.get('gens_ok',0)} · Copy OK: {STATS.get('gens_copy_ok',0)}</div></div>
        <div class="card"><div class="muted">Blocked</div><div class="v fail">{STATS.get('blocked',0)}</div><div class="muted">Updates: {STATS.get('updates',0)}</div></div>
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
    

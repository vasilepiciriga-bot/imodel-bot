# app.py
# iModel — Telegram bot
# v2.3.0  (AutoLang + GPT-refine + IdentityLock + NegativePrompt + StableSeed
#         + S3 + Replicate: NanoBanana + RealESRGAN_x4plus
#         + Stars + Whitelist (admins unlimited) + Promo + 3 langs + inline menus + Gallery + Refer)
# Delivery: bytes-only (без ссылок). Видео/анимации отсутствуют.

import os
import re
import time
import uuid
import random
import hashlib
from typing import Optional, Dict, List, Set

import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message, Update, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    LabeledPrice, PreCheckoutQuery,
    BufferedInputFile,
    BotCommand, BotCommandScopeDefault,
    InputMediaPhoto,
)

import replicate
import boto3
from botocore.config import Config

# ---------- OpenAI (GPT prompt refinement) ----------
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

APP_VERSION = "iModel 2.3.0"

# ===================== ENV ==========================
BOT_TOKEN      = os.getenv("BOT_TOKEN", "")
WEBHOOK_BASE   = os.getenv("WEBHOOK_BASE", "")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "secret123")

REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")
os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")

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

# Language / quotas
LANG_DEFAULT = os.getenv("LANG_DEFAULT", "ru")
FREE_QUOTA   = int(os.getenv("FREE_QUOTA", "5"))

# Канал-галерея (опционально)
GALLERY_CHANNEL_ID = os.getenv("GALLERY_CHANNEL_ID", "")
try:
    if GALLERY_CHANNEL_ID:
        GALLERY_CHANNEL_ID = int(GALLERY_CHANNEL_ID)
except Exception:
    GALLERY_CHANNEL_ID = None

# ===================== Admins =======================
def _parse_admins(val: str) -> Set[int]:
    out: Set[int] = set()
    for x in (val or "").replace(";", ",").split(","):
        x = x.strip()
        if not x: continue
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
    """Пользователь без списаний: либо в whitelist, либо админ."""
    if uid in FREE_USERS:
        return True
    return is_admin(uid, username)

# ===================== State ========================
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
app = FastAPI(title="iModel Bot")
api = app  # alias for uvicorn

USER_REFS: Dict[int, List[bytes]]  = {}   # 1–4 исходных селфи
USER_LAST_OUTPUT: Dict[int, bytes] = {}   # последний результат
USER_LAST_PROMPT: Dict[int, str]   = {}   # последний prompt
USER_LANG: Dict[int, str]          = {}   # язык
USER_CREDITS: Dict[int, int]       = {}   # баланс
USER_SEEN_TEXT: Set[int]           = set()

# для публикации до/после
LAST_REF: Dict[int, bytes]   = {}
LAST_PHOTO: Dict[int, bytes] = {}

# Whitelist — не списываем кредиты
FREE_USERS: set[int] = set()

# Промокоды
PROMO_CODES: Dict[str, Dict[str, int]] = {
    "JOIN2025": {"add": 10, "uses": 200},
    "IMODEL5":  {"add": 5,  "uses": 500},
}

# История результатов для /gallery
USER_HISTORY: Dict[int, List[bytes]] = {}
GALLERY_LIMIT = 5

# Рефералка
REF_BONUS_NEW  = int(os.getenv("REF_BONUS_NEW", "3"))
REF_BONUS_REF  = int(os.getenv("REF_BONUS_REF", "3"))
REF_MAP: Dict[int, int] = {}  # invited_id -> referrer_id
REF_STATS: Dict[int, Dict[str, int]] = {}  # referrer_id -> {"count": n, "earned": m}

BOT_USERNAME_GLOBAL = None

# ===================== I18N =========================
T = {
    "ru": {
        "start": "Привет! Это iModel 👋\n1) Пришли 1–4 фото лица\n2) Опиши сцену\n3) Получи фото.\n\nКоманды: /help /lang /presets /buy /promo /version /balance /gallery /refer",
        "help": "Как работает:\n• Отправь 1–4 фото\n• Напиши описание\n• Получишь фото\n\nЗапрещено: NSFW/дети/селебрити.\nКоманды: /buy /promo /balance /clear /tos /privacy /gallery /refer",
        "need_photo": "Сначала пришли фото лица.",
        "photo_ok": "Фото принято ✅ Теперь опиши сцену.",
        "gen": "Генерирую… ⏳",
        "fail": "Не удалось сгенерировать. Попробуй изменить описание.",
        "ready": "Готово ✅",
        "credits_none": "Нет кредитов. Используй /buy или /promo.",
        "choose_lang": "Выбери язык:\n/ru  /en  /ro",
        "lang_ru": "Язык установлен: Русский",
        "lang_en": "Язык установлен: Английский",
        "lang_ro": "Язык установлен: Румынский",
        "presets": "Идеи:\n• Возле машины с букетом\n• Пляж, закат\n• Город, неон\n• Кафе",
        "blocked": "⛔ Запрос запрещён.",
        "btn_balance": "Баланс",
        "btn_buy": "Купить",
        "buy_title": "💳 Купить генерации (звёзды Telegram):\nЧем больше пакет — тем дешевле!",
        "buy_btn_10": "10 генераций — 200★",
        "buy_btn_30": "30 генераций — 500★",
        "buy_btn_100": "100 генераций — 1200★",
        "bought": "Спасибо! +{add}. Всего: {all}.",
        "promo_usage": "Использование: /promo КОД",
        "promo_ok": "Промокод: +{add}. Всего: {all}.",
        "promo_bad": "Промокод не найден.",
        "version": "ℹ️ Версия: {ver}",
        "balance": "Ваш баланс: {n} генераций{free}",
        "balance_free": " (whitelist — списание не производится)",
        "cleared": "Память очищена.",
        "tos": "Условия: фото используются только для генерации; запрещены NSFW/дети/селебы; результат хранится до 72ч.",
        "privacy": "Приватность: не передаём фото; /clear удаляет временные данные; /forget — полное удаление.",
        "admin_only": "Команда только для админов.",
        "granted": "Выдано {n} генераций пользователю {uid}. Баланс: {bal}.",
        "free_added": "Пользователь {uid} добавлен в whitelist.",
        "gallery_empty": "Галерея пуста.",
        "ref_link_fail": "Не удалось определить username бота.",
    },
    "en": {
        "start": "Hi! This is iModel 👋\n1) Send 1–4 face photos\n2) Describe a scene\n3) Get the photo.\n\nCommands: /help /lang /presets /buy /promo /version /balance /gallery /refer",
        "help": "How it works:\n• Send 1–4 photos\n• Write a description\n• Get result\n\nNot allowed: NSFW/kids/celebrities.\nCommands: /buy /promo /balance /clear /tos /privacy /gallery /refer",
        "need_photo": "Please send a face photo first.",
        "photo_ok": "Photo received ✅ Now describe the scene.",
        "gen": "Working… ⏳",
        "fail": "Generation failed. Try changing the description.",
        "ready": "Done ✅",
        "credits_none": "No credits. Use /buy or /promo.",
        "choose_lang": "Choose language:\n/ru  /en  /ro",
        "lang_ru": "Language set: Russian",
        "lang_en": "Language set: English",
        "lang_ro": "Language set: Romanian",
        "presets": "Ideas:\n• By car with flowers\n• Beach, sunset\n• Urban neon\n• Cafe",
        "blocked": "⛔ Request blocked.",
        "btn_balance": "Balance",
        "btn_buy": "Buy",
        "buy_title": "💳 Buy generations (Telegram Stars):\nBigger packs are cheaper!",
        "buy_btn_10": "10 gens — 200★",
        "buy_btn_30": "30 gens — 500★",
        "buy_btn_100": "100 gens — 1200★",
        "bought": "Thanks! +{add}. Total: {all}.",
        "promo_usage": "Usage: /promo CODE",
        "promo_ok": "Promo applied: +{add}. Total: {all}.",
        "promo_bad": "Promo not found.",
        "version": "ℹ️ Version: {ver}",
        "balance": "Your balance: {n} generations{free}",
        "balance_free": " (whitelisted — no deductions)",
        "cleared": "Memory cleared.",
        "tos": "Terms: photos are used only for generation; NSFW/kids/celebrities forbidden; result may be kept up to 72h.",
        "privacy": "Privacy: we don't share photos; /clear removes temporary data; /forget purges all.",
        "admin_only": "Admins only.",
        "granted": "Granted {n} gens to {uid}. Balance: {bal}.",
        "free_added": "User {uid} added to whitelist.",
        "gallery_empty": "Gallery is empty.",
        "ref_link_fail": "Can't detect bot username.",
    },
    "ro": {
        "start": "Salut! Acesta este iModel 👋\n1) Trimite 1–4 poze\n2) Descrie scena\n3) Primești poza.\n\nComenzi: /help /lang /presets /buy /promo /version /balance /gallery /refer",
        "help": "Cum funcționează:\n• Trimite 1–4 poze\n• Scrie descrierea\n• Primești rezultatul\n\nInterzis: NSFW/copii/celebr.\nComenzi: /buy /promo /balance /clear /tos /privacy /gallery /refer",
        "need_photo": "Trimite mai întâi o poză cu fața.",
        "photo_ok": "Poză primită ✅ Acum descrie scena.",
        "gen": "Generez… ⏳",
        "fail": "Nu am reușit. Încearcă altă descriere.",
        "ready": "Gata ✅",
        "credits_none": "Nu mai ai credite. /buy sau /promo.",
        "choose_lang": "Alege limba:\n/ru  /en  /ro",
        "lang_ru": "Limba setată: Rusă",
        "lang_en": "Limba setată: Engleză",
        "lang_ro": "Limba setată: Română",
        "presets": "Idei:\n• Lângă mașină cu flori\n• Plajă, apus\n• Neon urban\n• Cafenea",
        "blocked": "⛔ Cerere blocată.",
        "btn_balance": "Sold",
        "btn_buy": "Cumpără",
        "buy_title": "💳 Cumpără generații (Stele Telegram):\nPachetele mari sunt mai ieftine!",
        "buy_btn_10": "10 gen — 200★",
        "buy_btn_30": "30 gen — 500★",
        "buy_btn_100": "100 gen — 1200★",
        "bought": "Mulțumesc! +{add}. Total: {all}.",
        "promo_usage": "Folosește: /promo COD",
        "promo_ok": "Promo: +{add}. Total: {all}.",
        "promo_bad": "Promo invalid.",
        "version": "ℹ️ Versiune: {ver}",
        "balance": "Sold: {n} generații{free}",
        "balance_free": " (whitelist — fără scădere)",
        "cleared": "Memoria a fost ștearsă.",
        "tos": "Termeni: pozele sunt folosite doar pentru generare; interzis NSFW/copii/celebr; rezultatul poate fi păstrat până la 72h.",
        "privacy": "Confidențialitate: nu partajăm pozele; /clear șterge temporarele; /forget pentru ștergere totală.",
        "admin_only": "Doar admin.",
        "granted": "Atribuit {n} gen utilizatorului {uid}. Sold: {bal}.",
        "free_added": "Utilizatorul {uid} în whitelist.",
        "gallery_empty": "Galeria este goală.",
        "ref_link_fail": "Nu pot obține username-ul botului.",
    }
}

def L(chat_id: int) -> dict:
    return T.get(USER_LANG.get(chat_id, LANG_DEFAULT), T[LANG_DEFAULT])

# === Auto-lang from Telegram language_code ===
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
BANNED_RE = re.compile(
    r"(nsfw|nude|porn|xxx|дет|ребёнок|ребенок|child|kid|teen|baby|celebrity|public\s*figure)",
    re.IGNORECASE
)
def blocked(text: str) -> bool:
    return bool(BANNED_RE.search(text or ""))

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

# ===================== GPT PROMPT REFINE + ID LOCK ====
SAFE_SUFFIX = (
    # без "portrait only"
    " | safe for work, fully clothed, adult 22+, no minors, no children, no teen, "
    "no nudity, no sexual content, no celebrity, respectful"
)

IDENTITY_LOCK = (
    "Keep the SAME person from the reference photo. Preserve facial identity, "
    "facial structure, bone structure, age, skin tone, natural eye color, hairline and hair color. "
    "Do not alter ethnicity, face proportions, freckles, moles, or scars. "
    "No face reshaping, no beautification filters, no de-aging, no make-up exaggeration."
)

NEGATIVE_LOCK = (
    "different person, identity change, de-aged, child, changed ethnicity, face morph, "
    "over-smooth skin, plastic doll, uncanny face, distorted features, "
    "extra fingers, extra hands, duplicate face, artifacts"
)

def enforce_safe_prompt(user_text: str) -> str:
    text = (user_text or "").strip()
    text = re.sub(r"\b(child|kid|teen|baby|underage|дет(и|ей|ям)?|реб(е|ё)нок)\b", "adult", text, flags=re.I)
    text = re.sub(r"\b(nsfw|nude|nudity|xxx|sex)\b", "", text, flags=re.I)
    if "adult" not in text.lower():
        text = "adult person, " + text
    if SAFE_SUFFIX.lower() not in text.lower():
        text = f"{text}. {SAFE_SUFFIX}"
    return text

def safer_variant(prompt: str) -> str:
    base = re.sub(r",?\s*no celebrity.*$", "", prompt, flags=re.I)
    extra = " | conservative clothing, neutral pose, documentary portrait, editorial style"
    return f"{base}{extra}"

def craft_prompt_gpt(raw_prompt: str, lang: str = "ru") -> str:
    # подготовим безопасный запрос
    safe_raw = enforce_safe_prompt(raw_prompt)

    # Если GPT-рефайн выключен или нет ключа — используем safe_raw
    if os.getenv("DISABLE_GPT_REFINE") == "1" or not OPENAI_API_KEY or OpenAI is None:
        base = safe_raw
    else:
        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
            sys = (
                "You are a prompt writer for a face-preserving image generation pipeline. "
                "Rewrite the user's brief into a concise, vivid, SFW English prompt that "
                "keeps the same person (face identity preserved) and the same intent. "
                "Avoid mentioning minors or celebrities. Ensure: adult subject, fully clothed, SFW."
            )
            user = (
                f"User prompt: {raw_prompt}\n\n"
                "Rewrite to one line. Add environment, mood, lighting, camera. Keep it respectful and SFW."
            )
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

    # ЖЁСТКО ДОБАВЛЯЕМ identity-lock (после GPT), чтобы не «съедалось»
    final = f"{base}. {IDENTITY_LOCK}".strip()
    return final

# ============ Insta-caption (короткий стильный) =======
def _caption_lang_pack(lang: str) -> dict:
    if lang == "en":
        return {
            "brief": ("Write a short stylish Instagram-like caption for an AI photo makeover result. "
                      "Max 120 characters, 1–2 sentences, no hashtags, no emojis unless natural. "
                      "Tone: premium, warm, confident. Avoid explicit sales; hint at transformation."),
            "fallbacks": [
                "Subtle glow, bold vibe. New look, same you.",
                "A little magic, a lot of you.",
                "Soft light, sharper story.",
            ],
        }
    if lang == "ro":
        return {
            "brief": ("Scrie un caption scurt și stilat pentru un rezultat foto AI. "
                      "Max 120 caractere, 1–2 propoziții, fără hashtag-uri, fără emoji artificial. "
                      "Ton: premium, cald, încrezător."),
            "fallbacks": [
                "Strălucire discretă, tu mai clar.",
                "Un strop de magie, același tu.",
                "Lumină fină, poveste puternică.",
            ],
        }
    return {
        "brief": ("Напиши короткий стильный caption к фото с AI-преображением. "
                  "Не более 120 символов, 1–2 фразы, без хештегов, эмодзи только если уместны. "
                  "Тон: премиум, тёплый, уверенный. Без прямых продаж."),
        "fallbacks": [
            "Лёгкое сияние, сильный образ.",
            "Чуть магии — и ты ярче.",
            "Мягкий свет. Чёткий стиль.",
        ],
    }

def generate_instacaption(user_prompt: str, lang: str = "ru") -> str:
    pack = _caption_lang_pack(lang)
    brief = pack["brief"]
    salt = uuid.uuid4().hex[:8]
    if OPENAI_API_KEY and OpenAI is not None:
        try:
            client = OpenAI(api_key=OPENAI_API_KEY)
            sys = ("You are a senior brand copywriter for beauty/fashion. "
                   "Return only the caption text, max 120 chars. No hashtags.")
            usr = (f"{brief}\n\n"
                   f"Context from user: {user_prompt[:180]}\n"
                   f"Variation seed: {salt}")
            r = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "system", "content": sys},
                          {"role": "user", "content": usr}],
                temperature=0.8,
                max_tokens=70,
            )
            txt = (r.choices[0].message.content or "").strip()
            if len(txt) > 140:
                txt = txt[:140].rstrip(" .,;:!?)") + "…"
            return txt or random.choice(pack["fallbacks"])
        except Exception as e:
            print("Caption GPT error:", str(e)[:160])
    return random.choice(pack["fallbacks"])

# ===================== CORE GENERATION =================
def generate_image_from_bytes(img_bytes: bytes, user_prompt: str, lang: str = "ru", seed: Optional[int] = None) -> Optional[bytes]:
    if blocked(user_prompt):
        print("⛔ Заблокировано фильтром")
        return None

    refined = craft_prompt_gpt(user_prompt, lang=lang)
    print(f"→ Генерация запущена. Refined: {refined[:180]}...")

    src_url = s3_put_and_presign(img_bytes, key_prefix="inputs/")
    if not src_url:
        print("→ Не удалось получить S3 presigned URL")
        return None

    # 1) NanoBanana с identity lock / negative prompt / seed
    def try_nano(p: str, seed_val: Optional[int] = None) -> Optional[str]:
        inputs_common = {
            "prompt": p,
            "negative_prompt": NEGATIVE_LOCK,
        }
        if seed_val is not None:
            inputs_common["seed"] = seed_val

        try:
            inp = dict(inputs_common)
            inp["image_input"] = [src_url]
            url = replicate_generate(NANOBANANA_MODEL, inp)
            if url == "SENSITIVE":
                return "SENSITIVE"
            if url:
                print("NanoBanana OK (image_input)")
                return url
        except Exception as e:
            print("NanoBanana image_input exception:", str(e)[:200])

        try:
            inp = dict(inputs_common)
            inp["image"] = src_url
            url = replicate_generate(NANOBANANA_MODEL, inp)
            if url == "SENSITIVE":
                return "SENSITIVE"
            if url:
                print("NanoBanana OK (image)")
                return url
        except Exception as e2:
            print("NanoBanana image exception:", str(e2)[:200])

        return None

    gen_url = try_nano(refined, seed_val=seed)
    if gen_url == "SENSITIVE":
        print("→ Sensitive flag → safer variant")
        gen_url = try_nano(safer_variant(refined), seed_val=seed)

    if not gen_url or gen_url == "SENSITIVE" or not gen_url.startswith("http"):
        print("→ gen_url пустой или sensitive")
        return None

    nano_bytes = _download_with_retries(gen_url)
    if not nano_bytes:
        print("→ не удалось скачать NanoBanana результат")
        return None

    # 2) ESRGAN — бережный апскейл x4plus (без face-enhance)
    try:
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
        print("→ ESRGAN не дал валидный url, отдаю nano_bytes")
        return nano_bytes
    except Exception as e:
        print("ESRGAN error:", str(e)[:200])
        return nano_bytes

# ===================== UI ============================
def kb_actions(chat_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🔄 Ещё",   callback_data="more"),
        InlineKeyboardButton(text="💰 Баланс", callback_data="balance"),
        InlineKeyboardButton(text="⭐ Купить",  callback_data="buy_open"),
    ],
    [
        InlineKeyboardButton(text="✨ Опубликовать в галерее", callback_data="pub_yes"),
    ]])

def main_menu_inline(chat_id: int) -> InlineKeyboardMarkup:
    lang = L(chat_id)
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⭐ " + lang["btn_buy"],      callback_data="buy_open"),
            InlineKeyboardButton(text="💰 " + lang["btn_balance"],  callback_data="balance"),
            InlineKeyboardButton(text="🌐 /lang",                   callback_data="lang_open"),
        ],
        [
            InlineKeyboardButton(text="🎛 /presets", callback_data="presets_open"),
            InlineKeyboardButton(text="🎁 /promo",   callback_data="promo_open"),
            InlineKeyboardButton(text="🆘 /help",    callback_data="help_open"),
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
        provider_token="",  # пусто для Stars
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
    await m.answer(lang["buy_title"], reply_markup=kb)

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
    await m.answer(L(m.chat.id)["bought"].format(add=add, all=USER_CREDITS[m.chat.id]))

# ===================== COMMANDS =======================
@dp.message(Command("version"))
async def cmd_version(m: Message):
    await m.answer(L(m.chat.id)["version"].format(ver=APP_VERSION))

@dp.message(Command("start"))
async def cmd_start(m: Message):
    if m.chat.id not in USER_LANG:
        USER_LANG[m.chat.id] = locale_to_lang(getattr(m.from_user, "language_code", None))

    # deep-link: /start ref_123456
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
        except Exception:
            pass

    USER_CREDITS.setdefault(m.chat.id, FREE_QUOTA)
    USER_SEEN_TEXT.discard(m.chat.id)
    await m.answer(L(m.chat.id)["start"], reply_markup=main_menu_inline(m.chat.id))

@dp.message(Command("help"))
async def cmd_help(m: Message):
    await m.answer(L(m.chat.id)["help"])

@dp.message(Command("lang"))
async def cmd_lang(m: Message):
    await m.answer(L(m.chat.id)["choose_lang"])

@dp.message(Command("ru"))
async def cmd_ru(m: Message):
    USER_LANG[m.chat.id] = "ru"; USER_SEEN_TEXT.add(m.chat.id)
    await m.answer(L(m.chat.id)["lang_ru"], reply_markup=main_menu_inline(m.chat.id))

@dp.message(Command("en"))
async def cmd_en(m: Message):
    USER_LANG[m.chat.id] = "en"; USER_SEEN_TEXT.add(m.chat.id)
    await m.answer(L(m.chat.id)["lang_en"], reply_markup=main_menu_inline(m.chat.id))

@dp.message(Command("ro"))
async def cmd_ro(m: Message):
    USER_LANG[m.chat.id] = "ro"; USER_SEEN_TEXT.add(m.chat.id)
    await m.answer(L(m.chat.id)["lang_ro"], reply_markup=main_menu_inline(m.chat.id))

@dp.message(Command("presets"))
async def cmd_presets(m: Message):
    await m.answer(L(m.chat.id)["presets"])

@dp.message(Command("promo"))
async def cmd_promo(m: Message):
    lang = L(m.chat.id)
    parts = (m.text or "").strip().split(maxsplit=1)
    if len(parts) < 2:
        return await m.answer(lang["promo_usage"])
    code = parts[1].strip().upper()
    promo = PROMO_CODES.get(code)
    if not promo or promo.get("uses", 0) <= 0:
        return await m.answer(lang["promo_bad"])
    add = int(promo.get("add", 0))
    promo["uses"] = max(0, promo["uses"] - 1)
    USER_CREDITS[m.chat.id] = USER_CREDITS.get(m.chat.id, 0) + add
    await m.answer(lang["promo_ok"].format(add=add, all=USER_CREDITS[m.chat.id]))

@dp.message(Command("balance"))
async def cmd_balance(m: Message):
    free = L(m.chat.id)["balance_free"] if is_free_user(m.chat.id, getattr(m.from_user, "username", None)) else ""
    n = USER_CREDITS.get(m.chat.id, FREE_QUOTA)
    await m.answer(L(m.chat.id)["balance"].format(n=n, free=free))

@dp.message(Command("clear"))
async def cmd_clear(m: Message):
    USER_REFS.pop(m.chat.id, None)
    USER_LAST_OUTPUT.pop(m.chat.id, None)
    USER_LAST_PROMPT.pop(m.chat.id, None)
    USER_HISTORY.pop(m.chat.id, None)
    LAST_REF.pop(m.chat.id, None)
    LAST_PHOTO.pop(m.chat.id, None)
    await m.answer(L(m.chat.id)["cleared"])

@dp.message(Command("tos"))
async def cmd_tos(m: Message):
    await m.answer(L(m.chat.id)["tos"])

@dp.message(Command("privacy"))
async def cmd_privacy(m: Message):
    await m.answer(L(m.chat.id)["privacy"])

@dp.message(Command("gallery"))
async def cmd_gallery(m: Message):
    hist = USER_HISTORY.get(m.chat.id, [])
    if not hist:
        return await m.answer(L(m.chat.id)["gallery_empty"])
    items = hist[-GALLERY_LIMIT:]
    if len(items) == 1:
        await m.answer_photo(BufferedInputFile(items[0], filename="imodel_gallery.jpg"), caption="🖼 Галерея (1)")
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
                await m.answer_photo(BufferedInputFile(b, filename=f"g{i}.jpg"), caption=cap)

@dp.message(Command("refer"))
async def cmd_refer(m: Message):
    if not BOT_USERNAME_GLOBAL:
        return await m.answer(L(m.chat.id)["ref_link_fail"])
    my_id = m.chat.id
    link = f"https://t.me/{BOT_USERNAME_GLOBAL}?start=ref_{my_id}"
    st = REF_STATS.get(my_id, {"count": 0, "earned": 0})
    await m.answer(
        "👥 Пригласи друзей и получай бонусные генерации!\n"
        f"Твоя ссылка: {link}\n\n"
        f"Приглашено: {st['count']}\n"
        f"Получено бонусов: {st['earned']} генераций",
        disable_web_page_preview=True
    )

# ==== ADMIN ====
@dp.message(Command("grant"))
async def cmd_grant(m: Message):
    if not is_admin(m.from_user.id, getattr(m.from_user, "username", None)):
        return await m.answer(L(m.chat.id)["admin_only"])
    parts = (m.text or "").split()
    if len(parts) < 3:
        return await m.answer("Usage: /grant <user_id> <amount>")
    try:
        uid = int(parts[1]); amt = int(parts[2])
    except Exception:
        return await m.answer("Usage: /grant <user_id> <amount>")
    USER_CREDITS[uid] = USER_CREDITS.get(uid, 0) + amt
    await m.answer(L(m.chat.id)["granted"].format(n=amt, uid=uid, bal=USER_CREDITS[uid]))

@dp.message(Command("free"))
async def cmd_free(m: Message):
    if not is_admin(m.from_user.id, getattr(m.from_user, "username", None)):
        return await m.answer(L(m.chat.id)["admin_only"])
    parts = (m.text or "").split()
    if len(parts) < 2:
        return await m.answer("Usage: /free <user_id>")
    try:
        uid = int(parts[1])
    except Exception:
        return await m.answer("Usage: /free <user_id>")
    FREE_USERS.add(uid)
    await m.answer(L(m.chat.id)["free_added"].format(uid=uid))

# ======= INLINE «псевдо-команды» из стартовой панели =======
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

# ===== Публикация в галерею (альбом до/после) =====
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
    await c.answer("Опубликовано")

# ===================== FLOW: PHOTO + TEXT ==============
@dp.message(F.photo)
async def on_photo(m: Message):
    if m.chat.id not in USER_LANG:
        USER_LANG[m.chat.id] = locale_to_lang(getattr(m.from_user, "language_code", None))

    f = await bot.get_file(m.photo[-1].file_id)
    b = await bot.download_file(f.file_path)
    img_bytes = b.read()
    USER_REFS.setdefault(m.chat.id, [])
    USER_REFS[m.chat.id] = (USER_REFS[m.chat.id] + [img_bytes])[-4:]
    LAST_REF[m.chat.id] = img_bytes

    caption = (m.caption or "").strip()
    if not caption:
        return await m.answer(L(m.chat.id)["photo_ok"])
    if blocked(caption):
        return await m.answer(L(m.chat.id)["blocked"])

    USER_CREDITS.setdefault(m.chat.id, FREE_QUOTA)
    if not has_credit(m.chat.id, getattr(m.from_user, "username", None)):
        return await m.answer(L(m.chat.id)["credits_none"])

    wait = await m.answer(L(m.chat.id)["gen"])
    final_bytes = generate_image_from_bytes(
        img_bytes, caption, lang=USER_LANG.get(m.chat.id, LANG_DEFAULT),
        seed=(hash(m.chat.id) % 10_000_000)
    )
    if not final_bytes:
        return await wait.edit_text(L(m.chat.id)["fail"])

    if not is_free_user(m.chat.id, getattr(m.from_user, "username", None)):
        USER_CREDITS[m.chat.id] -= 1
    USER_LAST_OUTPUT[m.chat.id] = final_bytes
    USER_LAST_PROMPT[m.chat.id] = caption
    LAST_PHOTO[m.chat.id] = final_bytes

    # история /gallery
    hist = USER_HISTORY.setdefault(m.chat.id, [])
    hist.append(final_bytes)
    if len(hist) > GALLERY_LIMIT:
        del hist[:-GALLERY_LIMIT]

    await wait.delete()
    await m.answer_photo(
        photo=BufferedInputFile(final_bytes, filename="imodel_result.jpg"),
        caption="✅",
        reply_markup=kb_actions(m.chat.id),
    )

@dp.message(F.text & ~F.text.startswith("/"))
async def on_prompt(m: Message):
    text = m.text.strip()

    if m.chat.id not in USER_LANG:
        USER_LANG[m.chat.id] = locale_to_lang(getattr(m.from_user, "language_code", None))
    if m.chat.id not in USER_SEEN_TEXT:
        USER_SEEN_TEXT.add(m.chat.id)
        if USER_LANG.get(m.chat.id, LANG_DEFAULT) == LANG_DEFAULT:
            USER_LANG[m.chat.id] = detect_lang(text)

    if blocked(text):
        return await m.answer(L(m.chat.id)["blocked"])

    refs = USER_REFS.get(m.chat.id, [])
    if not refs:
        return await m.answer(L(m.chat.id)["need_photo"])

    USER_CREDITS.setdefault(m.chat.id, FREE_QUOTA)
    if not has_credit(m.chat.id, getattr(m.from_user, "username", None)):
        return await m.answer(L(m.chat.id)["credits_none"])

    wait = await m.answer(L(m.chat.id)["gen"])
    ref = refs[-1]
    final_bytes = generate_image_from_bytes(
        ref, text, lang=USER_LANG.get(m.chat.id, LANG_DEFAULT),
        seed=(hash(m.chat.id) % 10_000_000)
    )
    if not final_bytes:
        return await wait.edit_text(L(m.chat.id)["fail"])

    if not is_free_user(m.chat.id, getattr(m.from_user, "username", None)):
        USER_CREDITS[m.chat.id] -= 1
    USER_LAST_OUTPUT[m.chat.id] = final_bytes
    USER_LAST_PROMPT[m.chat.id] = text
    LAST_PHOTO[m.chat.id] = final_bytes

    # история
    hist = USER_HISTORY.setdefault(m.chat.id, [])
    hist.append(final_bytes)
    if len(hist) > GALLERY_LIMIT:
        del hist[:-GALLERY_LIMIT]

    await wait.delete()
    await m.answer_photo(
        photo=BufferedInputFile(final_bytes, filename="imodel_result.jpg"),
        caption="✅",
        reply_markup=kb_actions(m.chat.id),
    )

# ===================== WEBHOOK ========================
@app.on_event("startup")
async def on_startup():
    print(f"=== {APP_VERSION} ===")
    print("ADMINS (IDs):", ADMIN_IDS)
    print("ADMINS (usernames):", ADMIN_USERNAMES)
    if GALLERY_CHANNEL_ID:
        print("Gallery channel:", GALLERY_CHANNEL_ID)

    me = await bot.get_me()
    global BOT_USERNAME_GLOBAL
    BOT_USERNAME_GLOBAL = me.username

    if BOT_TOKEN and WEBHOOK_BASE:
        url = f"{WEBHOOK_BASE}/?secret={WEBHOOK_SECRET}"
        await bot.set_webhook(url, secret_token=WEBHOOK_SECRET)
        print(f"✅ Вебхук установлен: {url}")
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
    update = Update.model_validate(data)
    await dp.feed_update(bot, update)
    return {"ok": True}
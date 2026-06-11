# app.py — iModel v2.7.0
# Copy-mode v2 (Scene Lock) + Identity Lock
# Остальное: AutoLang + GPT refine + S3 + Replicate NanoBanana
# Stars + Whitelist/Admin unlimited + Promo + 3 langs + pricing + gallery + refer
# Безопасные отправки; Видео/анимация отключены. Доставка — байты.

from __future__ import annotations

import os
import io
import json
import re
import time
import uuid
import base64
import random
import hashlib
import hmac
import asyncio
import html as html_lib
from urllib.parse import parse_qsl
from typing import Optional, Dict, List, Set, Any, Tuple

import requests
from fastapi import FastAPI, Request, BackgroundTasks
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
    InputMediaPhoto, WebAppInfo,
)
from aiogram.exceptions import TelegramForbiddenError, TelegramNotFound, TelegramBadRequest

import replicate
import boto3
from botocore.config import Config

try:
    import psycopg
except Exception:
    psycopg = None

try:
    from PIL import Image, ImageFilter, ImageStat
except Exception:
    Image = None
    ImageFilter = None
    ImageStat = None

# ---------- OpenAI (GPT + Vision) ----------
try:
    from openai import OpenAI
except Exception:
    OpenAI = None

APP_VERSION = "iModel 2.7.0"

# ===================== ENV ==========================
BOT_TOKEN      = os.getenv("BOT_TOKEN", "")
WEBHOOK_BASE   = os.getenv("WEBHOOK_BASE", "").rstrip("/")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
if not WEBHOOK_SECRET:
    print("⚠️ WEBHOOK_SECRET is not set — Telegram webhook will reject requests")
WEBHOOK_ALLOW_QUERY_SECRET = os.getenv("WEBHOOK_ALLOW_QUERY_SECRET", "0") == "1"
WEBHOOK_URL = f"{WEBHOOK_BASE}/" if WEBHOOK_BASE else ""


REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN", "")
os.environ["REPLICATE_API_TOKEN"] = REPLICATE_API_TOKEN

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL   = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_MODEL_VISION = os.getenv("OPENAI_MODEL_VISION", OPENAI_MODEL)

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or ""
DB_READY = False

# Auto posts to group (educational, witty)
GROUP_POSTS_ENABLED   = os.getenv("GROUP_POSTS_ENABLED", "0") == "1"
GROUP_POST_MIN_HOURS  = float(os.getenv("GROUP_POST_MIN_HOURS", "2"))
GROUP_POST_MAX_HOURS  = float(os.getenv("GROUP_POST_MAX_HOURS", "3"))
# Either a single lang like "ru" or a comma-list like "ru,ro" to rotate
GROUP_POST_LANGS_RAW  = os.getenv("GROUP_POST_LANGS", os.getenv("GROUP_POST_LANG", "ru,ro"))
_GROUP_LANGS          = [x.strip().lower() for x in GROUP_POST_LANGS_RAW.replace(";",",").split(",") if x.strip()]
if not _GROUP_LANGS:
    _GROUP_LANGS = ["ru"]
_GROUP_LANG_IDX = 0
# Quiet hours: do NOT post between END..START (e.g., 22..8)
GROUP_POST_START_HOUR = int(os.getenv("GROUP_POST_START_HOUR", "8"))
GROUP_POST_END_HOUR   = int(os.getenv("GROUP_POST_END_HOUR", "22"))
# Debug: force fixed interval in minutes and ignore quiet hours if >0
GROUP_POST_EVERY_MINUTES = int(os.getenv("GROUP_POST_EVERY_MINUTES", "0"))
GROUP_POST_TEXT_ONLY = os.getenv("GROUP_POST_TEXT_ONLY", "0") == "1"
GROUP_POST_LOOP_RUNNING = False
GROUP_POST_LAST_AT: float = 0.0

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
    "nudges_sent": 0,
    "nudges_errors": 0,
    "nudges_granted": 0,
    "jobs_created": 0,
    "jobs_done": 0,
    "jobs_failed": 0,
    "delivery_photo_ok": 0,
    "delivery_document_ok": 0,
    "delivery_failed": 0,
    "generation_latency_total_ms": 0,
    "generation_latency_count": 0,
}
STATS_USERS: Set[int] = set()
STATS_USERS_INFO: Dict[int, Dict[str, object]] = {}

def _safe_user_hash(uid: Optional[int]) -> str:
    if not uid:
        return ""
    salt = WEBHOOK_SECRET or BOT_TOKEN or "imodel"
    return hashlib.sha256(f"{uid}:{salt[:12]}".encode("utf-8")).hexdigest()[:16]

def log_event(event: str, **fields: Any):
    payload: Dict[str, Any] = {
        "ts": round(time.time(), 3),
        "event": event,
        "app": APP_VERSION,
    }
    for k, v in fields.items():
        if v is None:
            continue
        if k in {"chat_id", "user_id", "uid"} or k.endswith("_uid"):
            payload[f"{k}_hash"] = _safe_user_hash(int(v)) if str(v).lstrip("-").isdigit() else ""
            continue
        if isinstance(v, (str, int, float, bool, list, dict)):
            payload[k] = v
        else:
            payload[k] = str(v)
    print(json.dumps(payload, ensure_ascii=False), flush=True)

def _db_connect():
    if not DATABASE_URL or psycopg is None:
        return None
    return psycopg.connect(DATABASE_URL, autocommit=True)

def _db_execute(sql: str, params: tuple = ()) -> bool:
    if not DB_READY:
        return False
    try:
        with _db_connect() as conn:
            if conn is None:
                return False
            with conn.cursor() as cur:
                cur.execute(sql, params)
        return True
    except Exception as e:
        log_event("db_execute_error", error=str(e)[:180])
        return False

def _db_fetchall(sql: str, params: tuple = ()) -> List[tuple]:
    if not DB_READY:
        return []
    try:
        with _db_connect() as conn:
            if conn is None:
                return []
            with conn.cursor() as cur:
                cur.execute(sql, params)
                return list(cur.fetchall() or [])
    except Exception as e:
        log_event("db_fetch_error", error=str(e)[:180])
        return []

def db_init():
    global DB_READY
    if not DATABASE_URL or psycopg is None:
        DB_READY = False
        if DATABASE_URL and psycopg is None:
            log_event("db_disabled", reason="psycopg_not_installed")
        return
    try:
        with _db_connect() as conn:
            if conn is None:
                DB_READY = False
                return
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS imodel_users (
                        uid BIGINT PRIMARY KEY,
                        username TEXT,
                        info_json TEXT NOT NULL DEFAULT '{}',
                        role TEXT NOT NULL DEFAULT 'user',
                        grants_json TEXT NOT NULL DEFAULT '[]',
                        created_at DOUBLE PRECISION NOT NULL,
                        updated_at DOUBLE PRECISION NOT NULL
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS imodel_credits (
                        uid BIGINT PRIMARY KEY,
                        credits INTEGER NOT NULL,
                        updated_at DOUBLE PRECISION NOT NULL
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS imodel_stats_totals (
                        key TEXT PRIMARY KEY,
                        value BIGINT NOT NULL
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS imodel_stats_daily (
                        day TEXT NOT NULL,
                        key TEXT NOT NULL,
                        value BIGINT NOT NULL,
                        PRIMARY KEY (day, key)
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS imodel_jobs (
                        job_id TEXT PRIMARY KEY,
                        kind TEXT NOT NULL,
                        status TEXT NOT NULL,
                        chat_id BIGINT,
                        username TEXT,
                        prompt TEXT,
                        model TEXT,
                        timeline_json TEXT NOT NULL DEFAULT '[]',
                        result_json TEXT NOT NULL DEFAULT '{}',
                        error TEXT,
                        created_at DOUBLE PRECISION NOT NULL,
                        updated_at DOUBLE PRECISION NOT NULL
                    )
                """)
                cur.execute("ALTER TABLE imodel_jobs ADD COLUMN IF NOT EXISTS result_json TEXT NOT NULL DEFAULT '{}'")
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS imodel_audit_log (
                        id BIGSERIAL PRIMARY KEY,
                        actor_uid BIGINT,
                        action TEXT NOT NULL,
                        target_uid BIGINT,
                        data_json TEXT NOT NULL DEFAULT '{}',
                        created_at DOUBLE PRECISION NOT NULL
                    )
                """)
        DB_READY = True
        log_event("db_ready", backend="postgres")
    except Exception as e:
        DB_READY = False
        log_event("db_init_error", error=str(e)[:240])

def _db_save_stats_totals():
    if not DB_READY:
        return
    rows = [(k, int(v)) for k, v in STATS.items() if k != "start_ts" and isinstance(v, (int, float))]
    for k, v in rows:
        _db_execute(
            "INSERT INTO imodel_stats_totals(key, value) VALUES (%s, %s) "
            "ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value",
            (k, v),
        )

def _db_load_stats_totals() -> Dict[str, int]:
    rows = _db_fetchall("SELECT key, value FROM imodel_stats_totals")
    return {str(k): int(v) for k, v in rows}

def _db_save_stats_daily():
    if not DB_READY:
        return
    for day, vals in STATS_DAILY.items():
        for k, v in vals.items():
            _db_execute(
                "INSERT INTO imodel_stats_daily(day, key, value) VALUES (%s, %s, %s) "
                "ON CONFLICT (day, key) DO UPDATE SET value = EXCLUDED.value",
                (day, k, int(v)),
            )

def _db_load_stats_daily() -> Dict[str, Dict[str, int]]:
    out: Dict[str, Dict[str, int]] = {}
    for day, key, value in _db_fetchall("SELECT day, key, value FROM imodel_stats_daily"):
        out.setdefault(str(day), {})[str(key)] = int(value)
    return out

def _db_save_user(uid: int, info: Dict[str, object]):
    if not DB_READY:
        return
    role = USER_ROLES.get(uid) or role_for_user(uid, str(info.get("username") or "") or None)
    grants = sorted(USER_GRANTS.get(uid, set()))
    _db_execute(
        "INSERT INTO imodel_users(uid, username, info_json, role, grants_json, created_at, updated_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (uid) DO UPDATE SET username = EXCLUDED.username, info_json = EXCLUDED.info_json, "
        "role = EXCLUDED.role, grants_json = EXCLUDED.grants_json, updated_at = EXCLUDED.updated_at",
        (
            uid,
            str(info.get("username") or "")[:64],
            json.dumps(info, ensure_ascii=False),
            role,
            json.dumps(grants, ensure_ascii=False),
            float(info.get("first_seen", time.time()) or time.time()),
            time.time(),
        ),
    )

def _db_load_users() -> Dict[int, Dict[str, object]]:
    out: Dict[int, Dict[str, object]] = {}
    rows = _db_fetchall("SELECT uid, info_json, role, grants_json FROM imodel_users")
    for uid, info_json, role, grants_json in rows:
        try:
            iuid = int(uid)
            info = json.loads(info_json or "{}")
            out[iuid] = info
            loaded_role = str(role or "user")
            username = str(info.get("username") or "")
            if iuid in ADMIN_IDS:
                loaded_role = "owner"
            elif username and username.lower() in ADMIN_USERNAMES and loaded_role == "user":
                loaded_role = "admin"
            USER_ROLES[iuid] = loaded_role
            USER_GRANTS[iuid] = set(json.loads(grants_json or "[]"))
        except Exception:
            continue
    return out

def _db_save_credit(uid: int, credits: int):
    if not DB_READY:
        return
    _db_execute(
        "INSERT INTO imodel_credits(uid, credits, updated_at) VALUES (%s, %s, %s) "
        "ON CONFLICT (uid) DO UPDATE SET credits = EXCLUDED.credits, updated_at = EXCLUDED.updated_at",
        (uid, int(credits), time.time()),
    )

def _db_load_credits() -> Dict[int, int]:
    return {int(uid): int(credits) for uid, credits in _db_fetchall("SELECT uid, credits FROM imodel_credits")}

def _db_job_to_dict(row: tuple) -> Dict[str, Any]:
    (
        job_id, kind, status, chat_id, username, prompt, model,
        timeline_json, result_json, error, created_at, updated_at,
    ) = row
    try:
        timeline = json.loads(timeline_json or "[]")
    except Exception:
        timeline = []
    try:
        result = json.loads(result_json or "{}")
    except Exception:
        result = {}
    job: Dict[str, Any] = {
        "job_id": str(job_id),
        "kind": str(kind or "generation"),
        "status": str(status or "queued"),
        "chat_id": int(chat_id) if chat_id is not None else None,
        "username": str(username or ""),
        "prompt": str(prompt or ""),
        "model": str(model or NANOBANANA_MODEL),
        "timeline": timeline,
        "error": str(error or ""),
        "created_at": float(created_at or time.time()),
        "updated_at": float(updated_at or time.time()),
    }
    if isinstance(result, dict):
        job.update(result)
    return job

def _db_load_recent_jobs(limit: int = 50) -> List[Dict[str, Any]]:
    rows = _db_fetchall(
        "SELECT job_id, kind, status, chat_id, username, prompt, model, timeline_json, result_json, error, created_at, updated_at "
        "FROM imodel_jobs ORDER BY updated_at DESC LIMIT %s",
        (int(limit),),
    )
    return [_db_job_to_dict(row) for row in rows]

def _db_load_job(job_id: str) -> Optional[Dict[str, Any]]:
    rows = _db_fetchall(
        "SELECT job_id, kind, status, chat_id, username, prompt, model, timeline_json, result_json, error, created_at, updated_at "
        "FROM imodel_jobs WHERE job_id = %s LIMIT 1",
        (job_id,),
    )
    return _db_job_to_dict(rows[0]) if rows else None

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
        _db_save_stats_totals()
        try:
            _s3_put_text(STATE_PREFIX + "stats_totals.json", json.dumps(to_save, ensure_ascii=False))
        except Exception:
            pass
    except Exception as e:
        print("[stats] save totals error:", str(e)[:160])

def stats_save_daily():
    _save_json_atomic(STATS_DAILY_FILE, STATS_DAILY)
    _db_save_stats_daily()
    try:
        _s3_put_text(STATE_PREFIX + "stats_daily.json", json.dumps(STATS_DAILY, ensure_ascii=False))
    except Exception:
        pass

def users_save(uid: Optional[int] = None):
    try:
        _save_json_atomic(USERS_FILE, STATS_USERS_INFO)
        if uid is not None and uid in STATS_USERS_INFO:
            _db_save_user(uid, STATS_USERS_INFO[uid])
        elif DB_READY:
            for u, info in STATS_USERS_INFO.items():
                _db_save_user(int(u), info)
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
        db_loaded = _db_load_stats_totals()
        if db_loaded:
            loaded = db_loaded
        else:
            txt = _s3_get_text(STATE_PREFIX + "stats_totals.json")
            if txt:
                loaded = json.loads(txt)
        if loaded is None and os.path.exists(STATS_TOTALS_FILE):
            with open(STATS_TOTALS_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
        if loaded:
            for k, v in loaded.items():
                try:
                    if isinstance(v, (int, float)):
                        STATS[k] = v
                except Exception:
                    pass
            _db_save_stats_totals()
    except Exception as e:
        print("[stats] load totals error:", str(e)[:160])
    try:
        db_daily = _db_load_stats_daily()
        if db_daily:
            STATS_DAILY = db_daily
        else:
            txt = _s3_get_text(STATE_PREFIX + "stats_daily.json")
            if txt:
                STATS_DAILY = json.loads(txt) or {}
            elif os.path.exists(STATS_DAILY_FILE):
                with open(STATS_DAILY_FILE, "r", encoding="utf-8") as f:
                    STATS_DAILY = json.load(f) or {}
            else:
                STATS_DAILY = {}
        if DB_READY and STATS_DAILY:
            _db_save_stats_daily()
    except Exception as e:
        print("[stats] load daily error:", str(e)[:160])
        STATS_DAILY = {}
    try:
        data = None
        db_users = _db_load_users()
        if db_users:
            data = db_users
        else:
            txt = _s3_get_text(STATE_PREFIX + "users.json")
            if txt:
                data = json.loads(txt) or {}
        if data is None and os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
        if data:
            for uid_str, info in data.items():
                try:
                    STATS_USERS_INFO[int(uid_str)] = info
                except Exception:
                    continue
            users_save()
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
        users_save(uid)
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
        users_save(uid)
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

# Replicate models — primary chain: InstantID → PhotoMaker → NanoBanana (fallback)
# Version hashes pinned to avoid 404 on "latest" lookups
NANOBANANA_MODEL  = os.getenv("NANOBANANA_MODEL", "google/nano-banana")
INSTANTID_MODEL   = os.getenv("INSTANTID_MODEL",  "zsxkib/instant-id:2e4785a4d80dadf580077b2244c8d7c05d8e3faac04a04c02d8e099dd2876789")
PHOTOMAKER_MODEL  = os.getenv("PHOTOMAKER_MODEL", "tencentarc/photomaker:ddfc2b08d209f9fa8c1eca692712918bd449f695dabb4a958da31802a9570fe4")
GFPGAN_MODEL      = os.getenv("GFPGAN_MODEL",     "tencentarc/gfpgan:0fbacf7afc6c144e5be9767cff80f25aff23e52b0708f17e20f9879b2f21516c")
CODEFORMER_MODEL  = os.getenv("CODEFORMER_MODEL", "sczhou/codeformer:cc4956dd26fa5a7185d5660cc9100fab1b8070a1d1654a8bb5eb6d443b020bb2")
FACESWAP_MODEL    = os.getenv("FACESWAP_MODEL",   "codeplugtech/face-swap:278a81e7ebb22db98bcba54de985d22cc1abeead2754eb1f2af717247be69b34")

# Language / quotas
LANG_DEFAULT = os.getenv("LANG_DEFAULT", "en")
FREE_QUOTA   = int(os.getenv("FREE_QUOTA", "3"))

# Onboarding demo photo (Telegram file_id or public HTTPS URL; leave empty to skip)
DEMO_PHOTO = os.getenv("DEMO_PHOTO", "")

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
    PUBLISH_GROUP_ID = int(PUBLISH_GROUP_ID) if PUBLISH_GROUP_ID else None
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

VALID_ROLES = {"owner", "admin", "operator", "support", "publisher", "user", "banned"}
ROLE_GRANTS: Dict[str, Set[str]] = {
    "owner": {
        "admin.view", "users.manage", "credits.grant", "jobs.view", "jobs.retry",
        "broadcast.send", "gallery.publish", "promos.manage", "logs.view",
    },
    "admin": {
        "admin.view", "users.manage", "credits.grant", "jobs.view", "jobs.retry",
        "gallery.publish", "promos.manage", "logs.view",
    },
    "operator": {"admin.view", "jobs.view", "jobs.retry", "logs.view"},
    "support": {"admin.view", "jobs.view"},
    "publisher": {"gallery.publish"},
    "user": set(),
    "banned": set(),
}
USER_ROLES: Dict[int, str] = {}
USER_GRANTS: Dict[int, Set[str]] = {}
AUDIT_LOG: List[Dict[str, Any]] = []
JOBS: Dict[str, Dict[str, Any]] = {}

def is_admin(uid: int, username: Optional[str] = None) -> bool:
    if uid in ADMIN_IDS:
        return True
    if username:
        return username.lower() in ADMIN_USERNAMES
    return False

def role_for_user(uid: int, username: Optional[str] = None) -> str:
    if uid in USER_ROLES:
        return USER_ROLES[uid]
    if uid in ADMIN_IDS:
        return "owner"
    if username and username.lower() in ADMIN_USERNAMES:
        return "admin"
    return "user"

def grants_for_user(uid: int, username: Optional[str] = None) -> Set[str]:
    role = role_for_user(uid, username)
    return set(ROLE_GRANTS.get(role, set())) | set(USER_GRANTS.get(uid, set()))

def has_grant(uid: int, username: Optional[str], grant: str) -> bool:
    return grant in grants_for_user(uid, username)

def audit_log(actor_uid: Optional[int], action: str, target_uid: Optional[int] = None, **data: Any):
    entry = {
        "actor_uid": actor_uid,
        "action": action,
        "target_uid": target_uid,
        "data": data,
        "created_at": time.time(),
    }
    AUDIT_LOG.append(entry)
    if len(AUDIT_LOG) > 500:
        del AUDIT_LOG[:-500]
    if DB_READY:
        _db_execute(
            "INSERT INTO imodel_audit_log(actor_uid, action, target_uid, data_json, created_at) VALUES (%s, %s, %s, %s, %s)",
            (actor_uid, action, target_uid, json.dumps(data, ensure_ascii=False), entry["created_at"]),
        )
    log_event("audit", actor_uid=actor_uid, action=action, target_uid=target_uid, data=data)

def _job_result_json(job: Dict[str, Any]) -> str:
    result = {}
    for key in ("output_url", "output_bytes", "delivery_message_id"):
        if key in job:
            result[key] = job.get(key)
    return json.dumps(result, ensure_ascii=False)

def _db_save_job(job: Dict[str, Any]):
    if not DB_READY:
        return
    _db_execute(
        "INSERT INTO imodel_jobs(job_id, kind, status, chat_id, username, prompt, model, timeline_json, result_json, error, created_at, updated_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
        "ON CONFLICT (job_id) DO UPDATE SET status = EXCLUDED.status, chat_id = EXCLUDED.chat_id, "
        "username = EXCLUDED.username, prompt = EXCLUDED.prompt, model = EXCLUDED.model, "
        "timeline_json = EXCLUDED.timeline_json, result_json = EXCLUDED.result_json, "
        "error = EXCLUDED.error, updated_at = EXCLUDED.updated_at",
        (
            job.get("job_id"),
            job.get("kind", "generation"),
            job.get("status", "queued"),
            job.get("chat_id"),
            str(job.get("username") or "")[:64],
            str(job.get("prompt") or "")[:4000],
            str(job.get("model") or NANOBANANA_MODEL),
            json.dumps(job.get("timeline") or [], ensure_ascii=False),
            _job_result_json(job),
            str(job.get("error") or "")[:1000],
            float(job.get("created_at") or time.time()),
            float(job.get("updated_at") or time.time()),
        ),
    )

def record_job(job_id: Optional[str] = None, **updates: Any) -> Dict[str, Any]:
    jid = job_id or uuid.uuid4().hex
    job = JOBS.setdefault(jid, {"job_id": jid, "created_at": time.time(), "timeline": []})
    job.update(updates)
    job["updated_at"] = time.time()
    _db_save_job(job)
    log_event("job_record", job_id=jid, status=job.get("status"), kind=job.get("kind"), chat_id=job.get("chat_id"))
    return job

def job_event(job_id: Optional[str], event: str, **fields: Any):
    if not job_id:
        return
    job = JOBS.setdefault(job_id, {"job_id": job_id, "created_at": time.time(), "timeline": []})
    item = {"ts": round(time.time(), 3), "event": event}
    item.update({k: v for k, v in fields.items() if v is not None})
    timeline = job.setdefault("timeline", [])
    if isinstance(timeline, list):
        timeline.append(item)
        if len(timeline) > 40:
            del timeline[:-40]
    job["updated_at"] = time.time()
    _db_save_job(job)
    log_event(event, job_id=job_id, chat_id=job.get("chat_id"), **fields)

def load_recent_jobs_from_db(limit: int = 50):
    if not DB_READY:
        return
    for job in reversed(_db_load_recent_jobs(limit)):
        JOBS[str(job["job_id"])] = job

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
USER_LAST_PROMPT: Dict[int, str]   = {}   # последний prompt (ввод пользователя/сцена)
USER_LAST_REFINED_PROMPT: Dict[int, str] = {}  # фактический GPT-уточнённый промпт
USER_LANG: Dict[int, str]          = {}   # язык
USER_CREDITS: Dict[int, int]       = {}   # баланс
USER_SEEN_TEXT: Set[int]           = set()
USER_ONBOARDED: Set[int]           = set()
USER_LAST_JOB: Dict[int, str]      = {}
USER_LAST_ACTIVE: Dict[int, float] = {}   # timestamp последней активности — для TTL cleanup

# Persistent storage for credits
DATA_DIR = os.getenv("DATA_DIR", "data")
CREDITS_FILE = os.getenv("CREDITS_FILE", os.path.join(DATA_DIR, "credits.json"))

def _credits_save():
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = CREDITS_FILE + ".tmp"
        payload = json.dumps({str(k): int(v) for k, v in USER_CREDITS.items()}, ensure_ascii=False)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp, CREDITS_FILE)
        if DB_READY:
            for uid, credits in USER_CREDITS.items():
                _db_save_credit(int(uid), int(credits))
        _s3_put_text(STATE_PREFIX + "credits.json", payload)
    except Exception as e:
        print("[credits] save error:", str(e)[:160])

def _credits_load():
    try:
        db_credits = _db_load_credits()
        if db_credits:
            USER_CREDITS.update(db_credits)
            return
        # Prefer S3 state if available
        txt = _s3_get_text(STATE_PREFIX + "credits.json")
        if txt:
            data = json.loads(txt)
            for k, v in (data or {}).items():
                try:
                    USER_CREDITS[int(k)] = int(v)
                except Exception:
                    continue
        elif os.path.exists(CREDITS_FILE):
            with open(CREDITS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for k, v in (data or {}).items():
                try:
                    USER_CREDITS[int(k)] = int(v)
                except Exception:
                    continue
        if DB_READY and USER_CREDITS:
            for uid, credits in USER_CREDITS.items():
                _db_save_credit(int(uid), int(credits))
    except Exception as e:
        print("[credits] load error:", str(e)[:160])

def ensure_user_credit(uid: int):
    if uid not in USER_CREDITS:
        USER_CREDITS[uid] = FREE_QUOTA
        _credits_save()

_credits_load()

# Thread-safe credit operations (prevents double-spend on concurrent requests)
_credits_lock = asyncio.Lock()

async def _try_use_credit(uid: int, username: Optional[str] = None) -> bool:
    """Atomically check and pre-consume one credit. Returns False if balance is 0."""
    async with _credits_lock:
        if is_free_user(uid, username):
            return True
        if uid not in USER_CREDITS:
            USER_CREDITS[uid] = FREE_QUOTA
        if USER_CREDITS[uid] <= 0:
            return False
        USER_CREDITS[uid] -= 1
    _credits_save()  # outside lock — disk/network I/O
    return True

async def _refund_credit(uid: int, username: Optional[str] = None):
    """Refund one credit when generation fails after pre-consume."""
    if is_free_user(uid, username):
        return
    async with _credits_lock:
        USER_CREDITS[uid] = USER_CREDITS.get(uid, 0) + 1
    _credits_save()

# публикация до/после
LAST_REF: Dict[int, bytes]   = {}
LAST_PHOTO: Dict[int, bytes] = {}
# Deduplication of published albums (md5 keys with TTL)
RECENT_PUB: Dict[str, float] = {}
RECENT_PUB_TTL = 600.0  # 10 minutes

# Style share tokens (deep-links)
STYLE_SHARES: Dict[str, Dict[str, object]] = {}
# prompt-share removed

# Copy Mode
USER_COPY_MODE: Set[int]         = set()
USER_COPY_STYLE: Dict[int, bytes]= {}
USER_COPY_PROMPT: Dict[int, str] = {}

# Swap Mode (face swap into arbitrary target photo)
USER_SWAP_MODE: Set[int]         = set()

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
REF_BONUS_NEW  = int(os.getenv("REF_BONUS_NEW", "3"))
REF_BONUS_REF  = int(os.getenv("REF_BONUS_REF", "3"))
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
    Preset("studio_soft", "📸 Студия", "📸 Studio", "📸 Studiou", "📸 Studio",
           "professional studio portrait, softbox key light at 45 degrees, white seamless backdrop, 85mm f/1.8, crisp skin detail, catchlight in eyes, editorial magazine quality, sharp focus"),
    Preset("cinematic", "🎬 Кинематик", "🎬 Cinematic", "🎬 Cinematic", "🎬 Cinematisch",
           "cinematic film portrait, teal and orange color grade, strong rim light, shallow depth of field, anamorphic lens flare, dramatic moody atmosphere, 35mm film"),
    Preset("golden_hour", "🌅 Голден-ауэр", "🌅 Golden Hour", "🌅 Ora de aur", "🌅 Goldene Stunde",
           "outdoor portrait at golden hour sunset, warm orange backlight, sun halo, soft bokeh background, dreamy pastel sky, natural skin tones, filmic"),
    Preset("editorial_highkey", "🧴 Эдиториал", "🧴 Editorial", "🧴 Editorial", "🧴 Editorial High‑Key",
           "high-key editorial fashion portrait, clean white studio backdrop, dual softbox fill, glossy highlights, minimal shadows, Vogue magazine style, precise focus"),
    Preset("bw_film", "⚫️ Ч/Б Плёнка", "⚫️ B/W Film", "⚫️ Film B/N", "⚫️ S/W Film",
           "black and white analog film portrait, Ilford HP5 grain, rich mid-tone contrast, luminous highlights, deep shadows, timeless classic, dramatic mood"),
    Preset("kodak_portra", "🎞 Portra", "🎞 Portra", "🎞 Portra", "🎞 Portra",
           "Kodak Portra 400 film portrait, warm creamy skin tones, gentle saturation, soft halation, authentic grain texture, natural light, 50mm lens"),
    Preset("beauty_dish", "💄 Бьюти", "💄 Beauty", "💄 Beauty", "💄 Beauty",
           "beauty close-up portrait, large beauty dish overhead, soft ring catchlights, flawless luminous skin, glossy lips, precise editorial makeup, sharp focus on eyes"),
    Preset("headshot", "👔 Хэдшот", "👔 Headshot", "👔 Portret CV", "👔 Headshot",
           "professional corporate headshot, neutral mid-gray backdrop, flattering 45-degree key light, 85mm f/2.8, crisp focus, confident expression, LinkedIn-ready"),
    Preset("neon_night", "🌃 Неон", "🌃 Neon Night", "🌃 Noapte Neon", "🌃 Neon Nacht",
           "night city portrait, vibrant neon signs, cyan and magenta light spill, wet pavement reflections, shallow cinematic bokeh, cyberpunk atmosphere"),
    Preset("cafe", "☕️ Кафе", "☕️ Cafe", "☕️ Cafenea", "☕️ Café",
           "cozy cafe lifestyle portrait, warm tungsten ambient light, string lights bokeh, wooden interior, candid relaxed mood, 35mm f/2, muted warm tones"),
    Preset("forest", "🌲 Лес", "🌲 Forest", "🌲 Pădure", "🌲 Wald",
           "forest portrait, dappled natural light through canopy, soft green ambient, morning mist, 85mm, shallow depth, peaceful serene mood"),
    Preset("beach", "🏖 Пляж", "🏖 Beach", "🏖 Plajă", "🏖 Strand",
           "golden beach portrait, early morning backlight, ocean haze, pastel sunrise sky, soft rim light on hair, clean fresh tones, cinematic"),
    Preset("architecture", "🏛 Архитектура", "🏛 Architecture", "🏛 Arhitectură", "🏛 Architektur",
           "urban architectural portrait, concrete and steel backdrop, geometric symmetry, overcast diffused light, modern editorial street style, 24mm wide"),
    Preset("luxury_interior", "🏨 Интерьер", "🏨 Interior", "🏨 Interior", "🏨 Interieur",
           "luxury hotel lobby portrait, Italian marble columns, warm chandelier ambient, elegant depth, velvet and gold accents, upscale editorial"),
    Preset("rain_window", "🌧 Дождь", "🌧 Rain", "🌧 Ploaie", "🌧 Regen",
           "rainy window portrait, water droplets bokeh on glass, cold blue city lights reflected, intimate moody mood, 50mm f/1.4, cinematic low key"),
    Preset("snow", "❄️ Снег", "❄️ Snow", "❄️ Zăpadă", "❄️ Schnee",
           "winter snow portrait, soft falling snowflakes, cool blue-white palette, cozy wool scarf, diffused overcast light, fresh clean look"),
    Preset("rembrandt", "🕯 Рембрандт", "🕯 Rembrandt", "🕯 Rembrandt", "🕯 Rembrandt",
           "Rembrandt lighting portrait, single candle key light, deep chiaroscuro shadows, warm amber tone, painterly old masters style, museum quality"),
    Preset("soft_glam", "✨ Глам", "✨ Soft Glam", "✨ Soft Glam", "✨ Soft Glam",
           "soft glam beauty portrait, pearlescent skin glow, delicate highlight on cheekbones, neutral smoky eye, cinematic lens flare, editorial luxury"),
    Preset("vintage70", "📼 70‑е", "📼 70s", "📼 Ani 70", "📼 70er",
           "1970s vintage film portrait, Kodachrome color palette, halation lens glow, warm muted tones, analog film grain, retro fashion, nostalgic mood"),
    Preset("mono_hicon", "⬛️ Моно Контраст", "⬛️ Mono High‑Contrast", "⬛️ Mono Contrast", "⬛️ Mono Kontrast",
           "high-contrast black and white portrait, crushed blacks, blown highlights, bold graphic shadows, fine art gallery quality, dramatic presence"),
    Preset("park", "🌿 Парк", "🌿 Park", "🌿 Parc", "🌿 Park",
           "outdoor park portrait, soft natural diffused light, lush green bokeh background, 85mm f/2, lifestyle candid mood, warm skin tones"),
    Preset("fitness", "💪 Фитнес", "💪 Fitness", "💪 Fitness", "💪 Fitness",
           "fitness portrait in gym, hard directional key light, dramatic shadows on muscles, moody dark background, gritty raw energy, sports magazine"),
    Preset("garage", "🚗 Гараж", "🚗 Garage", "🚗 Garaj", "🚗 Garage",
           "portrait in automotive garage, industrial overhead lights, chrome and metal reflections, teal color accent, cinematic car culture aesthetic"),
    Preset("bookstore", "📚 Книги", "📚 Bookstore", "📚 Librărie", "📚 Buchladen",
           "bookstore portrait, warm tungsten ambient, rows of books shallow bokeh, intellectual cozy mood, 35mm, golden hour window light"),
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
        "onboard_welcome": "📸 *iModel* — профессиональные фото из вашего селфи.\n\nОдин снимок. Тридцать секунд. Результат как у фотографа.\n\n✨ {quota} генерации бесплатно — без регистрации.",
        "onboard_btn": "🚀 Попробовать бесплатно",
        "onboard_send_selfie": "📷 Отправьте своё селфи — сделаю первое фото прямо сейчас.\n\n*Совет:* хорошее освещение + лицо крупным планом = лучший результат.",
        "start": "С возвращением ✨\n\nОтправьте селфи — и я создам новое фото.",
        "help": "🆘 Помощь\n\nКак получить лучший результат:\n• Пришлите 1 селфи при ровном свете, без сильных фильтров\n• В описании укажите место, свет, стиль, кадрирование, настроение\n• Быстрый старт: откройте Пресеты и выберите стиль\n• Скопировать сцену: режим ‘Скопировать’ — сначала образец, затем селфи\n\nОплата и баланс:\n• Покупка — раздел ‘Купить’ (Telegram Stars)\n• Списание — только при успешной генерации (кроме whitelist/админ)\n• Промокоды — команда /promo КОД\n\nРеферальная программа:\n• Пригласи друга — ты +{ref_ref}, новый пользователь +{ref_new}\n• Твоя ссылка: /refer\n\nПравила и приватность:\n• Запрещены NSFW/селебы\n• Фото хранятся временно; /clear — очистка, /forget — полное удаление\n\nНужна помощь? Напишите @piciriga — ответим быстро.",
        "need_photo": "Сначала пришли фото лица.",
        "photo_ok": "Фото получено ✅ Теперь опишите сцену или используйте /presets.",
        "gen": "Генерирую… ⏳",
        "fail": "Не удалось сгенерировать. Попробуйте изменить описание или фото.",
        "ready": "Готово ✅",
        "credits_none": "💎 Генерации закончились\n\nТы уже видел, как работает iModel — теперь знаешь, чего это стоит.\n\nВыбери тариф и продолжи:",
        "credits_low": "🔋 Осталось: {n} {gen}",
        "credits_last": "⚠️ Последняя генерация! Пополни баланс → /buy",
        "credits_gen_1": "генерация",
        "credits_gen_2": "генерации",
        "credits_gen_5": "генераций",
        "hint_refer_zero": "👥 У вас 0 генераций. Пригласите друга — +{ref_ref} вам и +{ref_new} ему: /refer",
        "btn_invite": "👥 Пригласить друга (+{n} бесплатно)",
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
        "published_recent": "Уже опубликовано недавно.",
        "menu_presets": "📸 Пресеты",
        "menu_help": "🆘 Помощь",
        "menu_refer": "🎁 Бесплатные генерации",
        "menu_invite": "👥 Пригласить друга",
        "btn_support": "📨 Написать поддержку",
        "btn_back": "⬅️ Назад",
        "btn_refer": "🎁 Бесплатные генерации",
        "hint_refer_pay": "🎁 Бонусы: пригласи друга — +{ref_ref} тебе и +{ref_new} другу",
        "menu_pricing": "💎 Тарифы",
        "refer_msg": "👥 Пригласи друзей и получай бонусные генерации!\nТвоя ссылка: {link}\n\nПриглашено: {count}\nПолучено бонусов: {earned} генераций",
        "buy_title": "⭐ Пополнить баланс",
        "buy_btn_10": "✨  10 генераций — 200★",
        "buy_btn_30": "⚡  30 генераций — 500★  (−17%)",
        "buy_btn_100": "🔥  100 генераций — 1200★  (−40%)",
        "buy_btn_300": "💎  300 генераций — 2500★  (−58%)",
        "btn_upsell": "🔥 100 ген — 1200★",
        "bought": "✅ +{add} генераций. Баланс: {all}.",
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
        "style_share_btn": "✨ Сделать в таком стиле",
        "style_share_intro": "Стиль загружен ✅ Пришлите селфи — сделаю похожий результат.",
        "err_channel_not_configured": "Канал не настроен.",
        "err_group_not_configured": "Группа не настроена.",
        "err_no_result": "Нет результата для публикации.",
        "published_ok": "Опубликовано",
        "published_group_ok": "Опубликовано в группе",
        "before_after": "До / После ✨",
        "before": "До",
        "copy_prompt_updated": "Промпт обновлён. Теперь пришлите селфи.",
        "menu_swap": "💎 Точный swap",
        "swap_intro": "💎 Точный swap\nПришлите любое фото — вставлю ваше лицо в него.",
        "swap_no_selfie": "Сначала отправьте своё селфи в обычном режиме.",
        "swap_done": "Готово ✅",
        "swap_fail": "Swap не удался. Попробуйте другое фото.",
    },
    "en": {
        "menu_lang": "🌐 Language",
        "onboard_welcome": "📸 *iModel* — professional photos from your selfie.\n\nOne photo. Thirty seconds. Studio-quality result.\n\n✨ {quota} free generations — no sign-up needed.",
        "onboard_btn": "🚀 Try for free",
        "onboard_send_selfie": "📷 Send your selfie — I’ll create your first photo right now.\n\n*Tip:* good lighting + face in frame = best result.",
        "start": "Welcome back ✨\n\nSend a selfie and I’ll create a new photo for you.",
        "help": "🆘 Help\n\nBest results:\n• Send 1 selfie in even lighting, minimal filters\n• In your prompt describe location, light, style, framing, mood\n• Quick start: open Presets and pick a style\n• Copy a scene: use ‘Copy’ — first the reference, then your selfie\n\nPayments & balance:\n• Buy in ‘Buy’ (Telegram Stars)\n• Credits are deducted only on successful generation (except whitelist/admin)\n• Promo codes — /promo CODE\n\nReferral program:\n• Invite a friend — you +{ref_ref}, they +{ref_new}\n• Your link: /refer\n\nRules & privacy:\n• NSFW/celebrities are forbidden\n• Photos are stored temporarily; /clear to purge temp, /forget for full delete\n\nNeed help? Message @piciriga — we’ll reply quickly.",
        "need_photo": "Please send a face photo first.",
        "photo_ok": "Photo received ✅ Now describe the scene or use /presets.",
        "gen": "Working… ⏳",
        "fail": "Generation failed. Try adjusting your description or selfie.",
        "ready": "Done ✅",
        "credits_none": "💎 Out of generations\n\nYou've seen what iModel can do — keep going.\n\nChoose a plan:",
        "credits_low": "🔋 Remaining: {n} {gen}",
        "credits_last": "⚠️ Last generation! Top up → /buy",
        "credits_gen_1": "generation",
        "credits_gen_2": "generations",
        "credits_gen_5": "generations",
        "hint_refer_zero": "👥 You have 0 credits. Invite a friend — +{ref_ref} you and +{ref_new} them: /refer",
        "btn_invite": "👥 Invite a friend (+{n} free)",
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
        "published_recent": "Already published recently.",
        "menu_presets": "🎛 Presets",
        "menu_help": "🆘 Help",
        "menu_refer": "🎁 Free credits",
        "menu_invite": "👥 Invite a friend",
        "btn_support": "📨 Contact support",
        "btn_back": "⬅️ Back",
        "btn_refer": "🎁 Free credits",
        "hint_refer_pay": "🎁 Tip: invite a friend — +{ref_ref} you · +{ref_new} them",
        "menu_pricing": "💎 Pricing",
        "refer_msg": "👥 Invite friends and earn bonus generations!\nYour link: {link}\n\nInvited: {count}\nBonuses earned: {earned} gens",
        "style_share_btn": "✨ Make in this style",
        "style_share_intro": "Style loaded ✅ Send a selfie — I'll create a similar result.",
        "buy_title": "⭐ Top up",
        "buy_btn_10": "✨  10 generations — 200★",
        "buy_btn_30": "⚡  30 generations — 500★  (−17%)",
        "buy_btn_100": "🔥  100 generations — 1200★  (−40%)",
        "buy_btn_300": "💎  300 generations — 2500★  (−58%)",
        "btn_upsell": "🔥 100 gens — 1200★",
        "bought": "✅ +{add} generations. Balance: {all}.",
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
        "err_channel_not_configured": "Channel is not configured.",
        "err_group_not_configured": "Group is not configured.",
        "err_no_result": "No result to publish.",
        "published_ok": "Published",
        "published_group_ok": "Published to group",
        "before_after": "Before / After ✨",
        "before": "Before",
        "copy_prompt_updated": "Prompt updated. Now send a selfie.",
        "menu_swap": "💎 Exact swap",
        "swap_intro": "💎 Exact Swap\nSend any photo — I'll place your face into it.",
        "swap_no_selfie": "Send a selfie in normal mode first.",
        "swap_done": "Done ✅",
        "swap_fail": "Swap failed. Try a different photo.",
    },
    "ro": {
        "menu_lang": "🌐 Limba",
        "onboard_welcome": "📸 *iModel* — fotografii profesionale din selfie-ul tău.\n\nO poză. Treizeci de secunde. Rezultat de studio.\n\n✨ {quota} generări gratuite — fără înregistrare.",
        "onboard_btn": "🚀 Încearcă gratuit",
        "onboard_send_selfie": "📷 Trimite selfie-ul tău — creez prima fotografie chiar acum.\n\n*Sfat:* lumină bună + față în cadru = cel mai bun rezultat.",
        "start": "Bun venit înapoi ✨\n\nTrimite un selfie și creez o nouă fotografie pentru tine.",
        "help": "🆘 Ajutor\n\nRezultate mai bune:\n• Trimite 1 selfie cu lumină uniformă, fără filtre puternice\n• În descriere: locație, lumină, stil, încadrare, mood\n• Start rapid: deschide Preseturi și alege un stil\n• Copiere scenă: ‘Copiază’ — mai întâi referința, apoi selfie‑ul\n\nPlăți & sold:\n• Cumpără în ‘Cumpără’ (Stele Telegram)\n• Creditul se scade doar la generare reușită (exceptând whitelist/admin)\n• Cod promo — /promo COD\n\nProgram de recomandări:\n• Invită un prieten — tu +{ref_ref}, el/ea +{ref_new}\n• Linkul tău: /refer\n\nReguli & confidențialitate:\n• NSFW/celebr. interzise\n• Pozele se păstrează temporar; /clear curăță, /forget ștergere totală\n\nAi nevoie de ajutor? Scrie la @piciriga — răspundem rapid.",
        "need_photo": "Trimite o poză cu fața mai întâi.",
        "photo_ok": "Poză primită ✅ Acum descrie scena sau folosește /presets.",
        "gen": "Generez… ⏳",
        "fail": "Nu am reușit. Încearcă altă descriere sau alt selfie.",
        "ready": "Gata ✅",
        "credits_none": "💎 Generațiile s-au terminat\n\nAi văzut ce poate iModel — continuă.\n\nAlege un plan:",
        "credits_low": "🔋 Rămase: {n} {gen}",
        "credits_last": "⚠️ Ultima generație! Alimentează → /buy",
        "credits_gen_1": "generație",
        "credits_gen_2": "generații",
        "credits_gen_5": "generații",
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
        "published_recent": "Deja publicat recent.",
        "menu_presets": "🎛 Preseturi",
        "menu_help": "🆘 Ajutor",
        "menu_refer": "🎁 Generații gratuite",
        "menu_invite": "👥 Invită un prieten",
        "btn_support": "📨 Contact suport",
        "btn_back": "⬅️ Înapoi",
        "btn_refer": "🎁 Generații gratuite",
        "hint_refer_pay": "🎁 Bonus: invită un prieten — +{ref_ref} ție · +{ref_new} lui/ei",
        "menu_pricing": "💎 Prețuri",
        "refer_msg": "👥 Invită prieteni și primește generații bonus!\nLinkul tău: {link}\n\nInvitați: {count}\nBonusuri obținute: {earned}",
        "buy_title": "⭐ Alimentează contul",
        "buy_btn_10": "✨  10 gen — 200★",
        "buy_btn_30": "⚡  30 gen — 500★  (−17%)",
        "buy_btn_100": "🔥  100 gen — 1200★  (−40%)",
        "buy_btn_300": "💎  300 gen — 2500★  (−58%)",
        "btn_upsell": "🔥 100 gen — 1200★",
        "bought": "✅ +{add} generații. Sold: {all}.",
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
        "err_channel_not_configured": "Canalul nu este configurat.",
        "err_group_not_configured": "Grupul nu este configurat.",
        "err_no_result": "Nu există rezultat pentru publicare.",
        "published_ok": "Publicat",
        "published_group_ok": "Publicat în grup",
        "before_after": "Înainte / După ✨",
        "before": "Înainte",
        "copy_prompt_updated": "Prompt actualizat. Trimite selfie-ul.",
        "menu_swap": "💎 Swap exact",
        "swap_intro": "💎 Swap exact\nTrimite orice foto — îți pun fața în el.",
        "swap_no_selfie": "Trimite mai întâi un selfie în modul normal.",
        "swap_done": "Gata ✅",
        "swap_fail": "Swap eșuat. Încearcă altă fotografie.",
        "refer_msg": "👥 Invită prieteni și primește generații bonus!\nLinkul tău: {link}\n\nInvitați: {count}\nBonusuri obținute: {earned}",
        "style_share_btn": "✨ În acest stil",
        "style_share_intro": "Stil încărcat ✅ Trimite un selfie — generez un rezultat similar.",
    }
    ,
    "de": {
        "menu_lang": "🌐 Sprache",
        "onboard_welcome": "📸 *iModel* — professionelle Fotos aus deinem Selfie.\n\nEin Foto. Dreißig Sekunden. Studio-Qualität.\n\n✨ {quota} kostenlose Generierungen — ohne Anmeldung.",
        "onboard_btn": "🚀 Kostenlos testen",
        "onboard_send_selfie": "📷 Schicke dein Selfie — ich erstelle dein erstes Foto jetzt gleich.\n\n*Tipp:* gutes Licht + Gesicht im Bild = bestes Ergebnis.",
        "start": "Willkommen zurück ✨\n\nSchicke ein Selfie und ich erstelle ein neues Foto für dich.",
        "help": "🆘 Hilfe\n\nBeste Ergebnisse:\n• 1 Selfie bei gleichmäßiger Beleuchtung, ohne starke Filter\n• Beschreibe Ort, Licht, Stil, Bildausschnitt, Stimmung\n• Schnellstart: Presets öffnen und Stil wählen\n• Szene kopieren: ‘Kopieren’ — zuerst Referenz, dann Selfie\n\nZahlung & Guthaben:\n• Kaufen in ‘Kaufen’ (Telegram Stars)\n• Abzug nur bei erfolgreicher Generierung (außer Whitelist/Admin)\n• Promo‑Code — /promo CODE\n\nEmpfehlungsprogramm:\n• Freund einladen — du +{ref_ref}, er/sie +{ref_new}\n• Dein Link: /refer\n\nRegeln & Datenschutz:\n• NSFW/Promis verboten\n• Fotos werden temporär gespeichert; /clear löscht temporär, /forget vollständig\n\nBrauchen Sie Hilfe? Schreiben Sie @piciriga — wir antworten schnell.",
        "need_photo": "Bitte zuerst ein Gesichts‑Foto senden.",
        "photo_ok": "Foto empfangen ✅ Beschreibe jetzt die Szene oder nutze /presets.",
        "gen": "Erzeuge… ⏳",
        "fail": "Erzeugung fehlgeschlagen. Bitte Beschreibung oder Selfie anpassen.",
        "ready": "Fertig ✅",
        "credits_none": "💎 Keine Generierungen mehr\n\nDu hast iModel kennengelernt — mach weiter.\n\nWähle einen Plan:",
        "credits_low": "🔋 Verbleibend: {n} {gen}",
        "credits_last": "⚠️ Letzte Generierung! Aufladen → /buy",
        "credits_gen_1": "Generierung",
        "credits_gen_2": "Generierungen",
        "credits_gen_5": "Generierungen",
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
        "published_recent": "Kürzlich bereits veröffentlicht.",
        "menu_presets": "🎛 Presets",
        "menu_help": "🆘 Hilfe",
        "menu_refer": "🎁 Kostenlose Credits",
        "menu_invite": "👥 Freund einladen",
        "btn_support": "📨 Support kontaktieren",
        "btn_back": "⬅️ Zurück",
        "btn_refer": "🎁 Kostenlose Credits",
        "hint_refer_pay": "🎁 Tipp: Freund einladen — +{ref_ref} dir · +{ref_new} ihm/ihr",
        "menu_pricing": "💎 Preise",
        "refer_msg": "👥 Lade Freunde ein und erhalte Bonus‑Generierungen!\nDein Link: {link}\n\nEingeladen: {count}\nErhaltene Boni: {earned}",
        "buy_title": "⭐ Guthaben aufladen",
        "buy_btn_10": "✨  10 Gen — 200★",
        "buy_btn_30": "⚡  30 Gen — 500★  (−17%)",
        "buy_btn_100": "🔥  100 Gen — 1200★  (−40%)",
        "buy_btn_300": "💎  300 Gen — 2500★  (−58%)",
        "btn_upsell": "🔥 100 Gen — 1200★",
        "bought": "✅ +{add} Generierungen. Guthaben: {all}.",
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
        "style_share_btn": "✨ In diesem Stil",
        "style_share_intro": "Stil geladen ✅ Sende ein Selfie — ich erstelle ein ähnliches Ergebnis.",
        "err_channel_not_configured": "Kanal ist nicht konfiguriert.",
        "err_group_not_configured": "Gruppe ist nicht konfiguriert.",
        "err_no_result": "Kein Ergebnis zum Veröffentlichen.",
        "published_ok": "Veröffentlicht",
        "published_group_ok": "In Gruppe veröffentlicht",
        "before_after": "Vorher / Nachher ✨",
        "before": "Vorher",
        "copy_prompt_updated": "Prompt aktualisiert. Bitte sende ein Selfie.",
        "menu_swap": "💎 Exakter Swap",
        "swap_intro": "💎 Exakter Swap\nSende ein beliebiges Foto — ich füge dein Gesicht ein.",
        "swap_no_selfie": "Sende zuerst ein Selfie im normalen Modus.",
        "swap_done": "Fertig ✅",
        "swap_fail": "Swap fehlgeschlagen. Versuche ein anderes Foto.",
    }
}

def L(chat_id: int) -> dict:
    """Return language dict with safe fallback to default for missing keys.
    Access via d["key"] won't KeyError — falls back to default lang or the key itself.
    """
    base = T.get(LANG_DEFAULT, {})
    current = T.get(USER_LANG.get(chat_id, LANG_DEFAULT), base)

    class _Lang(dict):
        def __getitem__(self, k):  # type: ignore[override]
            if dict.__contains__(self, k):
                return dict.__getitem__(self, k)
            return base.get(k, k)

        def get(self, k, default=None):  # type: ignore[override]
            if dict.__contains__(self, k):
                return dict.__getitem__(self, k)
            return base.get(k, default)

    return _Lang(current)

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
        resp = await m.answer_photo(photo=photo, **kwargs)
        jid = USER_LAST_JOB.get(m.chat.id)
        if jid:
            record_job(jid, status="delivered")
            job_event(jid, "telegram_delivered", method="photo")
            stats_incr("delivery_photo_ok", 1)
            USER_LAST_JOB.pop(m.chat.id, None)
        return resp
    except (TelegramForbiddenError, TelegramNotFound):
        print(f"[safe_answer_photo] blocked/not found: chat_id={m.chat.id}")
    except TelegramBadRequest as e:
        print(f"[safe_answer_photo] bad request: {e}")
    jid = USER_LAST_JOB.get(m.chat.id)
    if jid:
        record_job(jid, status="delivery_failed", error="telegram_photo_failed")
        job_event(jid, "telegram_delivery_failed", method="photo")
        stats_incr("delivery_failed", 1)
        USER_LAST_JOB.pop(m.chat.id, None)
    return None

async def safe_edit_text(msg: Message, text: str):
    try:
        return await msg.edit_text(text)
    except TelegramBadRequest as e:
        print(f"[safe_edit_text] bad request: {e}")
    return None

async def _progress_loop(msg: Message, lang: str = "ru"):
    """Animate the wait message every 8 seconds while generation runs."""
    _stages = [
        (0,  {"ru": "⏳ Генерирую...",         "en": "⏳ Generating...",    "ro": "⏳ Generez...",   "de": "⏳ Erzeuge..."}),
        (16, {"ru": "🎨 Обрабатываю лицо...",  "en": "🎨 Processing face...","ro": "🎨 Procesez...", "de": "🎨 Verarbeite..."}),
        (35, {"ru": "✨ Улучшаю качество...",   "en": "✨ Enhancing...",      "ro": "✨ Îmbunătățesc...","de": "✨ Verbessere..."}),
        (55, {"ru": "🔄 Финальные штрихи...",  "en": "🔄 Final touches...", "ro": "🔄 Finalizez...", "de": "🔄 Letzte Schritte..."}),
    ]
    start = time.time()
    last_text = ""
    while True:
        await asyncio.sleep(8)
        elapsed = int(time.time() - start)
        label = _stages[0][1].get(lang, _stages[0][1]["en"])
        for threshold, texts in reversed(_stages):
            if elapsed >= threshold:
                label = texts.get(lang, texts["en"])
                break
        text = f"{label} ({elapsed}с)" if lang == "ru" else f"{label} ({elapsed}s)"
        if text != last_text:
            await safe_edit_text(msg, text)
            last_text = text

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
    # Replicate SDK >= 0.22 returns FileOutput objects with .url attribute
    if hasattr(output, "url"):
        u = getattr(output, "url", None)
        if callable(u):
            try:
                u = u()
            except Exception:
                u = None
        if isinstance(u, str) and u.startswith("http"):
            return u
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
    # Handle generators/iterators (Replicate SDK sometimes returns these)
    import types
    if isinstance(output, (types.GeneratorType,)) or hasattr(output, "__next__"):
        try:
            first = next(output)
            return _extract_first_url(first)
        except StopIteration:
            return None
        except Exception as e:
            print(f"_extract_first_url iterator error: {e}")
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
    t0 = time.time()
    log_event("replicate_start", model=model, input_keys=sorted(inputs.keys()))
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
                    REPLICATE_LAST_ERROR = f"[{model_name}] {msg}"
                    print("Replicate prediction error:", msg[:300])
                    log_event("replicate_error", model=model, error=msg[:240], status=status)
                    if "sensitive" in msg.lower():
                        return "SENSITIVE"
                else:
                    REPLICATE_LAST_ERROR = f"[{model_name}] status={status}"
                    print("Replicate prediction not succeeded:", status, "model:", model_name)
            out = getattr(pred, "output", None) or (pred.get("output") if isinstance(pred, dict) else None)
            print(f"Replicate raw output type={type(out).__name__} val={str(out)[:200]}")
            url = _extract_first_url(out)
            if url:
                log_event("replicate_done", model=model, prediction_id=pid, latency_ms=int((time.time() - t0) * 1000))
                return url
            try:
                url = _extract_first_url(dict(pred))
                if url:
                    log_event("replicate_done", model=model, prediction_id=pid, latency_ms=int((time.time() - t0) * 1000))
                    return url
            except Exception:
                pass
    except Exception as e:
        em = str(e)
        REPLICATE_LAST_ERROR = em
        print("replicate.predictions.create error:", em[:200])
        log_event("replicate_error", model=model, error=em[:240])
        if "sensitive" in em.lower():
            return "SENSITIVE"

    try:
        # replicate.run supports owner/name or owner/name:version
        out = replicate.run(model if not model_version else f"{model_name}:{model_version}", input=inputs)
        print(f"replicate.run output type={type(out).__name__} val={str(out)[:200]}")
        url = _extract_first_url(out)
        if url:
            log_event("replicate_done", model=model, latency_ms=int((time.time() - t0) * 1000), path="run")
            return url
        REPLICATE_LAST_ERROR = f"[{model_name}] run returned no URL, output={str(out)[:120]}"
    except Exception as e2:
        em2 = str(e2)
        REPLICATE_LAST_ERROR = f"[{model_name}] run error: {em2}"
        print("replicate.run error:", em2[:300])
        log_event("replicate_error", model=model, error=em2[:240], path="run")
        if "sensitive" in em2.lower():
            return "SENSITIVE"

    return None

def _normalize_to_jpeg(image_bytes: bytes, max_side: int = 1024) -> bytes:
    """Resize + convert to JPEG. Keeps size safe for Replicate uploads."""
    if Image is None:
        return image_bytes
    try:
        im = Image.open(io.BytesIO(image_bytes)).convert("RGB")
        w, h = im.size
        if max(w, h) > max_side:
            ratio = max_side / max(w, h)
            im = im.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=90)
        return buf.getvalue()
    except Exception as e:
        print(f"_normalize_to_jpeg error: {e}")
        return image_bytes

def enhance_face_gfpgan(image_bytes: bytes) -> bytes:
    """GFPGAN face restoration — returns enhanced bytes or original on failure."""
    if not GFPGAN_MODEL or not image_bytes:
        return image_bytes
    try:
        # Normalize input: JPEG ≤ 1024px so Replicate upload doesn't fail on large images
        input_bytes = _normalize_to_jpeg(image_bytes, max_side=1024)
        out = replicate.run(
            GFPGAN_MODEL,
            input={
                "img": io.BytesIO(input_bytes),
                "scale": 2,
                "version": "v1.4",
            }
        )
        print(f"GFPGAN raw output: type={type(out).__name__} val={str(out)[:300]}")
        url = _extract_first_url(out)
        print(f"GFPGAN extracted url: {url!r}")
        if url and url.startswith("http"):
            enhanced = _download_with_retries(url)
            if enhanced and len(enhanced) > 1000:
                print(f"GFPGAN OK: {len(image_bytes)} → {len(enhanced)} bytes")
                return enhanced
            print(f"GFPGAN download failed or too small: {len(enhanced) if enhanced else 0} bytes")
        else:
            print(f"GFPGAN: no valid URL extracted, output was: {str(out)[:300]}")
    except Exception as e:
        print(f"GFPGAN error (using original): {type(e).__name__}: {e}")
    return image_bytes

def enhance_face_codeformer(image_bytes: bytes, fidelity: float = 0.8) -> bytes:
    """CodeFormer face enhancement — subtle professional retouch, high identity fidelity.

    fidelity=1.0 → max identity preservation, no enhancement
    fidelity=0.0 → max enhancement, less identity
    0.8 is the sweet spot: professional polish, face stays exact.
    Falls back to GFPGAN, then original on failure.
    """
    if not CODEFORMER_MODEL or not image_bytes:
        return enhance_face_gfpgan(image_bytes)
    try:
        out = replicate.run(
            CODEFORMER_MODEL,
            input={
                "image": io.BytesIO(image_bytes),
                "codeformer_fidelity": fidelity,
                "background_enhance": False,
                "face_upsample": True,
                "upscale": 2,
            }
        )
        print(f"CodeFormer raw output: type={type(out).__name__} val={str(out)[:300]}")
        url = _extract_first_url(out)
        if url and url.startswith("http"):
            enhanced = _download_with_retries(url)
            if enhanced and len(enhanced) > 1000:
                print(f"CodeFormer OK (fidelity={fidelity}): {len(image_bytes)} → {len(enhanced)} bytes")
                return enhanced
            print(f"CodeFormer download failed or too small: {len(enhanced) if enhanced else 0} bytes")
        else:
            print(f"CodeFormer: no valid URL. output={str(out)[:300]}")
    except Exception as e:
        print(f"CodeFormer error (type={type(e).__name__}): {e} — trying GFPGAN")
    return enhance_face_gfpgan(image_bytes)

def face_swap(source_bytes: bytes, target_bytes: bytes) -> Optional[bytes]:
    """Swap face from source (selfie) into target (reference photo).

    target stays 100% intact — clothes, background, pose unchanged.
    Only the face region is replaced with the identity from source.
    Returns result bytes or None on failure.
    """
    if not FACESWAP_MODEL or not source_bytes or not target_bytes:
        return None
    try:
        out = replicate.run(
            FACESWAP_MODEL,
            input={
                "swap_image":   io.BytesIO(source_bytes),
                "target_image": io.BytesIO(target_bytes),
            }
        )
        url = _extract_first_url(out)
        if url and url.startswith("http"):
            result = _download_with_retries(url)
            if result and len(result) > 1000:
                print(f"FaceSwap OK: {len(target_bytes)} → {len(result)} bytes")
                return result
        print(f"FaceSwap: no valid URL in output: {str(out)[:120]}")
    except Exception as e:
        print(f"FaceSwap error: {str(e)[:200]}")
    return None

# ===================== HTTP DOWNLOAD ==================
def _download_with_retries(url: str, tries: int = 4, base_sleep: float = 0.6) -> Optional[bytes]:
    for i in range(max(1, tries)):
        try:
            r = requests.get(url, timeout=180)
            if r.ok and r.content:
                return r.content
            log_event("download_retry_http_error", attempt=i + 1, status=getattr(r, "status_code", None), url=url[:120])
        except Exception as exc:
            log_event("download_retry_error", attempt=i + 1, error=str(exc)[:120], url=url[:120])
        time.sleep(base_sleep * (i + 1))
    return None

# ===================== GROUP POSTS =====================
PROMO_TOPICS_RU = [
    "instagram aesthetic lifestyle portrait, candid smile, soft natural window light, airy pastel palette",
    "street style portrait, soft overcast light, shallow depth, subtle film grain, tasteful colors",
    "clean studio look, softbox glow, pastel backdrop, minimalist composition, editorial yet casual",
    "golden hour portrait, warm rim light, gentle haze, teal‑orange touch, modern influencer vibe",
    "coffee shop lifestyle portrait, warm tungsten, cozy mood, creamy bokeh, natural skin tones",
]

PROMO_TOPICS_RO = [
    "instagram aesthetic lifestyle portrait, candid laugh, soft daylight, airy pastels, minimal retouch",
    "urban portrait, overcast soft light, creamy bokeh, subtle grain, fashionable yet natural",
    "studio portrait, soft beauty light, clean pastel background, minimalist composition",
    "sunset golden hour, warm backlight, dreamy haze, modern influencer color grade",
    "cafe lifestyle portrait, warm lights, cozy atmosphere, shallow depth of field",
]

# Educational tip buckets per language
TIPS_RU = {
    "light_morning": "Лайфхак света: утром ставьте камеру так, чтобы солнечный блик шёл вдоль стены — мягкий объём без пересветов.",
    "light_sunset": "Золотой час спасает даже простую комнату — тёплая боковая подсветка даёт глубину и уют.",
    "light_lamps": "Лампы тёплого спектра + выключенный верхний свет = меньше плоских теней и больше атмосферы.",
    "framing_wide": "Ширик — это аккуратность: выравнивайте вертикали и следите, чтобы углы мебели не ‘уезжали’.",
    "framing_height": "Высота камеры ~90–110 см: линии столов и кроватей становятся ровнее, кадр — спокойнее.",
    "color_wb": "Баланс белого держите нейтральным: смешение ламп и дневного света лечится точкой серого.",
    "micro_contrast": "Немного микроконтраста подчёркивает текстуры дерева и ткани — не переборщите.",
    "donts": "Не перегружайте кадр: уберите лишние предметы со столешниц и пола — воздух дороже.",
}

TIPS_RO = {
    "light_morning": "Lumina de dimineață pe perete dă volum blând fără supraexpuneri.",
    "light_sunset": "Ora de aur încălzește orice cameră — lumină laterală = profunzime & cozy.",
    "light_lamps": "Becuri calde + fără lumină de tavan = umbre mai plăcute și atmosferă.",
    "framing_wide": "Cu wide‑angle fii atent la verticale — colțurile mobilei să nu ‘alunece’.",
    "framing_height": "Înălțimea camerei ~90–110 cm: linii mai drepte, cadru mai calm.",
    "color_wb": "Ține WB neutru: mixul dintre lumină de zi și lămpi se corectează cu un punct de gri.",
    "micro_contrast": "Puțin micro‑contrast scoate textura lemnului și a textilelor — cu măsură.",
    "donts": "Nu încărca cadrul: eliberează blaturile și podeaua — aerul valorează mult.",
}

def _pick_tip(lang: str) -> str:
    tips = TIPS_RU if lang.startswith("ru") else TIPS_RO if lang.startswith("ro") else None
    if not tips:
        return "Keep verticals straight and light soft — simple and classy."
    key = random.choice(list(tips.keys()))
    return tips[key]

def craft_group_post_text(lang: str, bot_username: Optional[str]) -> str:
    name = ("@" + bot_username) if bot_username else "the bot"

    # Instagram‑style witty quotes per language (short, charismatic, playful)
    QUOTES_RU = [
        "Красота — это когда лишнего нет, а ты есть.",
        "Харизма — это фильтр, который всегда ‘вкл’.",
        "Жизнь как лента — главное, что в кадре ты.",
        "Юмор — мой софтбокс. Подсвечивает даже понедельник.",
        "Идеального света не бывает. Бывает твоё настроение в кадре.",
        "Главный секрет стиля? Делать вид, что это не секрет.",
    ]
    QUOTES_RO = [
        "Frumusețea începe când dispare ‘prea mult’. Tu rămâi.",
        "Carisma e filtrul meu preferat — mereu ON.",
        "Viața e un feed — important e că ești în cadru.",
        "Umorul e softbox‑ul meu. Pune lumină pe orice zi.",
        "Lumina perfectă? Starea ta în cadru.",
    ]
    QUOTES_DE = [
        "Stil ist, wenn nichts zu viel ist — und du bleibst.",
        "Charisma ist mein Lieblingsfilter — immer an.",
        "Das Leben ist ein Feed. Hauptsache: du bist im Bild.",
        "Humor ist mein Softbox — beleuchtet jeden Montag.",
        "Perfektes Licht? Deine Stimmung im Bild.",
    ]
    QUOTES_EN = [
        "Style is when nothing’s extra — and you still shine.",
        "Charisma is my favorite filter — always on.",
        "Life is a feed. The point is: you’re in frame.",
        "Humor is my softbox — lights up any Monday.",
        "Perfect light? Your mood in the shot.",
    ]

    def pick_quote() -> str:
        if lang.startswith("ru"):
            return random.choice(QUOTES_RU)
        if lang.startswith("ro"):
            return random.choice(QUOTES_RO)
        if lang.startswith("de"):
            return random.choice(QUOTES_DE)
        return random.choice(QUOTES_EN)

    quote = pick_quote()

    # Try LLM if available — but ask for IG‑style quote
    try:
        if OPENAI_API_KEY and OpenAI is not None:
            client = OpenAI(api_key=OPENAI_API_KEY)
            sys = (
                "You craft short Instagram‑style quotes: witty, charismatic, playful. "
                "Return 1–2 sentences only. No hashtags, no emojis overload. "
                "Close with a soft CTA mentioning the bot handle."
            )
            user = f"Language: {lang}. Bot handle: {name}. Example tone: '{quote}'."
            r = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role":"system","content":sys},{"role":"user","content":user}],
                temperature=0.9,
                max_tokens=80,
                timeout=60,
            )
            out = (r.choices[0].message.content or "").strip()
            if out:
                return out
    except Exception as e:
        print("craft_group_post_text error:", str(e)[:160])

    # Fallback: static quote + CTA
    if lang.startswith("ru"):
        return f"{quote}\nПопробуй {name} — чуть юмора, много стиля."
    if lang.startswith("ro"):
        return f"{quote}\nÎncearcă {name} — un strop de umor, mult stil."
    if lang.startswith("de"):
        return f"{quote}\nTeste {name} — leicht, stilvoll, sympathisch."
    return f"{quote}\nTry {name} — tasteful, playful, you."

def craft_group_post_image_prompt(lang: str) -> str:
    topics = PROMO_TOPICS_RU if lang.startswith("ru") else PROMO_TOPICS_RO if lang.startswith("ro") else PROMO_TOPICS_RU
    theme = random.choice(topics)
    base = (
        "instagram aesthetic lifestyle portrait, 4:5 vertical, candid, tasteful and modern, "
        "soft natural light, airy pastel palette, subtle film grain, shallow depth of field, "
        "clean composition, natural skin tones, SFW, no brands, no text"
    )
    return f"{theme}. {base}"

def generate_group_post_image(lang: str) -> Optional[bytes]:
    if GROUP_POST_TEXT_ONLY:
        return None
    if not REPLICATE_API_TOKEN or not INSTANTID_MODEL:
        return None
    prompt = craft_group_post_image_prompt(lang)
    try:
        url = replicate_generate(INSTANTID_MODEL, {"prompt": prompt})
        if url and url.startswith("http"):
            img = _download_with_retries(url)
            if img:
                return img
    except Exception as e:
        print("group image generate error:", str(e)[:160])
    return None

def _next_group_lang() -> str:
    global _GROUP_LANG_IDX
    if not _GROUP_LANGS:
        return "ru"
    lang = _GROUP_LANGS[_GROUP_LANG_IDX % len(_GROUP_LANGS)]
    _GROUP_LANG_IDX = (_GROUP_LANG_IDX + 1) % max(1, len(_GROUP_LANGS))
    return lang

async def group_posts_loop():
    # Post to group every 2-3 hours with light randomness
    await asyncio.sleep(5)
    while True:
        try:
            if not PUBLISH_GROUP_ID or not GROUP_POSTS_ENABLED:
                await asyncio.sleep(60)
                continue
            # Rotate langs if list provided
            lang = _next_group_lang()
            # If debug interval set, ignore quiet hours
            if GROUP_POST_EVERY_MINUTES <= 0:
                # Respect quiet hours (22:00..08:00) in the language's timezone
                try:
                    from zoneinfo import ZoneInfo
                    import datetime as _dt
                    tzname = _lang_to_tz(lang)
                    now_loc = _dt.datetime.now(ZoneInfo(tzname))
                    hour = now_loc.hour
                    start_h = min(GROUP_POST_START_HOUR, GROUP_POST_END_HOUR)
                    end_h = max(GROUP_POST_START_HOUR, GROUP_POST_END_HOUR)
                    if not (start_h <= hour < end_h):
                        # sleep until next window start
                        next_start = now_loc.replace(hour=start_h, minute=0, second=0, microsecond=0)
                        if hour >= end_h:
                            next_start = next_start + _dt.timedelta(days=1)
                        wait_sec = max(60, int((next_start - now_loc).total_seconds()))
                        await asyncio.sleep(wait_sec)
                        continue
                except Exception:
                    pass
            # Compose text
            txt = craft_group_post_text(lang, BOT_USERNAME_GLOBAL)
            img = generate_group_post_image(lang)
            if img:
                try:
                    await bot.send_photo(
                        chat_id=PUBLISH_GROUP_ID,
                        photo=BufferedInputFile(img, filename="promo.jpg"),
                        caption=txt
                    )
                    STATS["published_group"] = int(STATS.get("published_group", 0)) + 1
                    global GROUP_POST_LAST_AT
                    GROUP_POST_LAST_AT = time.time()
                except Exception as e:
                    print("group promo send error:", str(e)[:160])
            else:
                try:
                    await bot.send_message(chat_id=PUBLISH_GROUP_ID, text=txt)
                    STATS["published_group"] = int(STATS.get("published_group", 0)) + 1
                    GROUP_POST_LAST_AT = time.time()
                except Exception as e:
                    print("group promo text error:", str(e)[:160])
            # Sleep
            if GROUP_POST_EVERY_MINUTES > 0:
                await asyncio.sleep(max(60, GROUP_POST_EVERY_MINUTES * 60))
            else:
                wait_h = random.uniform(GROUP_POST_MIN_HOURS, GROUP_POST_MAX_HOURS)
                await asyncio.sleep(max(300, int(wait_h * 3600)))
        except Exception as e:
            print("group_posts_loop error:", str(e)[:160])
            await asyncio.sleep(60)

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

# Negative prompt for InstantID/PhotoMaker — concise, model-appropriate
INSTANTID_NEGATIVE = (
    "deformed, ugly, bad anatomy, disfigured, mutation, extra limbs, extra fingers, "
    "blurry, low quality, lowres, watermark, text, logo, cartoon, anime, painting"
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
                timeout=60,
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
            "You are a senior photographer and lighting designer. Extract ONE LONG LINE (comma‑separated) SCENE SPEC for exact recreation "
            "with a different face. Be concrete and visual, no filler prose. Include in order: environment/location with key background cues "
            "(materials, furniture, depth, distance), composition & framing (portrait 4:5, close‑up/half‑body/full, headroom, negative space), "
            "camera angle (eye‑level/low/high) and lens/focal length feel (e.g., 85mm), exposure metadata (aperture, shutter, ISO), pose & head orientation, "
            "time of day, lighting design (key/fill/rim/back, source type like window/softbox/neon, direction/height/size/softness, Kelvin temperature), "
            "color palette and grading (film‑like, teal‑orange, pastel, muted, high contrast), mood, and style adjectives. Keep subject generic (adult person). "
            "Strictly SFW (fully clothed). No brands, no logos, no text, no celebrity. Keep it ONE line, information‑dense."
        )
        msg = [
            {"role": "system", "content": sys},
            {"role": "user", "content": [
                {"type": "text", "text": "Produce one detailed line for 1:1 scene copy (no face/identity notes)."},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
            ]}
        ]
        r = client.chat.completions.create(
            model=OPENAI_MODEL_VISION,
            messages=msg,
            temperature=0.2,
            max_tokens=260,
            timeout=60,
        )
        line = (r.choices[0].message.content or "").strip()
        if not line:
            return None
        line = enforce_safe_prompt(line)
        return f"{line}. {SCENE_LOCK}"
    except Exception as e:
        print("Vision scene error:", str(e)[:200])
        return None

def craft_mj_prompt_from_image(style_bytes: bytes) -> Optional[str]:
    """Produce an extra‑detailed, longer one‑line prompt for Copy Mode with very strong clothing and scene detail (SFW)."""
    if not OPENAI_API_KEY or OpenAI is None:
        return None
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        b64 = base64.b64encode(style_bytes).decode("utf-8")
        sys = (
            "You are an expert fashion + photography prompt engineer. Given ONE reference photo, return ONE LONG LINE in English, "
            "comma‑separated attributes, extremely detailed and information‑dense. Start with CLOTHING (garment category, layering, silhouette and fit, "
            "drape, materials/fabrics and weave, texture, pattern/print, construction details like collar/lapel/cuffs/hem/seams/pleats/darts, closures and hardware, "
            "accessories (belt, jewelry, earrings, necklace, watch, glasses, hat, scarf, bag), footwear, and a concise clothing color palette). Then cover: subject (generic 'adult person'), "
            "environment/location with distinctive background cues (materials, furniture, signage/bokeh shapes, depth, distance), composition/framing (portrait 4:5, close‑up/half‑body/full, headroom, negative space, rule of thirds), "
            "camera angle and lens/focal length feel (e.g., 85mm), exposure metadata (aperture f/.., shutter 1/..s, ISO ..), pose and head orientation, time of day, "
            "lighting design (key/fill/rim/back, source type window/softbox/neon, direction/height/size/softness, Kelvin temperature), color grading/toning (pastel, muted, teal‑orange, filmic), mood, and tiny styling cues. "
            "Strictly SFW (fully clothed). No brands, no logos, no celebrity, no text. Do not mention 'reference', 'swap', or 'face'. Keep it ONE single line, long but precise."
        )
        user_content = [
            {"type": "text", "text": "Return one long, comma‑separated line: clothing first (very detailed), then environment/composition/camera/exposure/lighting/grading/mood."},
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
            max_tokens=380,
            timeout=60,
        )
        line = (r.choices[0].message.content or "").strip()
        if not line:
            return None
        # Ensure SFW suffix but do not force age or break structure
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

# ===================== ADMIN NOTIFY ==================
async def notify_admins_payment(
    user_id: int,
    username: Optional[str],
    name: Optional[str],
    pack: str,
    gens: int,
    balance: int,
    stars: Optional[int] = None,
):
    try:
        # Collect recipients: explicit ADMIN_IDS + known chat ids by admin usernames
        recips: Set[int] = set(ADMIN_IDS)
        try:
            for uid, info in STATS_USERS_INFO.items():
                u = (info.get("username") or "").strip().lstrip("@").lower()
                if u and u in ADMIN_USERNAMES:
                    recips.add(int(uid))
        except Exception:
            pass
        if not recips:
            return
        who = username or (name or "user")
        stars_note = f", {stars}★" if stars else ""
        text = (
            f"💳 Покупка: +{gens} ген ({pack}{stars_note})\n"
            f"Пользователь: {who} (id {user_id})\n"
            f"Баланс после: {balance}"
        )
        for rid in recips:
            try:
                await bot.send_message(chat_id=rid, text=text)
            except TelegramForbiddenError:
                continue
            except TelegramNotFound:
                continue
            except TelegramBadRequest as e:
                print("notify_admins_payment bad request:", str(e)[:160])
            except Exception as e:
                print("notify_admins_payment error:", str(e)[:160])
    except Exception as e:
        print("notify_admins_payment outer error:", str(e)[:160])

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
            timeout=60,
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

INACTIVE_TTL = int(os.getenv("INACTIVE_TTL_HOURS", "24")) * 3600  # bytes freed after N hours of inactivity

async def memory_cleanup_loop():
    """Hourly: drop image bytes for users inactive > INACTIVE_TTL seconds."""
    await asyncio.sleep(60)
    while True:
        try:
            now = time.time()
            stale = [uid for uid, ts in USER_LAST_ACTIVE.items() if now - ts > INACTIVE_TTL]
            for uid in stale:
                USER_REFS.pop(uid, None)
                USER_LAST_OUTPUT.pop(uid, None)
                USER_LAST_ACTIVE.pop(uid, None)
                # USER_HISTORY kept (small, text-like in RAM; clear only refs/output bytes)
            if stale:
                print(f"[cleanup] freed image bytes for {len(stale)} inactive users")
        except Exception as e:
            print("[cleanup] error:", str(e)[:160])
        await asyncio.sleep(3600)

async def nudge_loop():
    # Run hourly; send up to NUDGE_BATCH_LIMIT eligible nudges
    await asyncio.sleep(5)
    while True:
        try:
            if NUDGE_ENABLED and STATS_USERS_INFO:
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
def assess_selfie_quality(img_bytes: bytes) -> Tuple[bool, str]:
    if Image is None or ImageStat is None or ImageFilter is None:
        return True, "unchecked"
    try:
        im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        w, h = im.size
        if w < 320 or h < 320:
            return False, "small"
        gray = im.convert("L")
        mean = ImageStat.Stat(gray).mean[0]
        if mean < 35:
            return False, "dark"
        if mean > 240:
            return False, "overexposed"
        edges = gray.filter(ImageFilter.FIND_EDGES)
        edge_mean = ImageStat.Stat(edges).mean[0]
        if edge_mean < 4.0:
            return False, "blurry"
        return True, "ok"
    except Exception:
        return True, "unreadable_skip"

def preprocess_selfie(img_bytes: bytes, max_side: int = 1024) -> bytes:
    """Normalize selfie before InstantID: square-center-crop + resize + JPEG.

    InstantID extracts face embeddings more accurately from a tightly framed,
    square portrait than from a wide landscape or full-body photo.
    Falls back to original bytes on any error.
    """
    if Image is None:
        return img_bytes
    try:
        im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
        w, h = im.size

        # Center-crop to square (removes edges, keeps face area)
        side = min(w, h)
        left  = (w - side) // 2
        top   = max(0, (h - side) // 3)   # bias toward top third — faces are rarely at bottom
        top   = min(top, h - side)
        im = im.crop((left, top, left + side, top + side))

        # Downscale if larger than max_side (no upscaling)
        if side > max_side:
            im = im.resize((max_side, max_side), Image.LANCZOS)

        buf = io.BytesIO()
        im.save(buf, format="JPEG", quality=92)
        return buf.getvalue()
    except Exception as e:
        print(f"preprocess_selfie error (using original): {e}")
        return img_bytes

def selfie_quality_text(chat_id: int, reason: str) -> str:
    lang = USER_LANG.get(chat_id, LANG_DEFAULT)
    if lang == "ru":
        return "Фото слишком тёмное, маленькое или размытое. Пришлите чёткое селфи крупнее, с лицом в хорошем свете."
    if lang == "ro":
        return "Poza este prea întunecată, mică sau neclară. Trimite un selfie clar, mai mare, cu fața bine luminată."
    if lang == "de":
        return "Das Foto ist zu dunkel, klein oder unscharf. Bitte sende ein klares, größeres Selfie mit gut beleuchtetem Gesicht."
    return "The photo is too dark, small, or blurry. Please send a clear larger selfie with your face in good light."

def generate_image_from_bytes(
    img_bytes: bytes,
    user_prompt: str,
    lang: str = "ru",
    strict: bool = False,
    style_bytes: Optional[bytes] = None,
    lock_scene: bool = True,
    user_id: Optional[int] = None,
    job_id: Optional[str] = None,
) -> Optional[bytes]:
    t0 = time.time()
    if user_id is not None:
        USER_LAST_ACTIVE[int(user_id)] = t0
    if job_id is None:
        job = record_job(
            kind="generation",
            status="running",
            chat_id=user_id,
            prompt=user_prompt,
            model=INSTANTID_MODEL,
        )
        job_id = str(job["job_id"])
    else:
        record_job(job_id, status="running", chat_id=user_id, prompt=user_prompt, model=INSTANTID_MODEL)
    if user_id is not None:
        USER_LAST_JOB[int(user_id)] = str(job_id)
    job_event(job_id, "generation_started", strict=strict, lock_scene=lock_scene)
    if blocked(user_prompt):
        print("⛔ Заблокировано фильтром")
        record_job(job_id, status="failed", error="blocked")
        job_event(job_id, "generation_failed", error="blocked")
        return None

    # In strict (Copy Mode), avoid GPT rephrasing to keep scene constraints intact
    refined = craft_prompt_gpt(user_prompt, lang=lang, allow_refine=not strict)
    if user_id is not None:
        USER_LAST_REFINED_PROMPT[user_id] = refined
    if strict and lock_scene:
        refined = f"{refined}. {SCENE_LOCK}. Exact same background, composition, lighting, color grading; only replace the face."

    # Beauty + quality suffix fed to InstantID for naturally beautiful skin/lighting
    QUALITY_SUFFIX = (
        "sharp focus, flawless complexion, professional skin retouching, "
        "perfect skin, bright eyes, beautiful lighting, "
        "professional photography, 8k resolution, award-winning photograph"
    )
    refined = f"{refined}. {QUALITY_SUFFIX}"

    print(f"→ Генерация: {refined[:180]}...")
    job_event(job_id, "prompt_refined", prompt=refined[:500])

    src_url = s3_put_and_presign(img_bytes, key_prefix="inputs/")
    if not src_url:
        print("→ Не удалось получить S3 presigned URL")
        record_job(job_id, status="failed", error="s3_input_failed")
        job_event(job_id, "generation_failed", error="s3_input_failed")
        return None
    job_event(job_id, "s3_input_ready")

    style_url: Optional[str] = None
    if strict and style_bytes:
        style_url = s3_put_and_presign(style_bytes, key_prefix="style/")
        if not style_url:
            print("→ Не удалось получить S3 URL для style-ref (продолжаем без него)")
        else:
            job_event(job_id, "s3_style_ready")

    # Copy mode: face swap first — reference stays intact, only face changes
    if strict and style_bytes:
        job_event(job_id, "replicate_request", model="faceswap")
        swapped = face_swap(img_bytes, style_bytes)
        if swapped:
            try:
                sw_md5  = hashlib.md5(swapped).hexdigest()
                ref_md5 = hashlib.md5(style_bytes).hexdigest()
                if sw_md5 != ref_md5:  # sanity: not an echo of the reference
                    final = enhance_face_codeformer(swapped, fidelity=0.85)
                    latency_ms = int((time.time() - t0) * 1000)
                    stats_incr("generation_latency_total_ms", latency_ms)
                    stats_incr("generation_latency_count", 1)
                    record_job(job_id, status="generated")
                    job_event(job_id, "generation_done", latency_ms=latency_ms, output_bytes=len(final))
                    return final
                print("FaceSwap echoed reference — falling back to InstantID")
            except Exception as _fs_err:
                print(f"FaceSwap post-processing error: {_fs_err}")
        print("FaceSwap failed — falling back to InstantID")

    # Preprocess selfie for better InstantID face embedding extraction
    _selfie_for_iid = preprocess_selfie(img_bytes)

    def try_instantid(p: str) -> Optional[str]:
        global REPLICATE_LAST_ERROR
        neg = f"{INSTANTID_NEGATIVE}"
        if strict:
            neg = f"{STRICT_NEGATIVE}, {neg}"

        # InstantID — передаём изображение напрямую как bytes, не через S3 URL
        # (Backblaze B2 presigned URLs могут быть недоступны из Replicate)
        if INSTANTID_MODEL:
            try:
                _premium = user_id is not None and not is_free_user(int(user_id))
                iid_inputs: Dict[str, Any] = {
                    "image": io.BytesIO(_selfie_for_iid),
                    "prompt": p,
                    "negative_prompt": neg,
                    "ip_adapter_scale": 0.85 if strict else 0.80,
                    "num_inference_steps": 50 if _premium else 30,
                    "guidance_scale": 5.5 if _premium else 5.0,
                    "width": 1024,
                    "height": 1024,
                }
                job_event(job_id, "replicate_request", model="instantid")
                t0_iid = time.time()
                out = replicate.run(INSTANTID_MODEL, input=iid_inputs)
                print(f"InstantID output type={type(out).__name__} val={str(out)[:200]}")
                url = _extract_first_url(out)
                if url == "SENSITIVE":
                    return "SENSITIVE"
                if url:
                    print(f"InstantID OK ({int((time.time()-t0_iid)*1000)}ms) url={url[:60]}")
                    return url
                REPLICATE_LAST_ERROR = f"[InstantID] no url in output: {str(out)[:120]}"
            except Exception as e:
                REPLICATE_LAST_ERROR = f"[InstantID] {str(e)[:200]}"
                print("InstantID error:", str(e)[:300])

        # PhotoMaker — тоже с прямой загрузкой bytes
        if PHOTOMAKER_MODEL:
            try:
                pm_inputs: Dict[str, Any] = {
                    "input_image": io.BytesIO(img_bytes),
                    "prompt": f"img, {p}",
                    "negative_prompt": neg,
                    "num_steps": 30,
                    "style_strength_ratio": 20,
                }
                job_event(job_id, "replicate_request", model="photomaker")
                t0_pm = time.time()
                out = replicate.run(PHOTOMAKER_MODEL, input=pm_inputs)
                print(f"PhotoMaker output type={type(out).__name__} val={str(out)[:200]}")
                url = _extract_first_url(out)
                if url == "SENSITIVE":
                    return "SENSITIVE"
                if url:
                    print(f"PhotoMaker OK ({int((time.time()-t0_pm)*1000)}ms)")
                    return url
                REPLICATE_LAST_ERROR = f"[PhotoMaker] no url in output: {str(out)[:120]}"
            except Exception as e:
                REPLICATE_LAST_ERROR = f"[PhotoMaker] {str(e)[:200]}"
                print("PhotoMaker error:", str(e)[:300])

        # Legacy fallback: NanoBanana (only if env var is set)
        if NANOBANANA_MODEL:
            try:
                nano_inputs: Dict[str, Any] = {
                    "prompt": p,
                    "output_format": "jpg",
                    "image_input": [src_url],
                }
                job_event(job_id, "replicate_request", model="nanobanana")
                url = replicate_generate(NANOBANANA_MODEL, nano_inputs)
                if url == "SENSITIVE":
                    return "SENSITIVE"
                if url:
                    print("NanoBanana OK (legacy fallback)")
                    return url
            except Exception as e:
                print("NanoBanana exception:", str(e)[:200])

        return None

    gen_url = try_instantid(refined)
    if gen_url == "SENSITIVE":
        print("→ Sensitive → safer variant")
        gen_url = try_instantid(safer_variant(refined))

    # Если не получилось — повторить с упрощённым промптом
    if (not gen_url or not str(gen_url).startswith("http")) and not strict:
        gen_url = try_instantid(safer_variant(refined))

    if not gen_url or gen_url == "SENSITIVE" or not gen_url.startswith("http"):
        print("→ gen_url пустой/sensitive")
        record_job(job_id, status="failed", error="empty_generation_url")
        job_event(job_id, "generation_failed", error="empty_generation_url")
        return None

    nano_bytes = _download_with_retries(gen_url)
    if not nano_bytes:
        print("→ не скачали NanoBanana")
        record_job(job_id, status="failed", error="download_failed")
        job_event(job_id, "generation_failed", error="download_failed")
        return None

    # Echo check BEFORE GFPGAN so re-encoding doesn't mask the comparison
    try:
        output_md5 = hashlib.md5(nano_bytes).hexdigest()
        selfie_md5 = hashlib.md5(img_bytes).hexdigest()
        style_md5  = hashlib.md5(style_bytes).hexdigest() if style_bytes else None
        if output_md5 == selfie_md5 or (style_md5 and output_md5 == style_md5):
            print("→ output equals input (likely echo) — treating as failure")
            record_job(job_id, status="failed", error="output_equals_input")
            job_event(job_id, "generation_failed", error="output_equals_input")
            return None
    except Exception:
        pass

    # Professional face retouch: CodeFormer (fidelity=0.8 → subtle, identity-preserving)
    # falls back to GFPGAN, then original on any error
    nano_bytes = enhance_face_codeformer(nano_bytes, fidelity=0.8)

    latency_ms = int((time.time() - t0) * 1000)
    stats_incr("generation_latency_total_ms", latency_ms)
    stats_incr("generation_latency_count", 1)
    record_job(job_id, status="generated")
    job_event(job_id, "generation_done", latency_ms=latency_ms, output_bytes=len(nano_bytes))
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

    # Dedup key
    try:
        key_src = (before or b"") + (after or b"")
        sig = "ch:" + hashlib.md5(key_src).hexdigest()
        now = time.time()
        # prune
        for k,v in list(RECENT_PUB.items()):
            if now - v > RECENT_PUB_TTL:
                RECENT_PUB.pop(k, None)
        if RECENT_PUB.get(sig) and now - RECENT_PUB[sig] < RECENT_PUB_TTL:
            return
        RECENT_PUB[sig] = now
    except Exception:
        pass

    if before:
        media = [
            InputMediaPhoto(type="photo", media=BufferedInputFile(before, filename="before.jpg"), caption="До"),
            InputMediaPhoto(type="photo", media=BufferedInputFile(after,  filename="after.jpg"),  caption=f"После · {cap}"),
        ]
        try:
            await bot.send_media_group(chat_id=GALLERY_CHANNEL_ID, media=media)
        except Exception as e:
            print("auto-post (album) error:", str(e)[:160])
        # prompt-share removed
    else:
        try:
            await bot.send_photo(
                chat_id=GALLERY_CHANNEL_ID,
                photo=BufferedInputFile(after, filename="after.jpg"),
                caption=cap
            )
        except Exception as e:
            print("auto-post (single) error:", str(e)[:160])
        # prompt-share removed
    stats_incr("auto_post", 1)

# ===================== UI ============================
def kb_actions(chat_id: int) -> InlineKeyboardMarkup:
    lang = L(chat_id)
    rows = [
        [
            InlineKeyboardButton(text="🔄 " + lang.get("btn_more", "More"),           callback_data="more"),
            InlineKeyboardButton(text=lang.get("menu_swap", "💎 Swap"),               callback_data="swap_open"),
            InlineKeyboardButton(text="✨ " + lang.get("btn_publish", "Publish"),      callback_data="pub_yes"),
        ],
        [
            InlineKeyboardButton(text=lang["menu_copy"],                              callback_data="copy_open"),
            InlineKeyboardButton(text=lang.get("menu_presets", "📸 Presets"),          callback_data="presets_open"),
            InlineKeyboardButton(text=lang.get("btn_upsell", "🔥 100 gens — 1200★"), callback_data="buy_stars_100"),
        ],
    ]
    try:
        if PUBLISH_GROUP_ID:
            rows.append([
                InlineKeyboardButton(text=lang.get("btn_publish_group", "To group"), callback_data="pub_group"),
            ])
    except Exception:
        pass
    return InlineKeyboardMarkup(inline_keyboard=rows)

def main_menu_inline(chat_id: int) -> InlineKeyboardMarkup:
    lang = L(chat_id)
    rows = [
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
    ]
    if WEBHOOK_BASE:
        rows.append([InlineKeyboardButton(text="📱 iModel Mini App", web_app=WebAppInfo(url=f"{WEBHOOK_BASE}/webapp"))])
    return InlineKeyboardMarkup(inline_keyboard=rows)

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

def create_style_share(style_bytes: bytes) -> Optional[str]:
    try:
        token = hashlib.md5(style_bytes + os.urandom(4)).hexdigest()[:12]
        entry: Dict[str, object] = {"bytes": style_bytes}
        # Try S3 upload for resilience
        try:
            key = f"shares/{int(time.time())}_{token}.jpg"
            _s3.put_object(Bucket=S3_BUCKET, Key=key, Body=style_bytes, ContentType="image/jpeg")
            entry["s3key"] = key
        except Exception as e:
            print("style share s3 error:", str(e)[:120])
        STYLE_SHARES[token] = entry
        return token
    except Exception as e:
        print("create_style_share error:", str(e)[:120])
    return None

def resolve_style_share(token: str) -> Optional[bytes]:
    entry = STYLE_SHARES.get(token)
    if entry and isinstance(entry.get("bytes"), (bytes, bytearray)):
        return bytes(entry["bytes"])  # type: ignore[index]
    # Try S3 if key present
    try:
        key = entry.get("s3key") if entry else None  # type: ignore[assignment]
        if key and S3_BUCKET:
            obj = _s3.get_object(Bucket=S3_BUCKET, Key=key)
            return obj["Body"].read()
    except Exception as e:
        print("resolve share s3 error:", str(e)[:120])
    return None

# prompt-share removed

def _pluralize_ru(n: int, lang: dict) -> str:
    """Return correct plural form for 'generation' in Russian (1/2/5 rule)."""
    if lang.get("credits_gen_1", "generation") == "генерация":
        if n % 100 in range(11, 20):
            return lang.get("credits_gen_5", "генераций")
        r = n % 10
        if r == 1:
            return lang.get("credits_gen_1", "генерация")
        elif r in (2, 3, 4):
            return lang.get("credits_gen_2", "генерации")
        return lang.get("credits_gen_5", "генераций")
    return lang.get("credits_gen_2", "generations")

async def _send_credits_hint(m: Message, uid: int, username: Optional[str] = None):
    """Send remaining-credits nudge after a successful generation. Silent for free users."""
    if is_free_user(uid, username):
        return
    n = USER_CREDITS.get(uid, 0)
    lang = L(uid)
    if n <= 0:
        return  # paywall will trigger on next attempt
    if n == 1:
        txt = lang.get("credits_last", "⚠️ Last generation! Top up → /buy")
    else:
        gen_word = _pluralize_ru(n, lang)
        txt = lang.get("credits_low", "🔋 Remaining: {n} {gen}").format(n=n, gen=gen_word)
    try:
        await m.answer(txt)
    except Exception:
        pass

def kb_invite_buy(chat_id: int) -> InlineKeyboardMarkup:
    lang = L(chat_id)
    invite_text = lang.get("btn_invite", "👥 Invite a friend (+{n} free)").format(n=REF_BONUS_REF)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=lang.get("buy_btn_10",  "✨ 10 gens — 200★"),  callback_data="buy_stars_10")],
        [InlineKeyboardButton(text=lang.get("buy_btn_30",  "⚡ 30 gens — 500★"),  callback_data="buy_stars_30")],
        [InlineKeyboardButton(text=lang.get("buy_btn_100", "🔥 100 gens — 1200★"), callback_data="buy_stars_100")],
        [InlineKeyboardButton(text=lang.get("buy_btn_300", "💎 300 gens — 2500★"), callback_data="buy_stars_300")],
        [InlineKeyboardButton(text=invite_text, callback_data="refer_open")],
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
    n = USER_CREDITS.get(m.chat.id, FREE_QUOTA)
    invite_text = lang.get("btn_invite", "👥 Invite a friend (+{n} free)").format(n=REF_BONUS_REF)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=lang["buy_btn_10"],  callback_data="buy_stars_10")],
        [InlineKeyboardButton(text=lang["buy_btn_30"],  callback_data="buy_stars_30")],
        [InlineKeyboardButton(text=lang["buy_btn_100"], callback_data="buy_stars_100")],
        [InlineKeyboardButton(text=lang.get("buy_btn_300", "💎 300 gens — 2500★"), callback_data="buy_stars_300")],
        [InlineKeyboardButton(text=invite_text, callback_data="refer_open")],
    ])
    balance_line = f"\n\n🔋 Баланс: {n} ген." if not is_free_user(m.chat.id, getattr(m.from_user, "username", None)) else ""
    await safe_answer(m, lang["buy_title"] + balance_line, reply_markup=kb)

@dp.callback_query(F.data.startswith("buy_stars_"))
async def cb_buy_stars(c: CallbackQuery):
    pack = c.data.split("_")[-1]
    # subtle referral tooltip
    txt = L(c.message.chat.id).get("hint_refer_pay", "Invite a friend for free credits").format(ref_new=REF_BONUS_NEW, ref_ref=REF_BONUS_REF)
    if pack == "10":
        await send_stars_invoice(c.message.chat.id, "iModel — 10 генераций", "10 профессиональных фото", "pack_10", 200)
    elif pack == "30":
        await send_stars_invoice(c.message.chat.id, "iModel — 30 генераций", "30 профессиональных фото (−17%)", "pack_30", 500)
    elif pack == "100":
        await send_stars_invoice(c.message.chat.id, "iModel — 100 генераций", "100 профессиональных фото (−40%)", "pack_100", 1200)
    elif pack == "300":
        await send_stars_invoice(c.message.chat.id, "iModel — 300 генераций", "300 профессиональных фото (−58%)", "pack_300", 2500)
    await safe_cb_answer(c, txt)

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
    elif payload == "pack_300": add = 300
    # ensure user is recorded with username for admin visibility
    _touch_user(m.chat.id, getattr(m.from_user, "username", None))
    USER_CREDITS[m.chat.id] = USER_CREDITS.get(m.chat.id, 0) + add
    _credits_save()
    await safe_answer(m, L(m.chat.id)["bought"].format(add=add, all=USER_CREDITS[m.chat.id]))
    stats_incr("payments", 1)
    _uadd(m.chat.id, "payments", 1)
    # Notify admins about the purchase
    try:
        uname = getattr(m.from_user, "username", None)
        name = getattr(m.from_user, "full_name", None) or getattr(m.from_user, "first_name", "")
        xtr = None
        try:
            xtr = int(getattr(m.successful_payment, "total_amount", 0))
        except Exception:
            xtr = None
        await notify_admins_payment(
            user_id=m.chat.id,
            username=("@" + uname) if uname else None,
            name=name,
            pack=payload,
            gens=add,
            balance=USER_CREDITS.get(m.chat.id, 0),
            stars=xtr,
        )
    except Exception as e:
        print("notify admins (payment) error:", str(e)[:160])

# ===================== COMMANDS =======================
@dp.message(Command("version"))
async def cmd_version(m: Message):
    await safe_answer(m, f"{L(m.chat.id)['version'].format(ver=APP_VERSION)}")

@dp.message(Command("ping"))
async def cmd_ping(m: Message):
    try:
        await safe_answer(m, "pong")
    except Exception:
        pass

@dp.message(Command("diag"))
async def cmd_diag(m: Message):
    try:
        langs = ",".join(_GROUP_LANGS) if ' _GROUP_LANGS' or _GROUP_LANGS else "-"
    except Exception:
        langs = "-"
    last = int(time.time() - GROUP_POST_LAST_AT) if GROUP_POST_LAST_AT else None
    lines = [
        f"App: {APP_VERSION}",
        f"Lang: {USER_LANG.get(m.chat.id, LANG_DEFAULT)}",
        f"Webhook: {WEBHOOK_URL}",
        f"--- Models ---",
        f"InstantID: {INSTANTID_MODEL}",
        f"PhotoMaker: {PHOTOMAKER_MODEL}",
        f"NanoBanana: {NANOBANANA_MODEL or '<disabled>'}",
        f"S3: bucket={S3_BUCKET or '<empty>'} ep={S3_ENDPOINT[:30] if S3_ENDPOINT else '<empty>'}",
        f"Last Replicate error: {REPLICATE_LAST_ERROR[:300] if REPLICATE_LAST_ERROR else 'none'}",
        f"--- Posts ---",
        f"Group posts: enabled={GROUP_POSTS_ENABLED} running={GROUP_POST_LOOP_RUNNING}",
        f"Group id: {PUBLISH_GROUP_ID}",
        f"Langs rotation: {langs}",
        f"Every minutes: {GROUP_POST_EVERY_MINUTES}",
        f"Window: {GROUP_POST_START_HOUR}-{GROUP_POST_END_HOUR}",
        f"Last post: {last if last is not None else 'never'}s ago",
    ]
    await safe_answer(m, "\n".join(lines))

@dp.message(Command("post_now"))
async def cmd_post_now(m: Message):
    # Allow fallback to current chat if it's a group/supergroup
    target_id = PUBLISH_GROUP_ID or (m.chat.id if str(m.chat.id).startswith("-") else None)
    if not target_id:
        return await safe_answer(m, "Group not configured. Use /set_group_here in a group or /set_group <id>.")
    lang = _next_group_lang()
    txt = craft_group_post_text(lang, BOT_USERNAME_GLOBAL)
    img = generate_group_post_image(lang)
    try:
        if img:
            await bot.send_photo(chat_id=target_id, photo=BufferedInputFile(img, filename="promo.jpg"), caption=txt)
        else:
            await bot.send_message(chat_id=target_id, text=txt)
        global GROUP_POST_LAST_AT
        GROUP_POST_LAST_AT = time.time()
        await safe_answer(m, f"Posted ({lang})")
    except Exception as e:
        await safe_answer(m, f"Post error: {str(e)[:160]}")

@dp.message(Command("set_group_here"))
async def cmd_set_group_here(m: Message):
    if not is_admin(m.chat.id, getattr(m.from_user, "username", None)):
        return await safe_answer(m, L(m.chat.id)["admin_only"])
    if not str(m.chat.id).startswith("-"):
        return await safe_answer(m, "Run this command inside a group/supergroup.")
    global PUBLISH_GROUP_ID
    PUBLISH_GROUP_ID = m.chat.id
    await safe_answer(m, f"Group set to {PUBLISH_GROUP_ID}")

@dp.message(Command("set_group"))
async def cmd_set_group(m: Message):
    if not is_admin(m.chat.id, getattr(m.from_user, "username", None)):
        return await safe_answer(m, L(m.chat.id)["admin_only"])
    parts = (m.text or "").split()
    if len(parts) < 2:
        return await safe_answer(m, "Usage: /set_group -1001234567890")
    try:
        gid = int(parts[1])
    except Exception:
        return await safe_answer(m, "Invalid group id")
    global PUBLISH_GROUP_ID
    PUBLISH_GROUP_ID = gid
    await safe_answer(m, f"Group set to {PUBLISH_GROUP_ID}")

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

@dp.message(Command("grant"))
async def cmd_grant(m: Message):
    username = getattr(m.from_user, "username", None)
    if not has_grant(m.chat.id, username, "users.manage"):
        return await safe_answer(m, L(m.chat.id)["admin_only"])
    parts = (m.text or "").split()
    if len(parts) < 3:
        roles = ", ".join(sorted(VALID_ROLES))
        return await safe_answer(m, f"Usage: /grant <telegram_id> <role>\nRoles: {roles}")
    try:
        target_uid = int(parts[1])
    except Exception:
        return await safe_answer(m, "Invalid telegram_id")
    role = parts[2].strip().lower()
    if role not in VALID_ROLES:
        return await safe_answer(m, f"Invalid role. Use: {', '.join(sorted(VALID_ROLES))}")
    USER_ROLES[target_uid] = role
    info = STATS_USERS_INFO.setdefault(target_uid, {"first_seen": time.time(), "last_seen": time.time(), "username": ""})
    users_save(target_uid)
    audit_log(m.chat.id, "role.set", target_uid, role=role)
    await safe_answer(m, f"✅ Role for {target_uid}: {role}")

@dp.message(Command("credits"))
async def cmd_credits_admin(m: Message):
    username = getattr(m.from_user, "username", None)
    if not has_grant(m.chat.id, username, "credits.grant"):
        return await safe_answer(m, L(m.chat.id)["admin_only"])
    parts = (m.text or "").split()
    if len(parts) < 3:
        return await safe_answer(m, "Usage: /credits <telegram_id> <delta>")
    try:
        target_uid = int(parts[1])
        delta = int(parts[2])
    except Exception:
        return await safe_answer(m, "Invalid arguments")
    ensure_user_credit(target_uid)
    USER_CREDITS[target_uid] = int(USER_CREDITS.get(target_uid, FREE_QUOTA)) + delta
    _credits_save()
    audit_log(m.chat.id, "credits.delta", target_uid, delta=delta, balance=USER_CREDITS[target_uid])
    await safe_answer(m, f"✅ Balance for {target_uid}: {USER_CREDITS[target_uid]}")

@dp.message(Command("copy"))
async def cmd_copy(m: Message):
    USER_COPY_MODE.add(m.chat.id)
    USER_COPY_STYLE.pop(m.chat.id, None)
    USER_COPY_PROMPT.pop(m.chat.id, None)
    await safe_answer(m, L(m.chat.id)["copy_intro"])

@dp.message(Command("app"))
async def cmd_app(m: Message):
    if not WEBHOOK_BASE:
        return await safe_answer(m, "Mini App URL is not configured.")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Open iModel Mini App", web_app=WebAppInfo(url=f"{WEBHOOK_BASE}/webapp"))]
    ])
    await safe_answer(m, "iModel Mini App", reply_markup=kb)


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
                USER_CREDITS[ref_id] = USER_CREDITS.get(ref_id, FREE_QUOTA) + REF_BONUS_REF
                _credits_save()
                stats_incr("referrals", 1)
                stats_incr("ref_bonus_ref", REF_BONUS_REF)
                stats_incr("ref_bonus_invited", REF_BONUS_NEW)
        except Exception:
            pass

    # Deep-link: start=style_<token> → preload Copy Mode with style
    if len(parts) > 1 and parts[1].startswith("style_"):
        token = parts[1][6:]
        sty = resolve_style_share(token)
        if sty:
            USER_COPY_MODE.add(m.chat.id)
            USER_COPY_STYLE[m.chat.id] = sty
            USER_COPY_PROMPT.pop(m.chat.id, None)
            await safe_answer(m, L(m.chat.id)["style_share_intro"])
            USER_ONBOARDED.add(m.chat.id)
            return

    # prompt-share deep-link removed

    ensure_user_credit(m.chat.id)
    USER_SEEN_TEXT.discard(m.chat.id)
    if m.chat.id not in USER_ONBOARDED:
        lang = L(m.chat.id)
        welcome_text = lang["onboard_welcome"].format(quota=FREE_QUOTA)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=lang["onboard_btn"], callback_data="onboard_go")],
            [
                InlineKeyboardButton(text="🇷🇺", callback_data="set_lang_ru"),
                InlineKeyboardButton(text="🇬🇧", callback_data="set_lang_en"),
                InlineKeyboardButton(text="🇷🇴", callback_data="set_lang_ro"),
                InlineKeyboardButton(text="🇩🇪", callback_data="set_lang_de"),
            ],
        ])
        if DEMO_PHOTO:
            try:
                await bot.send_photo(m.chat.id, photo=DEMO_PHOTO, caption=welcome_text, reply_markup=kb, parse_mode="Markdown")
            except Exception:
                await safe_answer(m, welcome_text, reply_markup=kb, parse_mode="Markdown")
        else:
            await safe_answer(m, welcome_text, reply_markup=kb, parse_mode="Markdown")
        return
    # Returning user: short greeting, push to action
    STATS_USERS.add(m.chat.id)
    if USER_LAST_OUTPUT.get(m.chat.id):
        # Show their last result with action keyboard as reminder
        try:
            await bot.send_photo(
                m.chat.id,
                photo=BufferedInputFile(USER_LAST_OUTPUT[m.chat.id], filename="last.jpg"),
                caption=L(m.chat.id)["start"],
                reply_markup=kb_actions(m.chat.id),
            )
            return
        except Exception:
            pass
    await safe_answer(m, L(m.chat.id)["start"], reply_markup=main_menu_inline(m.chat.id))

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
    chat_id = c.message.chat.id
    USER_LANG[chat_id] = code
    USER_SEEN_TEXT.add(chat_id)
    await safe_cb_answer(c)
    lang = L(chat_id)
    # If user hasn't onboarded yet, show updated welcome instead of main menu
    if chat_id not in USER_ONBOARDED:
        welcome_text = lang["onboard_welcome"].format(quota=FREE_QUOTA)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=lang["onboard_btn"], callback_data="onboard_go")],
            [
                InlineKeyboardButton(text="🇷🇺", callback_data="set_lang_ru"),
                InlineKeyboardButton(text="🇬🇧", callback_data="set_lang_en"),
                InlineKeyboardButton(text="🇷🇴", callback_data="set_lang_ro"),
                InlineKeyboardButton(text="🇩🇪", callback_data="set_lang_de"),
            ],
        ])
        await c.message.answer(welcome_text, reply_markup=kb, parse_mode="Markdown")
    else:
        key = {"ru": "lang_ru", "en": "lang_en", "ro": "lang_ro", "de": "lang_de"}[code]
        await c.message.answer(lang[key], reply_markup=main_menu_inline(chat_id))

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
    msg = L(m.chat.id)["refer_msg"].format(link=link, count=st["count"], earned=st["earned"])
    await safe_answer(m, msg)

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
    _uname = getattr(c.from_user, "username", None)
    if not await _try_use_credit(chat_id, _uname):
        return await c.message.answer(L(chat_id)["credits_none"], reply_markup=kb_invite_buy(chat_id))
    msg = await c.message.answer(L(chat_id)["gen"])
    ref = refs[-1]
    _lang = USER_LANG.get(chat_id, LANG_DEFAULT)
    _prog = asyncio.create_task(_progress_loop(msg, _lang))
    try:
        result = await asyncio.to_thread(
            generate_image_from_bytes,
            ref, preset.prompt, lang=_lang, user_id=chat_id
        )
    finally:
        _prog.cancel()
    if not result:
        await _refund_credit(chat_id, _uname)
        stats_incr("gens_fail", 1)
        _uadd(chat_id, "gens_fail", 1)
        return await safe_edit_text(msg, L(chat_id)["fail"])
    USER_LAST_OUTPUT[chat_id] = result
    USER_LAST_PROMPT[chat_id] = preset.prompt
    LAST_PHOTO[chat_id] = result
    stats_incr("gens_ok", 1)
    _uadd(chat_id, "gens_ok", 1)
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
    await c.message.answer_photo(
        photo=BufferedInputFile(result, filename="imodel_result.jpg"),
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
    lang = L(chat_id)
    selfie_prompt = lang.get("onboard_send_selfie", "📷 Send your selfie — I'll create your first photo right now.")
    await c.message.answer(selfie_prompt, parse_mode="Markdown")


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

@dp.callback_query(F.data == "swap_open")
async def cb_swap_open(c: CallbackQuery):
    uid = c.message.chat.id
    lang = L(uid)
    await safe_cb_answer(c)
    if not USER_REFS.get(uid):
        return await c.message.answer(lang.get("swap_no_selfie", "Send a selfie first."))
    USER_SWAP_MODE.add(uid)
    USER_COPY_MODE.discard(uid)
    await c.message.answer(lang.get("swap_intro", "💎 Exact Swap\nSend any photo — I'll place your face into it."))

@dp.callback_query(F.data == "pub_yes")
async def cb_pub_yes(c: CallbackQuery):
    if not GALLERY_CHANNEL_ID:
        await safe_cb_answer(c)
        return await c.message.answer(L(c.message.chat.id)["err_channel_not_configured"])
    before = LAST_REF.get(c.message.chat.id)
    after  = LAST_PHOTO.get(c.message.chat.id)
    if not after:
        await safe_cb_answer(c)
        return await c.message.answer(L(c.message.chat.id)["err_no_result"])
    # Deduplicate recent publishes (same before/after) to avoid repeats
    try:
        key_src = (before or b"") + (after or b"")
        sig = "ch:" + hashlib.md5(key_src).hexdigest()
        now = time.time()
        for k, v in list(RECENT_PUB.items()):
            if now - v > RECENT_PUB_TTL:
                RECENT_PUB.pop(k, None)
        if RECENT_PUB.get(sig) and now - RECENT_PUB[sig] < RECENT_PUB_TTL:
            await safe_cb_answer(c, L(c.message.chat.id)["published_recent"])
            return
        RECENT_PUB[sig] = now
    except Exception:
        pass
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
            cap = L(c.message.chat.id)["before_after"] if i == 1 else None
            if i == 0:
                media.append(InputMediaPhoto(type="photo", media=BufferedInputFile(b, filename="before.jpg"), caption=L(c.message.chat.id)["before"]))
            else:
                media.append(InputMediaPhoto(type="photo", media=BufferedInputFile(b, filename="after.jpg"), caption=cap))
        try:
            await bot.send_media_group(chat_id=GALLERY_CHANNEL_ID, media=media)
        except Exception as e:
            print("channel media group error:", str(e)[:160])
    # prompt-share removed
    stats_incr("published_channel", 1)
    _uadd(c.message.chat.id, "published", 1)
    await safe_cb_answer(c, L(c.message.chat.id)["published_ok"])

@dp.callback_query(F.data == "pub_group")
async def cb_pub_group(c: CallbackQuery):
    if not PUBLISH_GROUP_ID:
        await safe_cb_answer(c)
        return await c.message.answer(L(c.message.chat.id)["err_group_not_configured"])
    before = LAST_REF.get(c.message.chat.id)
    after  = LAST_PHOTO.get(c.message.chat.id)
    if not after:
        await safe_cb_answer(c)
        return await c.message.answer(L(c.message.chat.id)["err_no_result"])
    # Deduplicate recent publishes (same before/after)
    try:
        key_src = (before or b"") + (after or b"")
        sig = "gr:" + hashlib.md5(key_src).hexdigest()
        now = time.time()
        for k, v in list(RECENT_PUB.items()):
            if now - v > RECENT_PUB_TTL:
                RECENT_PUB.pop(k, None)
        if RECENT_PUB.get(sig) and now - RECENT_PUB[sig] < RECENT_PUB_TTL:
            await safe_cb_answer(c, L(c.message.chat.id)["published_recent"])
            return
        RECENT_PUB[sig] = now
    except Exception:
        pass
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
            cap = L(c.message.chat.id)["before_after"] if i == 1 else None
            if i == 0:
                media.append(InputMediaPhoto(type="photo", media=BufferedInputFile(b, filename="before.jpg"), caption=L(c.message.chat.id)["before"]))
            else:
                media.append(InputMediaPhoto(type="photo", media=BufferedInputFile(b, filename="after.jpg"), caption=cap))
        try:
            await bot.send_media_group(chat_id=PUBLISH_GROUP_ID, media=media)
        except Exception as e:
            print("group media group error:", str(e)[:160])
    # prompt-share removed
    stats_incr("published_group", 1)
    _uadd(c.message.chat.id, "published", 1)
    await safe_cb_answer(c, L(c.message.chat.id)["published_group_ok"])

# ===================== FLOW: PHOTO ====================
@dp.message(F.photo)
async def on_photo(m: Message):
    try:
        await _on_photo_inner(m)
    except Exception as e:
        log_event("on_photo_error", chat_id=m.chat.id, error=str(e)[:240])
        await safe_answer(m, L(m.chat.id).get("error_try_again", "❌ Что-то пошло не так. Попробуйте ещё раз."))

async def _on_photo_inner(m: Message):
    if m.chat.id not in USER_LANG:
        USER_LANG[m.chat.id] = locale_to_lang(getattr(m.from_user, "language_code", None))

    f = await bot.get_file(m.photo[-1].file_id)
    b = await bot.download_file(f.file_path)
    img_bytes = b.read()
    stats_incr("photos", 1)
    STATS_USERS.add(m.chat.id)
    _touch_user(m.chat.id, getattr(m.from_user, "username", None))
    _uadd(m.chat.id, "photos", 1)

    # ----- Swap Mode (face swap selfie into target photo) -----
    if m.chat.id in USER_SWAP_MODE:
        uid = m.chat.id
        lang = L(uid)
        USER_SWAP_MODE.discard(uid)
        selfie_bytes = (USER_REFS.get(uid) or [None])[-1]
        if not selfie_bytes:
            return await safe_answer(m, lang.get("swap_no_selfie", "Send a selfie first."))
        _uname_sw = getattr(m.from_user, "username", None)
        if not await _try_use_credit(uid, _uname_sw):
            return await safe_answer(m, lang["credits_none"], reply_markup=kb_invite_buy(uid))
        wait = await safe_answer(m, lang["gen"])
        _lang_sw = USER_LANG.get(uid, LANG_DEFAULT)
        _prog = asyncio.create_task(_progress_loop(wait, _lang_sw))
        try:
            result_bytes = await asyncio.to_thread(face_swap, selfie_bytes, img_bytes)
            if result_bytes:
                result_bytes = await asyncio.to_thread(enhance_face_codeformer, result_bytes, 0.85)
        except Exception as _sw_err:
            print(f"Swap mode error: {_sw_err}")
            result_bytes = None
        finally:
            _prog.cancel()
        if not result_bytes:
            await _refund_credit(uid, _uname_sw)
            if wait: await safe_edit_text(wait, lang.get("swap_fail", "Swap failed. Try a different photo."))
            return
        USER_LAST_OUTPUT[uid] = result_bytes
        LAST_PHOTO[uid] = result_bytes
        stats_incr("gens_swap_ok", 1)
        _uadd(uid, "gens_swap_ok", 1)
        hist = USER_HISTORY.setdefault(uid, [])
        hist.append(result_bytes)
        if len(hist) > GALLERY_LIMIT:
            del hist[:-GALLERY_LIMIT]
        if wait: await wait.delete()
        await safe_answer_photo(
            m,
            BufferedInputFile(result_bytes, filename="imodel_swap.jpg"),
            caption=lang.get("swap_done", "Done ✅"),
            reply_markup=kb_actions(uid),
        )
        await _send_credits_hint(m, uid, _uname_sw)
        return

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
            ok, reason = assess_selfie_quality(img_bytes)
            if not ok:
                log_event("selfie_rejected", chat_id=m.chat.id, reason=reason)
                return await safe_answer(m, selfie_quality_text(m.chat.id, reason))

            # 1) Берём уже подготовленный/отредактированный пользователем промпт, либо пробуем сгенерировать
            scene_spec = USER_COPY_PROMPT.get(m.chat.id)
            if not scene_spec:
                scene_spec = craft_mj_prompt_from_image(style_bytes)
            if not scene_spec:
                scene_spec = craft_scene_spec_from_image(style_bytes) or "person, same scene."
            USER_REFS.setdefault(m.chat.id, [])
            USER_REFS[m.chat.id] = (USER_REFS[m.chat.id] + [img_bytes])[-4:]
            LAST_REF[m.chat.id] = img_bytes  # «до»

            _uname_copy = getattr(m.from_user, "username", None)
            if not await _try_use_credit(m.chat.id, _uname_copy):
                return await safe_answer(m, L(m.chat.id)["credits_none"], reply_markup=kb_invite_buy(m.chat.id))

            wait = await safe_answer(m, L(m.chat.id)["gen"])
            _lang_copy = USER_LANG.get(m.chat.id, LANG_DEFAULT)
            _prog = asyncio.create_task(_progress_loop(wait, _lang_copy))
            try:
                final_bytes = await asyncio.to_thread(
                    generate_image_from_bytes,
                    img_bytes, scene_spec,
                    lang=_lang_copy, strict=True,
                    style_bytes=style_bytes, lock_scene=True, user_id=m.chat.id,
                )
                if not final_bytes:
                    final_bytes = await asyncio.to_thread(
                        generate_image_from_bytes,
                        img_bytes,
                        scene_spec + ". Keep face absolutely unchanged, do not beautify, do not reshape.",
                        lang=_lang_copy, strict=True,
                        style_bytes=style_bytes, lock_scene=True, user_id=m.chat.id,
                    )
            finally:
                _prog.cancel()
            if not final_bytes:
                await _refund_credit(m.chat.id, _uname_copy)
                if wait: await safe_edit_text(wait, L(m.chat.id)["fail"])
                stats_incr("gens_copy_fail", 1)
                _uadd(m.chat.id, "gens_copy_fail", 1)
                return

            USER_LAST_OUTPUT[m.chat.id] = final_bytes
            USER_LAST_PROMPT[m.chat.id] = scene_spec
            LAST_PHOTO[m.chat.id] = final_bytes
            stats_incr("gens_copy_ok", 1)
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
            await maybe_send_referral_hint(m.chat.id)
            await _send_credits_hint(m, m.chat.id, getattr(m.from_user, "username", None))

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
    ok, reason = assess_selfie_quality(img_bytes)
    if not ok:
        log_event("selfie_rejected", chat_id=m.chat.id, reason=reason)
        return await safe_answer(m, selfie_quality_text(m.chat.id, reason))

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
                _uname_preset = getattr(m.from_user, "username", None)
                if not await _try_use_credit(m.chat.id, _uname_preset):
                    return await safe_answer(m, L(m.chat.id)["credits_none"], reply_markup=kb_invite_buy(m.chat.id))
                wait = await safe_answer(m, L(m.chat.id)["gen"])
                _lang_p = USER_LANG.get(m.chat.id, LANG_DEFAULT)
                _prog = asyncio.create_task(_progress_loop(wait, _lang_p))
                try:
                    final_bytes = await asyncio.to_thread(
                        generate_image_from_bytes,
                        img_bytes, preset.prompt, lang=_lang_p, user_id=m.chat.id
                    )
                finally:
                    _prog.cancel()
                if not final_bytes:
                    await _refund_credit(m.chat.id, _uname_preset)
                    if wait: await safe_edit_text(wait, L(m.chat.id)["fail"])
                    stats_incr("gens_fail", 1)
                    _uadd(m.chat.id, "gens_fail", 1)
                    return
                USER_LAST_OUTPUT[m.chat.id] = final_bytes
                USER_LAST_PROMPT[m.chat.id] = preset.prompt
                LAST_PHOTO[m.chat.id] = final_bytes
                stats_incr("gens_ok", 1)
                _uadd(m.chat.id, "gens_ok", 1)
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
                await _send_credits_hint(m, m.chat.id, getattr(m.from_user, "username", None))
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

    _uname_photo = getattr(m.from_user, "username", None)
    if not await _try_use_credit(m.chat.id, _uname_photo):
        return await safe_answer(m, L(m.chat.id)["credits_none"], reply_markup=kb_invite_buy(m.chat.id))

    wait = await safe_answer(m, L(m.chat.id)["gen"])
    _lang_ph = USER_LANG.get(m.chat.id, LANG_DEFAULT)
    _prog = asyncio.create_task(_progress_loop(wait, _lang_ph))
    try:
        final_bytes = await asyncio.to_thread(
            generate_image_from_bytes,
            img_bytes, caption, lang=_lang_ph, user_id=m.chat.id
        )
    finally:
        _prog.cancel()
    if not final_bytes:
        await _refund_credit(m.chat.id, _uname_photo)
        if wait: await safe_edit_text(wait, L(m.chat.id)["fail"])
        stats_incr("gens_fail", 1)
        _uadd(m.chat.id, "gens_fail", 1)
        return

    USER_LAST_OUTPUT[m.chat.id] = final_bytes
    USER_LAST_PROMPT[m.chat.id] = caption
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
    await maybe_send_referral_hint(m.chat.id)
    await _send_credits_hint(m, m.chat.id, getattr(m.from_user, "username", None))

    if AUTO_POST and GALLERY_CHANNEL_ID:
        try:
            await post_before_after_to_channel(m.chat.id)
        except Exception as e:
            print("AUTO_POST error:", str(e)[:160])

# ===================== FLOW: TEXT =====================
@dp.message(F.text & ~F.text.startswith("/"))
async def on_prompt(m: Message):
    try:
        await _on_prompt_inner(m)
    except Exception as e:
        log_event("on_prompt_error", chat_id=m.chat.id, error=str(e)[:240])
        await safe_answer(m, L(m.chat.id).get("error_try_again", "❌ Что-то пошло не так. Попробуйте ещё раз."))

async def _on_prompt_inner(m: Message):
    # Если включён Copy Mode и пришёл текст — трактуем как ручное редактирование промпта для копирования сцены
    if m.chat.id in USER_COPY_MODE:
        USER_COPY_PROMPT[m.chat.id] = m.text.strip()
        await safe_answer(m, L(m.chat.id)["copy_prompt_updated"])
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

    _uname_text = getattr(m.from_user, "username", None)
    if not await _try_use_credit(m.chat.id, _uname_text):
        return await safe_answer(m, L(m.chat.id)["credits_none"])

    wait = await safe_answer(m, L(m.chat.id)["gen"])
    ref = refs[-1]
    _lang_txt = USER_LANG.get(m.chat.id, LANG_DEFAULT)
    _prog = asyncio.create_task(_progress_loop(wait, _lang_txt))
    try:
        final_bytes = await asyncio.to_thread(
            generate_image_from_bytes,
            ref, text, lang=_lang_txt, user_id=m.chat.id
        )
    finally:
        _prog.cancel()
    if not final_bytes:
        await _refund_credit(m.chat.id, _uname_text)
        if wait: await safe_edit_text(wait, L(m.chat.id)["fail"])
        stats_incr("gens_fail", 1)
        _uadd(m.chat.id, "gens_fail", 1)
        return

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

    _uname_regen = getattr(c.from_user, "username", None)
    if not await _try_use_credit(chat_id, _uname_regen):
        await safe_cb_answer(c)
        return await c.message.answer(L(chat_id)["credits_none"], reply_markup=kb_invite_buy(chat_id))

    await safe_cb_answer(c)
    msg = await c.message.answer(L(chat_id)["gen"])
    ref = refs[-1]
    _lang_regen = USER_LANG.get(chat_id, LANG_DEFAULT)
    _prog = asyncio.create_task(_progress_loop(msg, _lang_regen))
    try:
        result = await asyncio.to_thread(
            generate_image_from_bytes,
            ref, base_prompt, lang=_lang_regen, user_id=chat_id
        )
    finally:
        _prog.cancel()
    if not result:
        await _refund_credit(chat_id, _uname_regen)
        STATS["gens_fail"] += 1
        _uadd(chat_id, "gens_fail", 1)
        return await safe_edit_text(msg, L(chat_id)["fail"])

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
    await maybe_send_referral_hint(chat_id)
    # credits hint via a fake Message-like context isn't possible here; skip


async def ensure_webhook():
    """Ensure Telegram points to this deployment.

    Telegram does not expose the configured secret token in getWebhookInfo, so
    we refresh the webhook on startup even when the URL already matches. This
    keeps the header-secret in sync after env changes and repairs deploy races
    where an old container removed the webhook during shutdown.
    """
    current_url = ""
    try:
        info = await bot.get_webhook_info()
        current_url = getattr(info, "url", "") if info else ""
    except Exception as e:
        print("get_webhook_info error:", str(e)[:160])

    backoff = [0, 1, 2, 5]
    for i, delay in enumerate(backoff, start=1):
        if delay:
            await asyncio.sleep(delay)
        try:
            await bot.set_webhook(
                url=WEBHOOK_URL,
                secret_token=WEBHOOK_SECRET or None,
                drop_pending_updates=False,
            )
            if current_url == WEBHOOK_URL:
                print("Webhook refreshed OK")
            else:
                print(f"Webhook set OK: {current_url!r} → {WEBHOOK_URL!r}")
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
    missing_vars = [v for v in ["BOT_TOKEN", "REPLICATE_API_TOKEN"] if not os.getenv(v)]
    if missing_vars:
        raise SystemExit(f"❌ Missing required env vars: {missing_vars}")
    # DB init with retry (transient network failures on Railway cold-start)
    for _db_attempt in range(3):
        try:
            db_init()
            if DB_READY:
                break
        except Exception as _db_err:
            print(f"DB init attempt {_db_attempt+1}/3 failed: {str(_db_err)[:120]}")
        if _db_attempt < 2:
            await asyncio.sleep(2)
    # Load persisted stats/users
    try:
        stats_load()
        _credits_load()
        load_recent_jobs_from_db()
        print("Loaded persisted stats.")
    except Exception as e:
        print("Stats load error:", str(e)[:160])
    print("ADMINS (IDs):", ADMIN_IDS)
    print("ADMINS (usernames):", ADMIN_USERNAMES)
    if GALLERY_CHANNEL_ID:
        print("Gallery channel:", GALLERY_CHANNEL_ID, "AUTO_POST:", AUTO_POST)
    if PUBLISH_GROUP_ID:
        print("Publish group:", PUBLISH_GROUP_ID)
    print("Model → InstantID:", INSTANTID_MODEL, "| PhotoMaker:", PHOTOMAKER_MODEL, "| Legacy:", NANOBANANA_MODEL or "<disabled>")

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
            BotCommand(command="app",     description="Mini App"),
            BotCommand(command="help",    description="Помощь"),
            BotCommand(command="clear",   description="Очистить память"),
            BotCommand(command="version", description="Версия"),
        ],
        scope=BotCommandScopeDefault()
    )
    # Background nudges
    def _bg_task_error_handler(task: asyncio.Task):
        if not task.cancelled():
            exc = task.exception()
            if exc:
                log_event("background_task_error", task=task.get_name(), error=str(exc)[:240])

    try:
        t = asyncio.create_task(memory_cleanup_loop(), name="memory_cleanup")
        t.add_done_callback(_bg_task_error_handler)
        if NUDGE_ENABLED:
            t = asyncio.create_task(nudge_loop(), name="nudge_loop")
            t.add_done_callback(_bg_task_error_handler)
            print("Nudge loop started")
        if GROUP_POSTS_ENABLED:
            t = asyncio.create_task(group_posts_loop(), name="group_posts_loop")
            t.add_done_callback(_bg_task_error_handler)
            global GROUP_POST_LOOP_RUNNING
            GROUP_POST_LOOP_RUNNING = True
            print("Group posts loop started")
    except Exception as e:
        print("Nudge loop error on startup:", str(e)[:160])
@app.on_event("shutdown")
async def on_shutdown():
    print("🛑 Shutting down...")
    await bot.session.close()
    print("✅ Shutdown complete")


def _telegram_webhook_authorized(request: Request) -> bool:
    if not WEBHOOK_SECRET:
        return True  # секрет не настроен — принимаем все запросы
    header_secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if hmac.compare_digest(header_secret, WEBHOOK_SECRET):
        return True
    if WEBHOOK_ALLOW_QUERY_SECRET:
        query_secret = request.query_params.get("secret", "")
        return bool(hmac.compare_digest(query_secret, WEBHOOK_SECRET))
    return False

def validate_webapp_init_data(init_data: str) -> Optional[Dict[str, Any]]:
    if not BOT_TOKEN or not init_data:
        return None
    pairs = dict(parse_qsl(init_data, keep_blank_values=True))
    supplied_hash = pairs.pop("hash", "")
    if not supplied_hash:
        return None
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode("utf-8"), hashlib.sha256).digest()
    expected = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, supplied_hash):
        return None
    try:
        auth_date = int(pairs.get("auth_date", "0") or "0")
        if auth_date and time.time() - auth_date > 7 * 86400:
            return None
    except Exception:
        return None
    try:
        user = json.loads(pairs.get("user") or "{}")
    except Exception:
        user = {}
    uid = int(user.get("id") or 0)
    if not uid:
        return None
    return {"uid": uid, "username": user.get("username") or "", "user": user}

def _webapp_secret() -> bytes:
    return (WEBHOOK_SECRET or BOT_TOKEN or "imodel").encode("utf-8")

def make_webapp_token(uid: int, username: str = "") -> str:
    payload = {"uid": int(uid), "username": username[:64], "iat": int(time.time())}
    raw = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    sig = hmac.new(_webapp_secret(), raw.encode("utf-8"), hashlib.sha256).hexdigest()
    token = base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")
    return f"{token}.{sig}"

def parse_webapp_token(token: str) -> Optional[Dict[str, Any]]:
    try:
        body, sig = token.split(".", 1)
        raw = base64.urlsafe_b64decode(body + "=" * (-len(body) % 4)).decode("utf-8")
        expected = hmac.new(_webapp_secret(), raw.encode("utf-8"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, sig):
            return None
        payload = json.loads(raw)
        if time.time() - int(payload.get("iat", 0)) > 7 * 86400:
            return None
        return payload
    except Exception:
        return None

def webapp_user_from_request(request: Request) -> Optional[Dict[str, Any]]:
    auth = request.headers.get("Authorization", "")
    if auth.lower().startswith("bearer "):
        payload = parse_webapp_token(auth.split(" ", 1)[1].strip())
        if payload:
            return payload
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    validated = validate_webapp_init_data(init_data)
    if validated:
        return {"uid": validated["uid"], "username": validated.get("username", "")}
    return None

def public_job_snapshot(job: Dict[str, Any]) -> Dict[str, Any]:
    hidden = {"image_bytes", "style_bytes"}
    return {k: v for k, v in job.items() if k not in hidden and not isinstance(v, (bytes, bytearray))}

async def run_webapp_generation_job(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        return
    uid = int(job.get("chat_id") or 0)
    record_job(job_id, status="running")
    try:
        final_bytes = await asyncio.to_thread(
            generate_image_from_bytes,
            job["image_bytes"],
            str(job.get("prompt") or ""),
            lang=str(job.get("lang") or LANG_DEFAULT),
            strict=False,
            style_bytes=None,
            lock_scene=True,
            user_id=uid,
            job_id=job_id,
        )
    except Exception as e:
        final_bytes = None
        record_job(job_id, status="failed", error=str(e)[:500])
    if not final_bytes:
        stats_incr("jobs_failed", 1)
        record_job(job_id, status="failed", error=JOBS.get(job_id, {}).get("error") or "generation_failed")
        return
    output_url = s3_put_and_presign(final_bytes, key_prefix=f"outputs/webapp/{job_id}_")
    if uid and not is_free_user(uid, str(job.get("username") or "")):
        ensure_user_credit(uid)
        USER_CREDITS[uid] = max(0, int(USER_CREDITS.get(uid, FREE_QUOTA)) - 1)
        _credits_save()
    stats_incr("jobs_done", 1)
    record_job(job_id, status="ready", output_url=output_url, output_bytes=len(final_bytes))


async def _process_telegram_update(data: Dict[str, Any], received_at: float):
    try:
        update = Update.model_validate(data)
        await dp.feed_update(bot, update)
        log_event(
            "telegram_update_done",
            update_id=data.get("update_id"),
            latency_ms=int((time.time() - received_at) * 1000),
        )
    except Exception as e:
        log_event("telegram_update_error", update_id=data.get("update_id"), error=str(e)[:240])

@app.post("/")
async def telegram_webhook(request: Request, background_tasks: BackgroundTasks):
    if not _telegram_webhook_authorized(request):
        return JSONResponse({"status": "forbidden"}, status_code=403)
    data = await request.json()
    received_at = time.time()
    try:
        stats_incr("updates", 1)
        t = data.get("message", {}) or data.get("edited_message", {}) or data.get("callback_query", {})
        chat = (t.get("chat") or t.get("message", {}).get("chat") or {})
        log_event(
            "telegram_update_received",
            update_id=data.get("update_id"),
            chat_id=chat.get("id"),
            user_id=(t.get("from") or {}).get("id"),
            update_type=t.get("text", "<media>") if isinstance(t, dict) else "<unknown>",
        )
        user_obj = (t.get("from") or {})
        uid = user_obj.get("id")
        uname = user_obj.get("username")
        if isinstance(uid, int):
            STATS_USERS.add(uid)
            _touch_user(uid, uname)
    except Exception:
        pass
    background_tasks.add_task(_process_telegram_update, data, received_at)
    return {"ok": True}

@app.get("/")
async def root_health():
    return {"ok": True, "version": APP_VERSION}

@app.get("/healthz")
async def healthz():
    return {"status": "ok"}

@app.get("/webapp")
async def webapp_index():
    html = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
  <title>iModel Studio</title>
  <script src="https://telegram.org/js/telegram-web-app.js"></script>
  <style>
    :root { color-scheme: dark; --bg:#080b12; --panel:#111722; --soft:#1b2433; --text:#f4f7fb; --muted:#93a4b8; --accent:#79ffe1; --hot:#ff6fb1; }
    * { box-sizing:border-box; }
    body { margin:0; min-height:100vh; font:15px/1.45 -apple-system,BlinkMacSystemFont,Inter,Segoe UI,sans-serif; background:radial-gradient(circle at 20% 0%, #263b5f 0, transparent 34%), linear-gradient(155deg,#070910,#141927 55%,#0a0d14); color:var(--text); }
    .app { width:min(980px,100%); margin:0 auto; padding:18px 16px 32px; }
    .hero { padding:26px 0 18px; }
    .brand { display:flex; align-items:center; justify-content:space-between; gap:12px; margin-bottom:18px; }
    .logo { font-weight:800; letter-spacing:.02em; font-size:20px; }
    .pill { border:1px solid rgba(255,255,255,.14); background:rgba(255,255,255,.06); border-radius:999px; padding:7px 10px; color:var(--muted); font-size:12px; }
    h1 { font-size:36px; line-height:1.02; margin:0 0 10px; letter-spacing:0; }
    p { color:var(--muted); margin:0; }
    .grid { display:grid; gap:12px; grid-template-columns:1fr; }
    .panel { background:linear-gradient(180deg,rgba(255,255,255,.08),rgba(255,255,255,.04)); border:1px solid rgba(255,255,255,.12); border-radius:14px; padding:14px; box-shadow:0 18px 50px rgba(0,0,0,.24); }
    label { display:block; color:#c7d3e2; font-size:13px; margin:0 0 8px; }
    textarea, input[type=file] { width:100%; border:1px solid rgba(255,255,255,.14); background:#0e1420; color:var(--text); border-radius:10px; padding:12px; outline:none; }
    textarea { min-height:92px; resize:vertical; }
    .actions { display:flex; gap:10px; flex-wrap:wrap; margin-top:12px; }
    button { border:0; border-radius:10px; padding:12px 14px; font-weight:700; color:#071016; background:linear-gradient(135deg,var(--accent),#8ea7ff); cursor:pointer; }
    button.secondary { color:var(--text); background:rgba(255,255,255,.09); border:1px solid rgba(255,255,255,.14); }
    .status { margin-top:12px; color:#d5e1f0; white-space:pre-wrap; }
    .cards { display:grid; grid-template-columns:repeat(3,1fr); gap:10px; margin-top:14px; }
    .card { background:rgba(255,255,255,.06); border:1px solid rgba(255,255,255,.1); border-radius:12px; padding:12px; min-height:92px; }
    .card b { display:block; margin-bottom:6px; }
    @media (max-width:700px){ h1{font-size:31px}.cards{grid-template-columns:1fr}.app{padding-inline:14px} }
  </style>
</head>
<body>
  <main class="app">
    <section class="hero">
      <div class="brand"><div class="logo">iModel Studio</div><div class="pill" id="balance">credits: --</div></div>
      <h1>AI photo studio inside Telegram</h1>
      <p>Create polished portraits, copy a scene, track jobs, and keep your face identity consistent.</p>
    </section>
    <section class="grid">
      <div class="panel">
        <label>Selfie</label>
        <input id="photo" type="file" accept="image/*" />
        <label style="margin-top:12px">Scene</label>
        <textarea id="prompt" placeholder="Wedding guest, cinematic candid photo, many people around, warm lights"></textarea>
        <div class="actions">
          <button id="generate">Generate</button>
          <button class="secondary" id="refresh">Refresh balance</button>
        </div>
        <div class="status" id="status">Ready.</div>
      </div>
      <div class="cards">
        <div class="card"><b>Face Lock v2</b><span>Official multi-image Nano Banana flow with identity-first prompting.</span></div>
        <div class="card"><b>Jobs</b><span>Async status polling for Mini App generations.</span></div>
        <div class="card"><b>Gallery</b><span>Recent ready jobs appear as the backend stores outputs.</span></div>
      </div>
    </section>
  </main>
  <script>
    const tg = window.Telegram?.WebApp;
    tg?.ready(); tg?.expand();
    let token = "";
    const $ = id => document.getElementById(id);
    async function api(path, opts={}) {
      const headers = Object.assign({"Content-Type":"application/json"}, opts.headers || {});
      if (token) headers.Authorization = "Bearer " + token;
      return fetch(path, Object.assign({}, opts, {headers}));
    }
    async function session() {
      const r = await fetch("/api/v1/webapp/session", {method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({initData: tg?.initData || ""})});
      if (!r.ok) { $("status").textContent = "Open this inside Telegram to authenticate."; return; }
      const data = await r.json(); token = data.token; await me();
    }
    async function me() {
      const r = await api("/api/v1/me");
      if (!r.ok) return;
      const data = await r.json(); $("balance").textContent = "credits: " + data.credits + " · " + data.role;
    }
    function fileToB64(file) {
      return new Promise((resolve,reject)=>{ const fr=new FileReader(); fr.onload=()=>resolve(fr.result); fr.onerror=reject; fr.readAsDataURL(file); });
    }
    async function poll(id) {
      for (let i=0;i<80;i++) {
        const r = await api("/api/v1/generations/" + id);
        const data = await r.json();
        $("status").textContent = "Job " + data.status + (data.output_url ? "\\n" + data.output_url : "");
        if (["ready","failed"].includes(data.status)) { await me(); return; }
        await new Promise(r=>setTimeout(r,2500));
      }
    }
    $("refresh").onclick = me;
    $("generate").onclick = async () => {
      const file = $("photo").files[0]; const prompt = $("prompt").value.trim();
      if (!file || !prompt) { $("status").textContent = "Choose selfie and scene."; return; }
      $("status").textContent = "Uploading...";
      const image_b64 = await fileToB64(file);
      const r = await api("/api/v1/generations", {method:"POST", body:JSON.stringify({prompt, image_b64})});
      const data = await r.json();
      if (!r.ok) { $("status").textContent = data.error || "Failed"; return; }
      $("status").textContent = "Queued: " + data.job_id; poll(data.job_id);
    };
    session();
  </script>
</body>
</html>
    """
    return HTMLResponse(content=html)

@app.post("/api/v1/webapp/session")
async def api_webapp_session(request: Request):
    data = await request.json()
    validated = validate_webapp_init_data(str(data.get("initData") or ""))
    if not validated:
        return JSONResponse({"error": "invalid_init_data"}, status_code=403)
    uid = int(validated["uid"])
    username = str(validated.get("username") or "")
    _touch_user(uid, username)
    ensure_user_credit(uid)
    return {
        "token": make_webapp_token(uid, username),
        "user": validated.get("user") or {},
        "credits": USER_CREDITS.get(uid, FREE_QUOTA),
        "role": role_for_user(uid, username),
        "grants": sorted(grants_for_user(uid, username)),
    }

@app.get("/api/v1/me")
async def api_me(request: Request):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    uid = int(user["uid"])
    username = str(user.get("username") or "")
    ensure_user_credit(uid)
    return {
        "chat_id": uid,
        "username": username,
        "credits": USER_CREDITS.get(uid, FREE_QUOTA),
        "role": role_for_user(uid, username),
        "grants": sorted(grants_for_user(uid, username)),
    }

@app.get("/api/v1/gallery")
async def api_gallery(request: Request):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    uid = int(user["uid"])
    source_jobs = list(JOBS.values())
    if DB_READY:
        db_jobs = _db_load_recent_jobs(100)
        if db_jobs:
            source_jobs = db_jobs
    items = [
        public_job_snapshot(j)
        for j in source_jobs
        if int(j.get("chat_id") or 0) == uid and j.get("status") == "ready"
    ][-20:]
    return {"items": items}

@app.post("/api/v1/generations")
async def api_create_generation(request: Request):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    uid = int(user["uid"])
    username = str(user.get("username") or "")
    ensure_user_credit(uid)
    if not has_credit(uid, username):
        return JSONResponse({"error": "no_credits"}, status_code=402)
    data = await request.json()
    prompt = str(data.get("prompt") or "").strip()
    image_b64 = str(data.get("image_b64") or "").strip()
    if not prompt or not image_b64:
        return JSONResponse({"error": "prompt and image_b64 are required"}, status_code=400)
    try:
        if image_b64.startswith("data:") and "," in image_b64:
            image_b64 = image_b64.split(",", 1)[1]
        image_bytes = base64.b64decode(image_b64)
    except Exception:
        return JSONResponse({"error": "invalid image"}, status_code=400)
    ok, reason = assess_selfie_quality(image_bytes)
    if not ok:
        return JSONResponse({"error": "selfie_quality", "reason": reason}, status_code=400)
    job = record_job(
        kind="webapp_generation",
        status="queued",
        chat_id=uid,
        username=username,
        prompt=prompt,
        model=INSTANTID_MODEL,
        image_bytes=image_bytes,
        lang=str(data.get("lang") or LANG_DEFAULT),
    )
    stats_incr("jobs_created", 1)
    asyncio.create_task(run_webapp_generation_job(str(job["job_id"])))
    return {"job_id": job["job_id"], "status": "queued"}

@app.get("/api/v1/generations/{job_id}")
async def api_get_generation(job_id: str, request: Request):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    uid = int(user["uid"])
    job = JOBS.get(job_id) or (_db_load_job(job_id) if DB_READY else None)
    if not job:
        return JSONResponse({"error": "not_found"}, status_code=404)
    if int(job.get("chat_id") or 0) != uid and not has_grant(uid, str(user.get("username") or ""), "jobs.view"):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return public_job_snapshot(job)

@app.get("/metrics")
async def http_metrics(request: Request):
    if not METRICS_SECRET or request.query_params.get("secret") != METRICS_SECRET:
        return JSONResponse({"status": "forbidden"}, status_code=403)
    resp = dict(STATS)
    # Persisted users count (survives restarts)
    resp["users"] = len(STATS_USERS_INFO)
    resp["uptime_sec"] = int(time.time() - STATS["start_ts"]) if STATS.get("start_ts") else 0
    metric_jobs = _db_load_recent_jobs(200) if DB_READY else list(JOBS.values())
    resp["jobs_in_memory"] = len(JOBS)
    resp["jobs_window"] = len(metric_jobs)
    resp["jobs_queued"] = sum(1 for j in metric_jobs if j.get("status") == "queued")
    resp["jobs_running"] = sum(1 for j in metric_jobs if j.get("status") == "running")
    resp["jobs_failed_window"] = sum(1 for j in metric_jobs if j.get("status") in {"failed", "delivery_failed"})
    gen_count = int(STATS.get("generation_latency_count", 0) or 0)
    resp["generation_latency_avg_ms"] = int(STATS.get("generation_latency_total_ms", 0) / gen_count) if gen_count else 0
    resp["db_ready"] = DB_READY
    return resp

@app.get("/admin")
async def admin_panel(request: Request):
    if not ADMIN_PANEL_SECRET or request.query_params.get("secret") != ADMIN_PANEL_SECRET:
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
    recent_jobs = _db_load_recent_jobs(15) if DB_READY else []
    if not recent_jobs:
        recent_jobs = sorted(JOBS.values(), key=lambda j: float(j.get("updated_at", 0)), reverse=True)[:15]
    failed_jobs = [j for j in recent_jobs if str(j.get("status")) in {"failed", "delivery_failed"}]
    running_jobs = [j for j in recent_jobs if str(j.get("status")) in {"queued", "running"}]
    h = lambda value: html_lib.escape(str(value or ""))

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

      <div class="grid kpi" style="grid-template-columns: repeat(4,1fr); margin-top:14px;">
        <div class="card"><div class="muted">Jobs in memory</div><div class="v">{len(JOBS)}</div><div class="muted">DB: {'on' if DB_READY else 'off'}</div></div>
        <div class="card"><div class="muted">Queued/running</div><div class="v">{len(running_jobs)}</div><div class="muted">recent window</div></div>
        <div class="card"><div class="muted">Failed</div><div class="v fail">{len(failed_jobs)}</div><div class="muted">recent window</div></div>
        <div class="card"><div class="muted">Delivery failures</div><div class="v fail">{STATS.get('delivery_failed',0)}</div><div class="muted">photo ok {STATS.get('delivery_photo_ok',0)}</div></div>
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
          <div class="muted">Recent jobs</div>
          <table>
            <tr><th>Status</th><th>Job</th><th>User</th><th>Prompt</th><th>Error</th><th>Updated</th></tr>
            {''.join(
              f'<tr>'
              f'<td><span class="pill">{h(j.get("status"))}</span></td>'
              f'<td>{h(str(j.get("job_id",""))[:10])}</td>'
              f'<td>{h(uname_or_id(int(j.get("chat_id") or 0), j.get("username") or None))}</td>'
              f'<td>{h(str(j.get("prompt") or "")[:90])}</td>'
              f'<td>{h(str(j.get("error") or "")[:80])}</td>'
              f'<td>{time_ago(float(j.get("updated_at") or 0))}</td>'
              f'</tr>' for j in recent_jobs)
            }
          </table>
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

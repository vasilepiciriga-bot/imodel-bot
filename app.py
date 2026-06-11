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

APP_VERSION = "iModel 2.8.0"

from photoshoot_modes import (
    PHOTOSHOOT_MODES,
    get_mode_config,
    get_mode_credit_cost,
    get_mode_label,
    apply_prompt_layer,
    _score_candidate,
    step_label_text,
)
from experiments import get_variant, all_variants, nudge_interval_hours, EXPERIMENTS

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

_DB_POOL = None

def _init_db_pool():
    global _DB_POOL
    if not DATABASE_URL or psycopg is None:
        return
    try:
        from psycopg_pool import ConnectionPool
        _DB_POOL = ConnectionPool(DATABASE_URL, min_size=2, max_size=10, open=True)
        print("[db] connection pool initialized (2-10 connections)")
    except ImportError:
        print("[db] psycopg_pool not available, using single connections")
    except Exception as e:
        print("[db] pool init error:", str(e)[:120])

def _db_connect():
    if not DATABASE_URL or psycopg is None:
        return None
    if _DB_POOL:
        return _DB_POOL.connection()
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
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS imodel_events (
                        id BIGSERIAL PRIMARY KEY,
                        uid BIGINT,
                        event TEXT NOT NULL,
                        props_json TEXT NOT NULL DEFAULT '{}',
                        day TEXT NOT NULL,
                        ts DOUBLE PRECISION NOT NULL
                    )
                """)
                cur.execute("CREATE INDEX IF NOT EXISTS idx_imodel_events_uid   ON imodel_events(uid)")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_imodel_events_event ON imodel_events(event, day)")
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS imodel_community_presets (
                        key TEXT PRIMARY KEY,
                        creator_uid BIGINT NOT NULL,
                        creator_name TEXT,
                        label TEXT NOT NULL,
                        prompt TEXT NOT NULL,
                        output_s3_key TEXT,
                        votes INTEGER NOT NULL DEFAULT 0,
                        created_at DOUBLE PRECISION NOT NULL
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS imodel_community_votes (
                        uid BIGINT NOT NULL,
                        preset_key TEXT NOT NULL,
                        PRIMARY KEY (uid, preset_key)
                    )
                """)
                cur.execute("CREATE INDEX IF NOT EXISTS idx_community_votes ON imodel_community_presets(votes DESC)")
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS imodel_quests (
                        uid BIGINT NOT NULL,
                        quest_id TEXT NOT NULL,
                        progress INT NOT NULL DEFAULT 0,
                        claimed_date TEXT NOT NULL DEFAULT '',
                        progress_json TEXT NOT NULL DEFAULT '{}',
                        PRIMARY KEY (uid, quest_id)
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS imodel_processed_payments (
                        charge_id TEXT PRIMARY KEY,
                        uid BIGINT NOT NULL,
                        payload TEXT NOT NULL,
                        created_at DOUBLE PRECISION NOT NULL
                    )
                """)
                # Gallery query index — prevents full table scans on every gallery load.
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_jobs_user_gallery "
                    "ON imodel_jobs(chat_id, status, updated_at DESC)"
                )
                cur.execute(
                    "CREATE INDEX IF NOT EXISTS idx_jobs_status_updated "
                    "ON imodel_jobs(status, updated_at DESC)"
                )
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
        # GREATEST prevents a fresh-restart from overwriting historical DB values with zeros.
        # Stats only grow; if in-memory < DB it means load failed — keep the DB value.
        _db_execute(
            "INSERT INTO imodel_stats_totals(key, value) VALUES (%s, %s) "
            "ON CONFLICT (key) DO UPDATE SET value = GREATEST(EXCLUDED.value, imodel_stats_totals.value)",
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


def _db_save_quest(uid: int, quest_id: str, progress: int, claimed_date: str, progress_json: str = "{}"):
    _db_execute(
        "INSERT INTO imodel_quests(uid, quest_id, progress, claimed_date, progress_json) "
        "VALUES (%s, %s, %s, %s, %s) "
        "ON CONFLICT (uid, quest_id) DO UPDATE SET "
        "progress=EXCLUDED.progress, claimed_date=EXCLUDED.claimed_date, progress_json=EXCLUDED.progress_json",
        (uid, quest_id, progress, claimed_date, progress_json),
    )


def _db_load_quests():
    """Load quest state into USER_QUEST_PROGRESS and USER_QUEST_CLAIMED."""
    for uid, quest_id, progress, claimed_date, progress_json_raw in _db_fetchall(
        "SELECT uid, quest_id, progress, claimed_date, progress_json FROM imodel_quests"
    ):
        uid = int(uid)
        try:
            pj = json.loads(progress_json_raw or "{}")
        except Exception:
            pj = {}
        if pj:
            USER_QUEST_PROGRESS.setdefault(uid, {}).update(pj)
        elif progress:
            USER_QUEST_PROGRESS.setdefault(uid, {})[str(quest_id)] = int(progress)
        if claimed_date:
            USER_QUEST_CLAIMED.setdefault(uid, {})[str(quest_id)] = str(claimed_date)


def _db_is_payment_processed(charge_id: str) -> bool:
    if charge_id in _PROCESSED_PAYMENTS:
        return True
    rows = _db_fetchall(
        "SELECT charge_id FROM imodel_processed_payments WHERE charge_id=%s", (charge_id,)
    )
    if rows:
        _PROCESSED_PAYMENTS.add(charge_id)
        return True
    return False


def _db_mark_payment_processed(charge_id: str, uid: int, payload: str):
    _PROCESSED_PAYMENTS.add(charge_id)
    _db_execute(
        "INSERT INTO imodel_processed_payments(charge_id, uid, payload, created_at) "
        "VALUES (%s, %s, %s, %s) ON CONFLICT DO NOTHING",
        (charge_id, uid, payload, time.time()),
    )


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

def _db_load_user_jobs(uid: int, limit: int = 20) -> List[Dict[str, Any]]:
    rows = _db_fetchall(
        "SELECT job_id, kind, status, chat_id, username, prompt, model, timeline_json, result_json, error, created_at, updated_at "
        "FROM imodel_jobs WHERE chat_id = %s AND status = 'ready' ORDER BY updated_at DESC LIMIT %s",
        (uid, int(limit)),
    )
    return [_db_job_to_dict(row) for row in rows]

# ===== Persistent stats storage =====
DATA_DIR = os.getenv("DATA_DIR", "data")
STATS_TOTALS_FILE = os.path.join(DATA_DIR, "stats_totals.json")
STATS_DAILY_FILE  = os.path.join(DATA_DIR, "stats_daily.json")
USERS_FILE        = os.path.join(DATA_DIR, "users.json")

STATS_DAILY: Dict[str, Dict[str, int]] = {}
_STATS_DIRTY = False

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
    # --- totals ---
    try:
        loaded = None
        db_loaded = _db_load_stats_totals()
        if db_loaded:
            loaded = db_loaded
            print(f"[stats] loaded totals from DB ({len(db_loaded)} keys, gens_ok={db_loaded.get('gens_ok',0)})")
        else:
            print("[stats] DB totals empty — trying S3 fallback")
            txt = _s3_get_text(STATE_PREFIX + "stats_totals.json")
            if txt:
                loaded = json.loads(txt)
                print(f"[stats] loaded totals from S3 ({len(loaded)} keys)")
        if loaded is None and os.path.exists(STATS_TOTALS_FILE):
            with open(STATS_TOTALS_FILE, "r", encoding="utf-8") as f:
                loaded = json.load(f)
            print(f"[stats] loaded totals from file ({len(loaded)} keys)")
        if loaded:
            for k, v in loaded.items():
                try:
                    if isinstance(v, (int, float)):
                        STATS[k] = v
                except Exception:
                    pass
            # Only sync back to DB if we loaded from a non-DB source (S3/file)
            if not db_loaded:
                _db_save_stats_totals()
        else:
            print("[stats] WARNING: no totals found anywhere — starting from zero")
    except Exception as e:
        print("[stats] load totals error:", str(e)[:160])
    # --- daily ---
    try:
        db_daily = _db_load_stats_daily()
        if db_daily:
            STATS_DAILY = db_daily
            print(f"[stats] loaded daily from DB ({len(db_daily)} days)")
        else:
            txt = _s3_get_text(STATE_PREFIX + "stats_daily.json")
            if txt:
                STATS_DAILY = json.loads(txt) or {}
                print(f"[stats] loaded daily from S3 ({len(STATS_DAILY)} days)")
            elif os.path.exists(STATS_DAILY_FILE):
                with open(STATS_DAILY_FILE, "r", encoding="utf-8") as f:
                    STATS_DAILY = json.load(f) or {}
                print(f"[stats] loaded daily from file ({len(STATS_DAILY)} days)")
            else:
                STATS_DAILY = {}
                print("[stats] WARNING: no daily stats found anywhere")
        if DB_READY and STATS_DAILY and not db_daily:
            _db_save_stats_daily()
    except Exception as e:
        print("[stats] load daily error:", str(e)[:160])
        STATS_DAILY = {}
    # --- users ---
    try:
        data = None
        db_users = _db_load_users()
        if db_users:
            data = db_users
            print(f"[stats] loaded {len(db_users)} users from DB")
        else:
            print("[stats] DB users empty — trying S3 fallback")
            txt = _s3_get_text(STATE_PREFIX + "users.json")
            if txt:
                data = json.loads(txt) or {}
                print(f"[stats] loaded {len(data)} users from S3")
        if data is None and os.path.exists(USERS_FILE):
            with open(USERS_FILE, "r", encoding="utf-8") as f:
                data = json.load(f) or {}
            print(f"[stats] loaded {len(data)} users from file")
        if data:
            for uid_str, info in data.items():
                try:
                    STATS_USERS_INFO[int(uid_str)] = info
                except Exception:
                    continue
            if not db_users:
                users_save()
        else:
            print("[stats] WARNING: no user data found anywhere")
    except Exception as e:
        print("[users] load error:", str(e)[:160])
    # --- quests ---
    try:
        if DB_READY:
            _db_load_quests()
            print("[stats] quest state loaded from DB")
    except Exception as e:
        print("[quests] load error:", str(e)[:160])
    # --- processed payments (warm in-memory set) ---
    try:
        if DB_READY:
            for (cid,) in _db_fetchall("SELECT charge_id FROM imodel_processed_payments"):
                _PROCESSED_PAYMENTS.add(str(cid))
            print(f"[payments] loaded {len(_PROCESSED_PAYMENTS)} processed charge IDs")
    except Exception as e:
        print("[payments] load error:", str(e)[:160])

def stats_incr(key: str, n: int = 1):
    global _STATS_DIRTY
    try:
        STATS[key] = int(STATS.get(key, 0)) + n
        day = _date_key()
        d = STATS_DAILY.setdefault(day, {})
        d[key] = int(d.get(key, 0)) + n
        _STATS_DIRTY = True
    except Exception as e:
        print("[stats] incr error:", key, str(e)[:160])

async def _stats_flush_loop():
    global _STATS_DIRTY
    await asyncio.sleep(30)
    while True:
        try:
            if _STATS_DIRTY:
                _STATS_DIRTY = False
                stats_save_totals()
                stats_save_daily()
        except Exception as e:
            print("[stats] flush error:", str(e)[:120])
        await asyncio.sleep(30)

# ===================== ANALYTICS EVENTS ========================
POSTHOG_API_KEY = os.getenv("POSTHOG_API_KEY", "")
POSTHOG_HOST    = os.getenv("POSTHOG_HOST", "https://app.posthog.com")
_POSTHOG_Q: asyncio.Queue = asyncio.Queue(maxsize=500)

async def _posthog_worker():
    while True:
        try:
            item = await asyncio.wait_for(_POSTHOG_Q.get(), timeout=60)
            uid, event, props, ts = item
            await asyncio.to_thread(_posthog_capture_sync, uid, event, props, ts)
            _POSTHOG_Q.task_done()
        except asyncio.TimeoutError:
            continue
        except Exception as e:
            print("[posthog] worker error:", str(e)[:120])

def analytics_event(uid: Optional[int], event: str, props: Optional[Dict[str, Any]] = None):
    """
    Record a structured funnel event. Non-blocking, never raises.
    Writes to imodel_events (Postgres) and forwards to PostHog if configured.
    Also increments stats_incr for lightweight aggregation.
    """
    try:
        now = time.time()
        day = _date_key()
        p = props or {}
        # Enrich with user context
        if uid:
            ui = STATS_USERS_INFO.get(uid) or {}
            p.setdefault("lang", USER_LANG.get(uid, LANG_DEFAULT))
            p.setdefault("credits", USER_CREDITS.get(uid, 0))
            p.setdefault("gens_ok", int(ui.get("gens_ok", 0)))
            p.setdefault("paid", int(ui.get("payments", 0)) > 0)
        p_json = json.dumps(p, ensure_ascii=False)
        _db_execute(
            "INSERT INTO imodel_events(uid, event, props_json, day, ts) VALUES (%s,%s,%s,%s,%s)",
            (uid, event, p_json, day, now),
        )
        stats_incr(f"evt_{event}", 1)
        if POSTHOG_API_KEY and uid:
            try:
                _POSTHOG_Q.put_nowait((uid, event, p, now))
            except asyncio.QueueFull:
                pass
    except Exception as e:
        print(f"[analytics] event error {event}: {str(e)[:120]}")

def _posthog_capture_sync(uid: int, event: str, props: Dict[str, Any], ts: float):
    try:
        import urllib.request as _ur
        payload = json.dumps({
            "api_key": POSTHOG_API_KEY,
            "event": event,
            "distinct_id": str(uid),
            "properties": {**props, "$lib": "imodel-bot"},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)),
        }).encode()
        req = _ur.Request(
            f"{POSTHOG_HOST}/capture/",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        _ur.urlopen(req, timeout=5)
    except Exception:
        pass

def _analytics_funnel_counts(days: int = 7) -> Dict[str, Any]:
    """Aggregate funnel metrics from imodel_events for the last N days."""
    if not DB_READY:
        return {}
    try:
        cutoff_day = time.strftime("%Y-%m-%d", time.gmtime(time.time() - days * 86400))
        rows = _db_fetchall(
            "SELECT event, COUNT(*), COUNT(DISTINCT uid) FROM imodel_events "
            "WHERE day >= %s GROUP BY event",
            (cutoff_day,),
        )
        totals: Dict[str, int] = {}
        uniq: Dict[str, int] = {}
        for event, cnt, ucnt in rows:
            totals[event] = int(cnt)
            uniq[event] = int(ucnt)

        def rate(num: str, den: str) -> Optional[float]:
            d = totals.get(den, 0)
            return round(totals.get(num, 0) / d, 3) if d else None

        return {
            "period_days": days,
            "generation_started":    totals.get("generation_started", 0),
            "generation_completed":  totals.get("generation_completed", 0),
            "paywall_hit":           totals.get("paywall_hit", 0),
            "purchase_completed":    totals.get("purchase_completed", 0),
            "share_tapped":          totals.get("share_tapped", 0),
            "nudge_converted":       totals.get("nudge_converted", 0),
            "referral_joined":       totals.get("referral_joined", 0),
            "mode_selected":         totals.get("mode_selected", 0),
            # Rates
            "completion_rate":       rate("generation_completed", "generation_started"),
            "paywall_rate":          rate("paywall_hit", "generation_started"),
            "purchase_rate":         rate("purchase_completed", "paywall_hit"),
            "share_rate":            rate("share_tapped", "generation_completed"),
            "nudge_conversion_rate": rate("nudge_converted", "nudges_sent"),
            # Unique users
            "unique_generators":     uniq.get("generation_started", 0),
            "unique_buyers":         uniq.get("purchase_completed", 0),
        }
    except Exception as e:
        print(f"[analytics] funnel error: {str(e)[:120]}")
        return {}

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

# Subscription tiers
SUB_PRO_STARS   = int(os.getenv("SUB_PRO_STARS",   "490"))
SUB_ELITE_STARS = int(os.getenv("SUB_ELITE_STARS", "990"))
SUB_PRO_CREDITS   = int(os.getenv("SUB_PRO_CREDITS",   "75"))
SUB_ELITE_CREDITS = int(os.getenv("SUB_ELITE_CREDITS", "270"))
SUB_PERIOD = 2592000  # 30 days in seconds

# Weekly subscription tier (low barrier)
SUB_WEEKLY_STARS   = int(os.getenv("SUB_WEEKLY_STARS",   "149"))
SUB_WEEKLY_CREDITS = int(os.getenv("SUB_WEEKLY_CREDITS", "20"))
SUB_WEEKLY_PERIOD  = 604800  # 7 days

# Creator subscription tier (~€15/month)
SUB_CREATOR_STARS   = int(os.getenv("SUB_CREATOR_STARS",   "1150"))
SUB_CREATOR_CREDITS = int(os.getenv("SUB_CREATOR_CREDITS", "400"))

# Style pack pricing
STYLE_PACK_STARS    = int(os.getenv("STYLE_PACK_STARS",    "490"))
AGE_PACK_STARS      = int(os.getenv("AGE_PACK_STARS",      "290"))
SHOP_BANNER         = os.getenv("SHOP_BANNER", "")  # e.g. "🔥 Weekend Sale — 50% more credits today only!"
VIRAL_PACK_STARS    = int(os.getenv("VIRAL_PACK_STARS",    "190"))
LOCATIONS_PACK_STARS= int(os.getenv("LOCATIONS_PACK_STARS","290"))
FANTASY_PACK_STARS  = int(os.getenv("FANTASY_PACK_STARS",  "390"))

# Canonical payload → stars map used by pre_checkout validation and payment idempotency.
# Must be kept in sync with ITEMS in api_shop_invoice and send_stars_invoice.
def _build_payment_sku_map() -> Dict[str, int]:
    return {
        "pack_10":        199,
        "pack_30":        490,
        "pack_100":       1290,
        "pack_300":       2990,
        "sub_weekly":     SUB_WEEKLY_STARS,
        "sub_pro":        SUB_PRO_STARS,
        "sub_creator":    SUB_CREATOR_STARS,
        "sub_elite":      SUB_ELITE_STARS,
        "premium_pack_1": STYLE_PACK_STARS,
        "age_pack":       AGE_PACK_STARS,
        "viral_pack":     VIRAL_PACK_STARS,
        "locations_pack": LOCATIONS_PACK_STARS,
        "fantasy_pack":   FANTASY_PACK_STARS,
    }

# In-memory set of already-processed telegram_payment_charge_ids (survive restarts via DB load).
_PROCESSED_PAYMENTS: set = set()

# Challenge bonus
CHALLENGE_BONUS_CREDITS = int(os.getenv("CHALLENGE_BONUS_CREDITS", "2"))

# Trending presets (comma-sep keys, updated via env var weekly)
TRENDING_PRESETS_ENV = os.getenv("TRENDING_PRESETS", "cinematic,neon_night,golden_hour,beauty_dish,vintage70")

# Daily bonus / streak
DAILY_BONUS_BASE = int(os.getenv("DAILY_BONUS_BASE", "1"))
STREAK_MILESTONE_BONUSES: Dict[int, int] = {3: 3, 7: 7, 14: 14, 30: 25}  # streak day → extra credits
DAILY_STREAK_MILESTONES: Dict[int, int] = {3: 2, 7: 3, 14: 5, 30: 7}  # day → bonus gens

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

ADMIN_IDS: Set[int] = _parse_admins(os.getenv("ADMIN_IDS", "917120373"))
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

MAX_CONCURRENT_JOBS_PER_USER = 3

def _user_active_jobs_count(uid: int) -> int:
    """Count queued or running jobs for a user."""
    return sum(
        1 for j in JOBS.values()
        if int(j.get("chat_id") or 0) == uid and j.get("status") in ("queued", "running")
    )

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
    for key in (
        "output_url", "output_s3_key", "output_bytes",
        "delivery_message_id", "output_urls", "step_label",
        # gallery display metadata — must survive DB round-trip
        "photoshoot_mode", "mode", "preset_key", "age_key",
        "bonus_credits", "lang",
    ):
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
    if job.get("status") == "ready":
        _cache_write_job(public_job_snapshot(job))
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
    if DB_READY:
        for job in reversed(_db_load_recent_jobs(limit)):
            JOBS[str(job["job_id"])] = job
    else:
        for snap in _cache_load_jobs():
            jid = str(snap.get("job_id") or "")
            if jid:
                JOBS.setdefault(jid, snap)

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

# Serve pre-built React mini app from webapp/dist/
from fastapi.staticfiles import StaticFiles as _SF
_WEBAPP_DIST = os.path.join(os.path.dirname(os.path.abspath(__file__)), "webapp", "dist")

# Persistent data directory — lives outside dist/ so npm run build never wipes it
_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
_PRESET_THUMBS_DIR = os.path.join(_DATA_DIR, "preset-thumbs")
os.makedirs(_PRESET_THUMBS_DIR, exist_ok=True)
app.mount("/preset-thumbs", _SF(directory=_PRESET_THUMBS_DIR), name="preset_thumbs")

# Thumbnail S3 key registry — committed to git, survives deploys
_PRESET_THUMB_CONFIG = os.path.join(os.path.dirname(os.path.abspath(__file__)), "preset-thumbs.json")
PRESET_THUMB_KEYS: dict = {}
try:
    if os.path.exists(_PRESET_THUMB_CONFIG):
        with open(_PRESET_THUMB_CONFIG) as _f:
            PRESET_THUMB_KEYS = json.load(_f)
except Exception:
    pass

# Community presets — user-generated styles shared by the community
_COMMUNITY_FILE = os.path.join(_DATA_DIR, "community_presets.json")
COMMUNITY_PRESETS: list = []   # [{key, creator_uid, creator_name, label, prompt, output_s3_key, votes, created_at}]
COMMUNITY_VOTES: set = set()   # "{uid}_{key}" strings for no-DB mode

try:
    if os.path.exists(_COMMUNITY_FILE):
        with open(_COMMUNITY_FILE) as _cf:
            COMMUNITY_PRESETS = json.load(_cf)
except Exception:
    pass


def _save_community_file():
    try:
        os.makedirs(_DATA_DIR, exist_ok=True)
        with open(_COMMUNITY_FILE, "w") as _cf:
            json.dump(COMMUNITY_PRESETS, _cf, ensure_ascii=False)
    except Exception:
        pass


def _has_community_vote(uid: int, key: str) -> bool:
    if DB_READY:
        rows = _db_fetchall("SELECT 1 FROM imodel_community_votes WHERE uid=%s AND preset_key=%s LIMIT 1", (uid, key))
        return bool(rows)
    return f"{uid}_{key}" in COMMUNITY_VOTES


def _load_community_presets_for_api(uid: int, sort: str = "top", limit: int = 100) -> list:
    if DB_READY:
        order = "votes DESC, created_at DESC" if sort != "new" else "created_at DESC"
        rows = _db_fetchall(
            f"SELECT key, creator_uid, creator_name, label, prompt, output_s3_key, votes, created_at "
            f"FROM imodel_community_presets ORDER BY {order} LIMIT %s",
            (limit,),
        )
        return [
            {"key": r[0], "creator_uid": r[1], "creator_name": r[2], "label": r[3],
             "prompt": r[4], "output_s3_key": r[5], "votes": r[6], "created_at": r[7]}
            for r in rows
        ]
    # No-DB: use in-memory list
    key_fn = (lambda x: -x.get("votes", 0)) if sort != "new" else (lambda x: -x.get("created_at", 0))
    return sorted(COMMUNITY_PRESETS, key=key_fn)[:limit]


# Gallery JSON-lines cache — persists completed jobs when DB is unavailable
import json as _json
_GALLERY_CACHE_FILE = os.path.join(_DATA_DIR, "gallery_cache.jsonl")

def _cache_write_job(snap: dict) -> None:
    """Upsert one ready-job snapshot into the local JSONL cache (newest 500 entries)."""
    os.makedirs(_DATA_DIR, exist_ok=True)
    entries: list = []
    if os.path.exists(_GALLERY_CACHE_FILE):
        try:
            with open(_GALLERY_CACHE_FILE) as _f:
                for _line in _f:
                    try:
                        _e = _json.loads(_line)
                        if _e.get("job_id") != snap.get("job_id"):
                            entries.append(_e)
                    except Exception:
                        pass
        except Exception:
            pass
    entries.append(snap)
    entries = entries[-500:]
    try:
        with open(_GALLERY_CACHE_FILE, "w") as _f:
            for _e in entries:
                _f.write(_json.dumps(_e) + "\n")
    except Exception as _ce:
        print(f"gallery cache write error: {_ce}")

def _cache_load_jobs() -> list:
    """Load all cached job snapshots from the JSONL file."""
    if not os.path.exists(_GALLERY_CACHE_FILE):
        return []
    out: list = []
    try:
        with open(_GALLERY_CACHE_FILE) as _f:
            for _line in _f:
                try:
                    out.append(_json.loads(_line))
                except Exception:
                    pass
    except Exception:
        pass
    return out

def _cache_delete_job(job_id: str) -> None:
    """Remove a single job_id from the JSONL cache."""
    entries = [_e for _e in _cache_load_jobs() if _e.get("job_id") != job_id]
    try:
        with open(_GALLERY_CACHE_FILE, "w") as _f:
            for _e in entries:
                _f.write(_json.dumps(_e) + "\n")
    except Exception:
        pass

if os.path.isdir(_WEBAPP_DIST):
    app.mount("/webapp", _SF(directory=_WEBAPP_DIST, html=True), name="webapp_static")

USER_REFS: Dict[int, List[bytes]]  = {}   # 1–4 селфи (последние)
USER_LAST_OUTPUT: Dict[int, bytes] = {}     # последний результат
USER_LAST_OUTPUT_URL: Dict[int, str] = {}   # S3 URL для share
USER_LAST_PROMPT: Dict[int, str]   = {}   # последний prompt (ввод пользователя/сцена)
USER_LAST_REFINED_PROMPT: Dict[int, str] = {}  # фактический GPT-уточнённый промпт
USER_LANG: Dict[int, str]          = {}   # язык
USER_CREDITS: Dict[int, int]       = {}   # баланс
USER_SEEN_TEXT: Set[int]           = set()
USER_ONBOARDED: Set[int]           = set()
USER_LAST_JOB: Dict[int, str]      = {}
USER_LAST_ACTIVE: Dict[int, float] = {}   # timestamp последней активности — для TTL cleanup
USER_LAST_BONUS: Dict[int, float]  = {}   # timestamp последнего daily bonus
USER_STREAK: Dict[int, int]        = {}   # streak day count
USER_STREAK_REMINDED: Dict[int, float] = {}   # uid → timestamp of last streak-at-risk reminder sent
USER_QUEST_REMINDED:  Dict[int, float] = {}   # uid → timestamp of last quest-expiry reminder sent
USER_PORTFOLIO_PUBLIC: Dict[int, bool] = {}   # uid → portfolio is public (opt-in)

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

def _ref_save():
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = REF_FILE + ".tmp"
        payload = json.dumps({
            "map":   {str(k): int(v) for k, v in REF_MAP.items()},
            "stats": {str(k): v for k, v in REF_STATS.items()},
        }, ensure_ascii=False)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp, REF_FILE)
        _s3_put_text(STATE_PREFIX + "referrals.json", payload)
    except Exception as e:
        print("[ref] save error:", str(e)[:160])

def _ref_load():
    try:
        txt = _s3_get_text(STATE_PREFIX + "referrals.json")
        if not txt and os.path.exists(REF_FILE):
            with open(REF_FILE, "r", encoding="utf-8") as f:
                txt = f.read()
        if not txt:
            return
        data = json.loads(txt)
        for k, v in (data.get("map") or {}).items():
            try:
                REF_MAP[int(k)] = int(v)
            except Exception:
                continue
        for k, v in (data.get("stats") or {}).items():
            try:
                REF_STATS[int(k)] = {
                    "count":  int(v.get("count", 0)),
                    "earned": int(v.get("earned", 0)),
                }
            except Exception:
                continue
    except Exception as e:
        print("[ref] load error:", str(e)[:160])

_ref_load()

SUBS_FILE = os.getenv("SUBS_FILE", os.path.join(DATA_DIR, "subscriptions.json"))

def _subs_save():
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = SUBS_FILE + ".tmp"
        payload = json.dumps({str(k): v for k, v in USER_SUBSCRIPTION.items()}, ensure_ascii=False)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp, SUBS_FILE)
        _s3_put_text(STATE_PREFIX + "subscriptions.json", payload)
    except Exception as e:
        print("[subs] save error:", str(e)[:160])

def _subs_load():
    try:
        txt = _s3_get_text(STATE_PREFIX + "subscriptions.json")
        if not txt and os.path.exists(SUBS_FILE):
            with open(SUBS_FILE, "r", encoding="utf-8") as f:
                txt = f.read()
        if txt:
            data = json.loads(txt)
            for k, v in (data or {}).items():
                try:
                    USER_SUBSCRIPTION[int(k)] = v
                except Exception:
                    continue
    except Exception as e:
        print("[subs] load error:", str(e)[:160])

_subs_load()

def get_active_sub(uid: int) -> Optional[Dict]:
    sub = USER_SUBSCRIPTION.get(uid)
    if sub and sub.get("expires", 0) > time.time():
        return sub
    return None

# ---- Daily bonus persistence ----
BONUS_FILE = os.getenv("BONUS_FILE", os.path.join(DATA_DIR, "bonus.json"))

def _bonus_save():
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = BONUS_FILE + ".tmp"
        payload = json.dumps({
            "last": {str(k): v for k, v in USER_LAST_BONUS.items()},
            "streak": {str(k): v for k, v in USER_STREAK.items()},
        }, ensure_ascii=False)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp, BONUS_FILE)
        _s3_put_text(STATE_PREFIX + "bonus.json", payload)
    except Exception as e:
        print("[bonus] save error:", str(e)[:160])

def _bonus_load():
    try:
        txt = _s3_get_text(STATE_PREFIX + "bonus.json")
        if not txt and os.path.exists(BONUS_FILE):
            with open(BONUS_FILE, "r", encoding="utf-8") as f:
                txt = f.read()
        if txt:
            data = json.loads(txt)
            for k, v in (data.get("last") or {}).items():
                try: USER_LAST_BONUS[int(k)] = float(v)
                except Exception: pass
            for k, v in (data.get("streak") or {}).items():
                try: USER_STREAK[int(k)] = int(v)
                except Exception: pass
    except Exception as e:
        print("[bonus] load error:", str(e)[:160])

_bonus_load()

DAILY_WINDOW = 86400  # 24h in seconds
STREAK_RESET  = 172800  # 48h — miss a day = reset

def _claim_daily_bonus(uid: int) -> Optional[tuple]:
    """Try to claim daily bonus. Returns (gens_added, streak_day, milestone_bonus) or None if already claimed."""
    now = time.time()
    last = USER_LAST_BONUS.get(uid, 0)
    elapsed = now - last
    if elapsed < DAILY_WINDOW:
        return None  # already claimed today
    # Update streak
    prev_streak = USER_STREAK.get(uid, 0)
    if elapsed < STREAK_RESET:
        streak = prev_streak + 1
    else:
        streak = 1  # reset
    USER_STREAK[uid] = streak
    USER_LAST_BONUS[uid] = now
    # Determine bonus amount
    add = DAILY_STREAK_MILESTONES.get(streak, DAILY_BONUS_BASE)
    # Streak milestone bonus (one-time per milestone)
    milestone_bonus = 0
    if streak in STREAK_MILESTONE_BONUSES:
        ui = STATS_USERS_INFO.setdefault(uid, {})
        claimed_milestones = ui.get("streak_milestone_claimed", [])
        if streak not in claimed_milestones:
            milestone_bonus = STREAK_MILESTONE_BONUSES[streak]
            ui["streak_milestone_claimed"] = claimed_milestones + [streak]
            add += milestone_bonus
    USER_CREDITS[uid] = USER_CREDITS.get(uid, 0) + add
    _bonus_save()
    _credits_save()
    return (add, streak, milestone_bonus)

# ---- Style packs persistence ----
STYLE_PACKS_FILE = os.getenv("STYLE_PACKS_FILE", os.path.join(DATA_DIR, "style_packs.json"))

def _style_packs_save():
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        payload = json.dumps({
            "packs": {str(k): sorted(v) for k, v in USER_STYLE_PACKS.items()},
            "age":   {str(k): v for k, v in USER_AGE_PACKS.items()},
        }, ensure_ascii=False)
        tmp = STYLE_PACKS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp, STYLE_PACKS_FILE)
        _s3_put_text(STATE_PREFIX + "style_packs.json", payload)
    except Exception as e:
        print("[style_packs] save error:", str(e)[:160])

def _style_packs_load():
    try:
        txt = _s3_get_text(STATE_PREFIX + "style_packs.json")
        if not txt and os.path.exists(STYLE_PACKS_FILE):
            with open(STYLE_PACKS_FILE, "r", encoding="utf-8") as f:
                txt = f.read()
        if txt:
            data = json.loads(txt)
            for k, v in (data.get("packs") or {}).items():
                try: USER_STYLE_PACKS[int(k)] = set(v)
                except Exception: pass
            for k, v in (data.get("age") or {}).items():
                try: USER_AGE_PACKS[int(k)] = bool(v)
                except Exception: pass
    except Exception as e:
        print("[style_packs] load error:", str(e)[:160])

_style_packs_load()

# ===================== GIFT CREDITS =======================
GIFT_MAX_CREDITS  = int(os.getenv("GIFT_MAX_CREDITS", "50"))
GIFT_SENDER_BONUS = int(os.getenv("GIFT_SENDER_BONUS", "1"))  # bonus when gift is claimed
GIFT_CODES: Dict[str, Dict] = {}   # code → {from_uid, credits, created_at, claimed, claimed_by, claimed_at}
GIFTS_FILE = os.getenv("GIFTS_FILE", os.path.join(DATA_DIR, "gifts.json"))

def _gifts_save():
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        payload = json.dumps(GIFT_CODES, ensure_ascii=False)
        tmp = GIFTS_FILE + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp, GIFTS_FILE)
        _s3_put_text(STATE_PREFIX + "gifts.json", payload)
    except Exception as e:
        print("[gifts] save error:", str(e)[:160])

def _gifts_load():
    try:
        txt = _s3_get_text(STATE_PREFIX + "gifts.json")
        if not txt and os.path.exists(GIFTS_FILE):
            with open(GIFTS_FILE, "r", encoding="utf-8") as f:
                txt = f.read()
        if txt:
            data = json.loads(txt)
            now = time.time()
            for code, v in (data or {}).items():
                # Drop claimed codes older than 30 days; keep unclaimed for 7 days
                age = now - float(v.get("created_at", 0))
                if v.get("claimed") and age > 30 * 86400:
                    continue
                if not v.get("claimed") and age > 7 * 86400:
                    continue
                GIFT_CODES[code] = v
    except Exception as e:
        print("[gifts] load error:", str(e)[:160])

def _make_gift_code() -> str:
    import secrets
    return "gift_" + secrets.token_hex(4).upper()

_gifts_load()

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

async def _try_use_credits_n(uid: int, n: int, username: Optional[str] = None) -> bool:
    """Atomically pre-consume n credits. Returns False if balance < n."""
    if n <= 0:
        return True
    async with _credits_lock:
        if is_free_user(uid, username):
            return True
        if uid not in USER_CREDITS:
            USER_CREDITS[uid] = FREE_QUOTA
        if USER_CREDITS[uid] < n:
            return False
        USER_CREDITS[uid] -= n
    _credits_save()
    return True

async def _refund_credits_n(uid: int, n: int, username: Optional[str] = None):
    """Refund n credits after a failed tournament."""
    if n <= 0 or is_free_user(uid, username):
        return
    async with _credits_lock:
        USER_CREDITS[uid] = USER_CREDITS.get(uid, 0) + n
    _credits_save()

async def _maybe_give_milestone_bonus(ref_id: int, new_count: int):
    """Award milestone bonus to referrer and notify them."""
    bonus = REFERRAL_MILESTONES.get(new_count, 0)
    if not bonus:
        return
    async with _credits_lock:
        USER_CREDITS[ref_id] = USER_CREDITS.get(ref_id, 0) + bonus
    _credits_save()
    stats_incr(f"ref_milestone_{new_count}", 1)
    lang = USER_LANG.get(ref_id, LANG_DEFAULT)
    msg = {
        "ru": f"🏆 Milestone! Вы пригласили {new_count} друзей — +{bonus} кредитов в подарок!",
        "en": f"🏆 Milestone! {new_count} friends joined via your link — +{bonus} bonus credits!",
        "ro": f"🏆 Milestone! {new_count} prieteni s-au alăturat — +{bonus} credite bonus!",
        "de": f"🏆 Meilenstein! {new_count} Freunde beigetreten — +{bonus} Bonus-Credits!",
        "ar": f"🏆 إنجاز! انضم {new_count} أصدقاء — +{bonus} رصيد مجاني!",
    }.get(lang, f"🏆 Milestone! {new_count} friends joined — +{bonus} bonus credits!")
    try:
        await bot.send_message(ref_id, msg)
    except Exception:
        pass

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

# Subscriptions: {uid: {"plan": "pro"|"elite"|"weekly", "expires": float, "credits_per_month": int}}
USER_SUBSCRIPTION: Dict[int, Dict] = {}

# Style packs: {uid: set of pack_id strings}
USER_STYLE_PACKS: Dict[int, Set[str]] = {}
USER_AGE_PACKS:   Dict[int, bool]     = {}  # uid → True if Age Magic Pack purchased

# ── Quests ──────────────────────────────────────────────────────────────────
QUESTS_CONFIG = [
    {"id": "gen_daily_2",  "title": "Generate 2 photos",       "target": 2,  "reward": 2,  "icon": "📸", "type": "daily"},
    {"id": "gen_daily_5",  "title": "Generate 5 photos",       "target": 5,  "reward": 5,  "icon": "🔥", "type": "daily"},
    {"id": "try_preset",   "title": "Try a new style",          "target": 1,  "reward": 1,  "icon": "✨", "type": "daily"},
    {"id": "share_photo",  "title": "Share a photo",            "target": 1,  "reward": 2,  "icon": "📤", "type": "daily"},
    {"id": "streak_7",     "title": "Reach 7-day streak",       "target": 7,  "reward": 7,  "icon": "🏆", "type": "milestone"},
    {"id": "gen_50",       "title": "50 total generations",     "target": 50, "reward": 10, "icon": "💫", "type": "lifetime"},
    {"id": "invite_1",          "title": "Invite your first friend",  "target": 1,  "reward": 5,  "icon": "👥", "type": "lifetime"},
    {"id": "add_to_home_screen","title": "Add app to home screen",   "target": 1,  "reward": 5,  "icon": "🏠", "type": "lifetime"},
]
# uid → {quest_id: count}  (daily quests reset each UTC day)
USER_QUEST_PROGRESS: Dict[int, Dict[str, int]] = {}
# uid → {quest_id: date_string}  (when the quest was claimed — daily reset for daily type)
USER_QUEST_CLAIMED:  Dict[int, Dict[str, str]] = {}

# ── Achievements ─────────────────────────────────────────────────────────────
ACHIEVEMENTS_CONFIG = [
    {"id": "first_gen",   "title": "First Creation",   "icon": "🌟", "desc": "Generated your first AI photo"},
    {"id": "gen_10",      "title": "Creative Spark",   "icon": "✨", "desc": "10 photos generated"},
    {"id": "gen_50",      "title": "Prolific Creator", "icon": "🎨", "desc": "50 photos generated"},
    {"id": "gen_100",     "title": "Visionary",        "icon": "👑", "desc": "100 photos generated"},
    {"id": "streak_7",    "title": "Week Warrior",     "icon": "🔥", "desc": "7-day streak"},
    {"id": "streak_30",   "title": "Unstoppable",      "icon": "⚡", "desc": "30-day streak"},
    {"id": "invited_1",   "title": "Ambassador",       "icon": "🤝", "desc": "Invited a friend"},
    {"id": "invited_5",   "title": "Connector",        "icon": "🌐", "desc": "Invited 5 friends"},
    {"id": "paid_user",   "title": "Supporter",        "icon": "💎", "desc": "Made a purchase"},
    {"id": "all_presets", "title": "Style Explorer",   "icon": "🎭", "desc": "Used 10 different presets"},
]
# uid → set of unlocked achievement ids with timestamps: {id: timestamp}
USER_ACHIEVEMENTS: Dict[int, Dict[str, float]] = {}

# Photoshoot Tournament Mode
USER_PHOTOSHOOT_MODE: Dict[int, str]        = {}  # uid → mode key (e.g. "premium")
USER_PHOTOSHOOT_CUSTOM_DESC: Dict[int, str] = {}  # uid → vision text (custom mode)

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
# Milestone bonuses: invited count → bonus credits awarded to referrer
REFERRAL_MILESTONES: Dict[int, int] = {3: 5, 5: 8, 10: 15, 25: 30}
REF_FILE = os.getenv("REF_FILE", os.path.join(DATA_DIR, "referrals.json"))

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

# Premium Style Pack (490★ one-time unlock)
PREMIUM_STYLES = [
    {"key": "haute_couture",  "label_ru": "Высокая мода",  "label_en": "Haute Couture", "category": "artistic",
     "pack_id": "premium_pack_1", "emoji": "👗",
     "prompt": "haute couture fashion portrait, Vogue Paris editorial, extreme luxury, silk and lace, architectural lighting, flawless skin"},
    {"key": "cyberpunk",      "label_ru": "Киберпанк",     "label_en": "Cyberpunk",    "category": "cinematic",
     "pack_id": "premium_pack_1", "emoji": "🤖",
     "prompt": "cyberpunk portrait, holographic neons, rain-soaked urban dystopia, techwear outfit, blade runner atmosphere, vivid cyan magenta"},
    {"key": "oil_painting",   "label_ru": "Масло",         "label_en": "Oil Painting", "category": "artistic",
     "pack_id": "premium_pack_1", "emoji": "🎨",
     "prompt": "classical oil painting portrait, impasto brushwork, Flemish master lighting, rich saturated palette, museum quality masterpiece"},
    {"key": "watercolor",     "label_ru": "Акварель",      "label_en": "Watercolor",   "category": "artistic",
     "pack_id": "premium_pack_1", "emoji": "💧",
     "prompt": "watercolor portrait, soft washes, loose expressive brushwork, pastel tones, impressionistic style, delicate paper texture"},
    {"key": "anime_portrait", "label_ru": "Аниме",         "label_en": "Anime",        "category": "artistic",
     "pack_id": "premium_pack_1", "emoji": "⛩️",
     "prompt": "anime-style portrait, crisp cell shading, vibrant saturated palette, studio Ghibli quality, expressive large eyes, clean linework"},
    {"key": "art_deco",       "label_ru": "Арт Деко",      "label_en": "Art Déco",     "category": "artistic",
     "pack_id": "premium_pack_1", "emoji": "✦",
     "prompt": "art deco portrait, geometric ornamental background, gold and black palette, 1920s glamour, ornate symmetrical design"},
    {"key": "film_noir",      "label_ru": "Нуар",          "label_en": "Film Noir",    "category": "cinematic",
     "pack_id": "premium_pack_1", "emoji": "🕵️",
     "prompt": "film noir portrait, stark chiaroscuro, venetian blind shadow patterns, monochrome, 1940s detective atmosphere, rain on window"},
    {"key": "vaporwave",      "label_ru": "Вейпорвейв",    "label_en": "Vaporwave",    "category": "cinematic",
     "pack_id": "premium_pack_1", "emoji": "🌸",
     "prompt": "vaporwave aesthetic portrait, pink and purple gradient, retro CRT glow, 80s nostalgia, synthwave vibes, neon pastel"},
    {"key": "baroque",        "label_ru": "Барокко",       "label_en": "Baroque",      "category": "artistic",
     "pack_id": "premium_pack_1", "emoji": "🕯️",
     "prompt": "baroque portrait, Caravaggio chiaroscuro, dramatic shadow, ornate draping, museum masterpiece quality, deep rich colors"},
    {"key": "impressionist",  "label_ru": "Импрессионизм", "label_en": "Impressionist","category": "artistic",
     "pack_id": "premium_pack_1", "emoji": "🌸",
     "prompt": "impressionist portrait painting, Monet-style dappled light, loose visible brushstrokes, garden backdrop, warm dreamy palette"},
    {"key": "neo_tokyo",      "label_ru": "Нео-Токио",     "label_en": "Neo Tokyo",    "category": "cinematic",
     "pack_id": "premium_pack_1", "emoji": "🗼",
     "prompt": "neo-Tokyo street portrait, Akira-inspired neon dystopia, kanji signage, rain-slicked streets, dark futuristic atmosphere"},
    {"key": "grunge",         "label_ru": "Гранж",         "label_en": "Grunge",       "category": "lifestyle",
     "pack_id": "premium_pack_1", "emoji": "🎸",
     "prompt": "90s grunge portrait, desaturated Seattle aesthetic, flannel shirt, overcast outdoor light, raw film grain, Kurt Cobain era"},
    {"key": "cottagecore",    "label_ru": "Коттедж",       "label_en": "Cottagecore",  "category": "lifestyle",
     "pack_id": "premium_pack_1", "emoji": "🌿",
     "prompt": "cottagecore portrait, wildflower meadow, soft golden light, linen dress, pastoral dreamy aesthetic, bees and butterflies"},
    {"key": "luxe_hotel",     "label_ru": "Люкс-отель",    "label_en": "Luxe Hotel",   "category": "lifestyle",
     "pack_id": "premium_pack_1", "emoji": "🏨",
     "prompt": "five-star hotel suite portrait, Italian marble, warm chandelier glow, silk robe, ultra-luxury editorial, opulent setting"},
    {"key": "desert_fashion", "label_ru": "Пустыня",       "label_en": "Desert Fashion","category": "outdoor",
     "pack_id": "premium_pack_1", "emoji": "🏜️",
     "prompt": "desert fashion editorial, red dunes, harsh directional sun, couture styling, National Geographic quality, warm earth tones"},
]

# Age Magic Pack (290★ one-time) — 4 age transformation styles
AGE_STYLES = [
    {"key": "age_young_10", "label_ru": "−10 лет", "label_en": "−10 Years",
     "emoji": "✨", "prompt": "youthful face, 10 years younger, smooth radiant skin, vibrant energetic look, natural beauty"},
    {"key": "age_young_20", "label_ru": "−20 лет", "label_en": "−20 Years",
     "emoji": "🌟", "prompt": "very young face, 20 years younger, fresh youthful appearance, smooth flawless skin, bright eyes"},
    {"key": "age_older_10", "label_ru": "+10 лет",  "label_en": "+10 Years",
     "emoji": "🍂", "prompt": "mature distinguished face, 10 years older, elegant silver streaks, wise confident expression"},
    {"key": "age_older_20", "label_ru": "+20 лет",  "label_en": "+20 Years",
     "emoji": "🌿", "prompt": "older distinguished face, 20 years older, silver hair, deep character lines, wise dignified presence"},
]

# Preset Packs — themed scene/mood presets sold as one-time Star purchases
PRESET_PACKS: Dict[str, Dict] = {
    "viral_pack": {
        "label_en": "Viral Social", "label_ru": "Соц. сети", "emoji": "📱",
        "stars": VIRAL_PACK_STARS, "category": "lifestyle",
        "presets": [
            {"key": "dark_academia",    "emoji": "🎓", "label_en": "Dark Academia",   "label_ru": "Дарк Академия",
             "prompt": "dark academia aesthetic portrait, ivy-league library, warm candlelight, turtleneck and tweed blazer, leather-bound books, moody intellectual atmosphere, golden hour"},
            {"key": "y2k_glam",         "emoji": "💿", "label_en": "Y2K Glam",        "label_ru": "Y2K Гламур",
             "prompt": "Y2K aesthetic portrait, early 2000s nostalgia, metallic silver outfit, butterfly clips, frosted glossy lips, pop-star energy, vibrant saturated color"},
            {"key": "barbiecore",       "emoji": "💗", "label_en": "Barbiecore",       "label_ru": "Барбикор",
             "prompt": "Barbiecore portrait, bubblegum pink backdrop, plastic fantastic editorial, glitter and glam, bright hot pinks, campy fashion photography, fun bold colors"},
            {"key": "soft_aesthetic",   "emoji": "🌸", "label_en": "Soft Aesthetic",   "label_ru": "Мягкая эстетика",
             "prompt": "soft girl aesthetic portrait, pastel palette, butterflies and wildflowers, blush pink tones, dreamy light leak, wholesome sweet mood, cottagecore edge"},
            {"key": "e_girl",           "emoji": "🖤", "label_en": "E-Girl",           "label_ru": "Е-гёрл",
             "prompt": "e-girl aesthetic portrait, alt fashion, layered chains, blush under eyes, dark streaks, bedroom ring light, edgy-cute hybrid, TikTok generation"},
            {"key": "indie_alt",        "emoji": "🌻", "label_en": "Indie Alt",        "label_ru": "Инди Альт",
             "prompt": "indie alternative aesthetic portrait, thrift-store layers, golden analog film grain, lo-fi vignette, muted warm tones, authentic raw candid mood"},
        ],
    },
    "locations_pack": {
        "label_en": "World Locations", "label_ru": "Локации мира", "emoji": "🌍",
        "stars": LOCATIONS_PACK_STARS, "category": "outdoor",
        "presets": [
            {"key": "paris_cafe",       "emoji": "🥐", "label_en": "Paris Café",       "label_ru": "Парижское кафе",
             "prompt": "Paris sidewalk café portrait, Eiffel Tower soft bokeh, morning golden light, French bistro atmosphere, cobblestone street, espresso and croissant"},
            {"key": "tokyo_night",      "emoji": "🏙", "label_en": "Tokyo Night",       "label_ru": "Токийская ночь",
             "prompt": "Shinjuku night street portrait, golden lanterns and vibrant neon signs, Japanese architecture bokeh, light rain puddles, cinematic Tokyo atmosphere"},
            {"key": "maldives_beach",   "emoji": "🌊", "label_en": "Maldives",          "label_ru": "Мальдивы",
             "prompt": "Maldives overwater bungalow portrait, turquoise crystal lagoon, white sand beach, tropical golden hour, luxury paradise, resort lifestyle"},
            {"key": "nyc_penthouse",    "emoji": "🗽", "label_en": "NYC Penthouse",     "label_ru": "Пентхаус NYC",
             "prompt": "NYC penthouse rooftop portrait, Manhattan skyline at blue hour, city lights bokeh, floor-to-ceiling glass, power and luxury lifestyle, golden dusk"},
            {"key": "tuscany_vineyard", "emoji": "🍷", "label_en": "Tuscany",           "label_ru": "Тоскана",
             "prompt": "Tuscany countryside portrait, rolling golden hills, cypress tree lanes, vineyard at sunset, Italian villa bokeh, warm Mediterranean late afternoon light"},
            {"key": "dubai_skyline",    "emoji": "🌃", "label_en": "Dubai",             "label_ru": "Дубай",
             "prompt": "Dubai skyline portrait, Burj Khalifa backdrop, luxury desert city at golden hour, ultra-modern glass architecture, dramatic editorial travel photography"},
        ],
    },
    "fantasy_pack": {
        "label_en": "Fantasy & Sci-Fi", "label_ru": "Фэнтези и Sci-Fi", "emoji": "⚔️",
        "stars": FANTASY_PACK_STARS, "category": "cinematic",
        "presets": [
            {"key": "medieval_castle",  "emoji": "⚔️", "label_en": "Medieval Castle",  "label_ru": "Средневековье",
             "prompt": "medieval fantasy portrait, castle stone walls, flickering torchlight, chainmail and wool cloak, epic fantasy film quality, dramatic heroic lighting"},
            {"key": "space_station",    "emoji": "🚀", "label_en": "Space Station",     "label_ru": "Космос",
             "prompt": "space station portrait, Earth visible through porthole window, zero gravity atmosphere, NASA quality photography, cosmic stars background, astronaut aesthetic"},
            {"key": "elven_forest",     "emoji": "🌿", "label_en": "Elven Forest",      "label_ru": "Эльфийский лес",
             "prompt": "Elven forest portrait, magical bioluminescent trees, ethereal light beams, flowing elvish robes, Lord of the Rings quality, mystical fantasy atmosphere"},
            {"key": "cyberpunk_alley",  "emoji": "🤖", "label_en": "Cyberpunk Alley",   "label_ru": "Киберпанк",
             "prompt": "cyberpunk back-alley portrait, holographic billboard ads, acid rain, techwear outfit, dystopian megacity, Blade Runner 2049 cinematic quality"},
            {"key": "victorian_manor",  "emoji": "🕯", "label_en": "Victorian Manor",   "label_ru": "Викторианство",
             "prompt": "Victorian manor portrait, antique drawing room, fireplace amber glow, ornate wallpaper, period drama BBC quality, candlelit elegant atmosphere"},
            {"key": "pirates_cove",     "emoji": "🏴‍☠️", "label_en": "Pirate Cove",  "label_ru": "Пиратская бухта",
             "prompt": "pirate cove portrait, tall ship and ocean at sunset, weathered wood and rigging, period pirate costume, dramatic adventure film cinematography"},
        ],
    },
}

# Preset category mapping
_PRESET_CATEGORY_MAP = {
    "studio_soft": "studio", "editorial_highkey": "studio", "beauty_dish": "studio",
    "headshot": "studio", "rembrandt": "studio",
    "cinematic": "cinematic", "bw_film": "cinematic", "kodak_portra": "cinematic",
    "vintage70": "cinematic", "mono_hicon": "cinematic", "soft_glam": "cinematic",
    "golden_hour": "outdoor", "forest": "outdoor", "beach": "outdoor",
    "park": "outdoor", "snow": "outdoor", "rain_window": "outdoor",
    "cafe": "lifestyle", "fitness": "lifestyle", "garage": "lifestyle",
    "bookstore": "lifestyle", "architecture": "lifestyle", "luxury_interior": "lifestyle",
}
def _preset_category(key: str) -> str:
    return _PRESET_CATEGORY_MAP.get(key, "lifestyle")

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
        "onboard_btn_examples": "📸 Посмотреть примеры →",
        "onboard_modes_intro": "🎨 *Что умеет iModel:*\n\n{modes_list}\n\nВаш стартовый баланс: *{credits}⚡*",
        "onboard_send_selfie": "📷 Отправьте своё селфи — сделаю первое фото прямо сейчас.\n\n*Совет:* хорошее освещение + лицо крупным планом = лучший результат.",
        "start": "С возвращением ✨\n\nОтправьте селфи — и я создам новое фото.",
        "help": "🆘 Помощь\n\nКак получить лучший результат:\n• Пришлите 1 селфи при ровном свете, без сильных фильтров\n• В описании укажите место, свет, стиль, кадрирование, настроение\n• Быстрый старт: откройте Пресеты и выберите стиль\n• Скопировать сцену: режим ‘Скопировать’ — сначала образец, затем селфи\n\nОплата и баланс:\n• Покупка — раздел ‘Купить’ (Telegram Stars)\n• Списание — только при успешной генерации (кроме whitelist/админ)\n• Промокоды — команда /promo КОД\n\nРеферальная программа:\n• Пригласи друга — ты +{ref_ref}, новый пользователь +{ref_new}\n• Твоя ссылка: /refer\n\nПравила и приватность:\n• Запрещены NSFW/селебы\n• Фото хранятся временно; /clear — очистка, /forget — полное удаление\n\nНужна помощь? Напишите @piciriga — ответим быстро.",
        "need_photo": "Сначала пришли фото лица.",
        "photo_ok": "Фото получено ✅ Теперь опишите сцену или используйте /presets.",
        "gen": "Генерирую… ⏳",
        "fail": "Не удалось сгенерировать. Попробуйте изменить описание или фото.",
        "ready": "Готово ✅",
        "credits_none": "💎 Генерации закончились\n\nТы уже видел, как работает iModel — теперь знаешь, чего это стоит.\n\nВыбери тариф и продолжи:",
        "credits_none_paid": "💎 Кредиты закончились\n\nВы уже знаете результат — не останавливайтесь.\n\nПополните баланс и продолжите:",
        "credits_none_active": "⚡ Генерации закончились\n\nВы уже сделали несколько крутых фото — загляните ещё дальше.\n\nВыберите пакет:",
        "credits_none_first": "✨ Бесплатные генерации использованы\n\nВам понравилось? Продолжайте — лучшие результаты ещё впереди.\n\nВыберите свой план:",
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
        "btn_share": "Поделиться",
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
        "btn_sub": "📅 Подписка",
        "sub_title": "📅 Подписка iModel\n\nАвтопродление каждый месяц. Отменить — в настройках Telegram.",
        "sub_pro_btn":   f"⚡ Pro — {SUB_PRO_STARS}★/мес · {SUB_PRO_CREDITS} ген",
        "sub_elite_btn": f"💎 Elite — {SUB_ELITE_STARS}★/мес · {SUB_ELITE_CREDITS} ген",
        "sub_bought":  "✅ Подписка {plan} активна! +{add} генераций. Баланс: {all}.",
        "sub_renewed": "🔄 Подписка {plan} продлена. +{add} генераций. Баланс: {all}.",
        "sub_active":  "📅 {plan} — активна до {date}",
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
        "daily_claimed": "🎁 +{n} ген! День {streak} подряд.",
        "daily_milestone_3":  "🔥 3 дня подряд! +{n} ген в подарок!",
        "daily_milestone_7":  "⚡ Неделя подряд! +{n} ген в подарок!",
        "daily_milestone_14": "💎 2 недели подряд! +{n} ген в подарок!",
        "daily_milestone_30": "🏆 Месяц подряд! +{n} ген в подарок!",
        "daily_already": "✅ Бонус уже получен. Следующий через {h}ч.",
        "daily_cmd": "🔥 Серия: {streak} дн.\n🎁 Бонус: +{next_n} ген через {h}ч.",
    },
    "en": {
        "menu_lang": "🌐 Language",
        "onboard_welcome": "📸 *iModel* — professional photos from your selfie.\n\nOne photo. Thirty seconds. Studio-quality result.\n\n✨ {quota} free generations — no sign-up needed.",
        "onboard_btn": "🚀 Try for free",
        "onboard_btn_examples": "📸 See AI examples →",
        "onboard_modes_intro": "🎨 *What iModel can do:*\n\n{modes_list}\n\nYour starting balance: *{credits}⚡*",
        "onboard_send_selfie": "📷 Send your selfie — I’ll create your first photo right now.\n\n*Tip:* good lighting + face in frame = best result.",
        "start": "Welcome back ✨\n\nSend a selfie and I’ll create a new photo for you.",
        "help": "🆘 Help\n\nBest results:\n• Send 1 selfie in even lighting, minimal filters\n• In your prompt describe location, light, style, framing, mood\n• Quick start: open Presets and pick a style\n• Copy a scene: use ‘Copy’ — first the reference, then your selfie\n\nPayments & balance:\n• Buy in ‘Buy’ (Telegram Stars)\n• Credits are deducted only on successful generation (except whitelist/admin)\n• Promo codes — /promo CODE\n\nReferral program:\n• Invite a friend — you +{ref_ref}, they +{ref_new}\n• Your link: /refer\n\nRules & privacy:\n• NSFW/celebrities are forbidden\n• Photos are stored temporarily; /clear to purge temp, /forget for full delete\n\nNeed help? Message @piciriga — we’ll reply quickly.",
        "need_photo": "Please send a face photo first.",
        "photo_ok": "Photo received ✅ Now describe the scene or use /presets.",
        "gen": "Working… ⏳",
        "fail": "Generation failed. Try adjusting your description or selfie.",
        "ready": "Done ✅",
        "credits_none": "💎 Out of generations\n\nYou've seen what iModel can do — keep going.\n\nChoose a plan:",
        "credits_none_paid": "💎 Credits used up\n\nYou already know the quality — don't stop now.\n\nTop up and keep creating:",
        "credits_none_active": "⚡ Out of generations\n\nYou've made some great photos — there's more to explore.\n\nPick a pack:",
        "credits_none_first": "✨ Free credits used\n\nLiked what you saw? The best results are ahead.\n\nChoose your plan:",
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
        "btn_share": "Share",
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
        "btn_sub": "📅 Subscription",
        "sub_title": "📅 iModel Subscription\n\nAuto-renews monthly. Cancel anytime in Telegram settings.",
        "sub_pro_btn":   f"⚡ Pro — {SUB_PRO_STARS}★/mo · {SUB_PRO_CREDITS} gens",
        "sub_elite_btn": f"💎 Elite — {SUB_ELITE_STARS}★/mo · {SUB_ELITE_CREDITS} gens",
        "sub_bought":  "✅ {plan} subscription active! +{add} generations. Balance: {all}.",
        "sub_renewed": "🔄 {plan} subscription renewed. +{add} generations. Balance: {all}.",
        "sub_active":  "📅 {plan} — active until {date}",
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
        "daily_claimed": "🎁 +{n} gen! Day {streak} in a row.",
        "daily_milestone_3":  "🔥 3 days in a row! +{n} gens as a gift!",
        "daily_milestone_7":  "⚡ One week in a row! +{n} gens as a gift!",
        "daily_milestone_14": "💎 Two weeks in a row! +{n} gens as a gift!",
        "daily_milestone_30": "🏆 One month in a row! +{n} gens as a gift!",
        "daily_already": "✅ Already claimed today. Next bonus in {h}h.",
        "daily_cmd": "🔥 Streak: {streak} days\n🎁 Bonus: +{next_n} gens in {h}h.",
    },
    "ro": {
        "menu_lang": "🌐 Limba",
        "onboard_welcome": "📸 *iModel* — fotografii profesionale din selfie-ul tău.\n\nO poză. Treizeci de secunde. Rezultat de studio.\n\n✨ {quota} generări gratuite — fără înregistrare.",
        "onboard_btn": "🚀 Încearcă gratuit",
        "onboard_modes_intro": "🎨 *Ce poate face iModel:*\n\n{modes_list}\n\nSoldul tău de start: *{credits}⚡*",
        "onboard_send_selfie": "📷 Trimite selfie-ul tău — creez prima fotografie chiar acum.\n\n*Sfat:* lumină bună + față în cadru = cel mai bun rezultat.",
        "start": "Bun venit înapoi ✨\n\nTrimite un selfie și creez o nouă fotografie pentru tine.",
        "help": "🆘 Ajutor\n\nRezultate mai bune:\n• Trimite 1 selfie cu lumină uniformă, fără filtre puternice\n• În descriere: locație, lumină, stil, încadrare, mood\n• Start rapid: deschide Preseturi și alege un stil\n• Copiere scenă: ‘Copiază’ — mai întâi referința, apoi selfie‑ul\n\nPlăți & sold:\n• Cumpără în ‘Cumpără’ (Stele Telegram)\n• Creditul se scade doar la generare reușită (exceptând whitelist/admin)\n• Cod promo — /promo COD\n\nProgram de recomandări:\n• Invită un prieten — tu +{ref_ref}, el/ea +{ref_new}\n• Linkul tău: /refer\n\nReguli & confidențialitate:\n• NSFW/celebr. interzise\n• Pozele se păstrează temporar; /clear curăță, /forget ștergere totală\n\nAi nevoie de ajutor? Scrie la @piciriga — răspundem rapid.",
        "need_photo": "Trimite o poză cu fața mai întâi.",
        "photo_ok": "Poză primită ✅ Acum descrie scena sau folosește /presets.",
        "gen": "Generez… ⏳",
        "fail": "Nu am reușit. Încearcă altă descriere sau alt selfie.",
        "ready": "Gata ✅",
        "credits_none": "💎 Generațiile s-au terminat\n\nAi văzut ce poate iModel — continuă.\n\nAlege un plan:",
        "credits_none_paid": "💎 Credite epuizate\n\nȘtii deja calitatea — nu te opri acum.\n\nReîncarcă și continuă:",
        "credits_none_active": "⚡ Generații epuizate\n\nAi creat câteva poze excelente — explorează mai mult.\n\nAlege un pachet:",
        "credits_none_first": "✨ Credite gratuite folosite\n\nȚi-a plăcut? Cele mai bune rezultate urmează.\n\nAlege planul tău:",
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
        "btn_share": "Distribuie",
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
        "btn_sub": "📅 Abonament",
        "sub_title": "📅 Abonament iModel\n\nReînnoire automată lunară. Anulează din setările Telegram.",
        "sub_pro_btn":   f"⚡ Pro — {SUB_PRO_STARS}★/lună · {SUB_PRO_CREDITS} gen",
        "sub_elite_btn": f"💎 Elite — {SUB_ELITE_STARS}★/lună · {SUB_ELITE_CREDITS} gen",
        "sub_bought":  "✅ Abonament {plan} activ! +{add} generații. Sold: {all}.",
        "sub_renewed": "🔄 Abonament {plan} reînnoit. +{add} generații. Sold: {all}.",
        "sub_active":  "📅 {plan} — activ până la {date}",
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
        "daily_claimed": "🎁 +{n} gen! Ziua {streak} la rând.",
        "daily_milestone_3":  "🔥 3 zile la rând! +{n} gen cadou!",
        "daily_milestone_7":  "⚡ O săptămână la rând! +{n} gen cadou!",
        "daily_milestone_14": "💎 Două săptămâni la rând! +{n} gen cadou!",
        "daily_milestone_30": "🏆 O lună la rând! +{n} gen cadou!",
        "daily_already": "✅ Bonus primit azi. Următorul în {h}h.",
        "daily_cmd": "🔥 Serie: {streak} zile\n🎁 Bonus: +{next_n} gen în {h}h.",
        "refer_msg": "👥 Invită prieteni și primește generații bonus!\nLinkul tău: {link}\n\nInvitați: {count}\nBonusuri obținute: {earned}",
        "style_share_btn": "✨ În acest stil",
        "style_share_intro": "Stil încărcat ✅ Trimite un selfie — generez un rezultat similar.",
    }
    ,
    "de": {
        "menu_lang": "🌐 Sprache",
        "onboard_welcome": "📸 *iModel* — professionelle Fotos aus deinem Selfie.\n\nEin Foto. Dreißig Sekunden. Studio-Qualität.\n\n✨ {quota} kostenlose Generierungen — ohne Anmeldung.",
        "onboard_btn": "🚀 Kostenlos testen",
        "onboard_modes_intro": "🎨 *Was iModel kann:*\n\n{modes_list}\n\nDein Startguthaben: *{credits}⚡*",
        "onboard_send_selfie": "📷 Schicke dein Selfie — ich erstelle dein erstes Foto jetzt gleich.\n\n*Tipp:* gutes Licht + Gesicht im Bild = bestes Ergebnis.",
        "start": "Willkommen zurück ✨\n\nSchicke ein Selfie und ich erstelle ein neues Foto für dich.",
        "help": "🆘 Hilfe\n\nBeste Ergebnisse:\n• 1 Selfie bei gleichmäßiger Beleuchtung, ohne starke Filter\n• Beschreibe Ort, Licht, Stil, Bildausschnitt, Stimmung\n• Schnellstart: Presets öffnen und Stil wählen\n• Szene kopieren: ‘Kopieren’ — zuerst Referenz, dann Selfie\n\nZahlung & Guthaben:\n• Kaufen in ‘Kaufen’ (Telegram Stars)\n• Abzug nur bei erfolgreicher Generierung (außer Whitelist/Admin)\n• Promo‑Code — /promo CODE\n\nEmpfehlungsprogramm:\n• Freund einladen — du +{ref_ref}, er/sie +{ref_new}\n• Dein Link: /refer\n\nRegeln & Datenschutz:\n• NSFW/Promis verboten\n• Fotos werden temporär gespeichert; /clear löscht temporär, /forget vollständig\n\nBrauchen Sie Hilfe? Schreiben Sie @piciriga — wir antworten schnell.",
        "need_photo": "Bitte zuerst ein Gesichts‑Foto senden.",
        "photo_ok": "Foto empfangen ✅ Beschreibe jetzt die Szene oder nutze /presets.",
        "gen": "Erzeuge… ⏳",
        "fail": "Erzeugung fehlgeschlagen. Bitte Beschreibung oder Selfie anpassen.",
        "ready": "Fertig ✅",
        "credits_none": "💎 Keine Generierungen mehr\n\nDu hast iModel kennengelernt — mach weiter.\n\nWähle einen Plan:",
        "credits_none_paid": "💎 Credits aufgebraucht\n\nDu kennst die Qualität — hör nicht auf.\n\nAufladen und weitermachen:",
        "credits_none_active": "⚡ Generierungen aufgebraucht\n\nDu hast tolle Fotos gemacht — entdecke mehr.\n\nWähle ein Paket:",
        "credits_none_first": "✨ Kostenlose Credits verwendet\n\nGefällt dir das Ergebnis? Die besten Resultate kommen noch.\n\nWähle deinen Plan:",
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
        "btn_share": "Teilen",
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
        "btn_sub": "📅 Abo",
        "sub_title": "📅 iModel Abo\n\nAutomatische monatliche Verlängerung. Kündigung in Telegram-Einstellungen.",
        "sub_pro_btn":   f"⚡ Pro — {SUB_PRO_STARS}★/Monat · {SUB_PRO_CREDITS} Gen",
        "sub_elite_btn": f"💎 Elite — {SUB_ELITE_STARS}★/Monat · {SUB_ELITE_CREDITS} Gen",
        "sub_bought":  "✅ {plan}-Abo aktiv! +{add} Generierungen. Guthaben: {all}.",
        "sub_renewed": "🔄 {plan}-Abo verlängert. +{add} Generierungen. Guthaben: {all}.",
        "sub_active":  "📅 {plan} — aktiv bis {date}",
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
        "daily_claimed": "🎁 +{n} Gen! Tag {streak} in Folge.",
        "daily_milestone_3":  "🔥 3 Tage in Folge! +{n} Gen als Geschenk!",
        "daily_milestone_7":  "⚡ Eine Woche in Folge! +{n} Gen als Geschenk!",
        "daily_milestone_14": "💎 Zwei Wochen in Folge! +{n} Gen als Geschenk!",
        "daily_milestone_30": "🏆 Ein Monat in Folge! +{n} Gen als Geschenk!",
        "daily_already": "✅ Bonus bereits erhalten. Nächster in {h}h.",
        "daily_cmd": "🔥 Serie: {streak} Tage\n🎁 Bonus: +{next_n} Gen in {h}h.",
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

def s3_upload_and_key(
    img_bytes: bytes,
    key_prefix: str = "inputs/",
    content_type: str = "image/jpeg",
) -> tuple:
    """Upload to S3 and return (presigned_url, s3_key) with 7-day expiry. Both None on error."""
    if not all([S3_BUCKET, S3_KEY_ID, S3_SECRET, S3_ENDPOINT, S3_REGION]):
        return None, None
    key = f"{key_prefix}{int(time.time())}_{hashlib.md5(img_bytes).hexdigest()[:8]}.jpg"
    try:
        _s3.put_object(Bucket=S3_BUCKET, Key=key, Body=img_bytes, ContentType=content_type)
        url = _s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": S3_BUCKET, "Key": key},
            ExpiresIn=604800,
        )
        return url, key
    except Exception as e:
        print(f"S3 upload_and_key error: {e}")
        return None, None


def s3_presign_key(key: str, expires: int = 604800) -> Optional[str]:
    """Generate a fresh presigned URL for an existing S3 key (7-day default)."""
    if not all([S3_BUCKET, S3_KEY_ID, S3_SECRET, S3_ENDPOINT]):
        return None
    try:
        return _s3.generate_presigned_url(
            ClientMethod="get_object",
            Params={"Bucket": S3_BUCKET, "Key": key},
            ExpiresIn=expires,
        )
    except Exception:
        return None


def s3_delete_key(key: str) -> bool:
    """Delete an S3 object by key. Returns True on success."""
    if not all([S3_BUCKET, S3_KEY_ID, S3_SECRET, S3_ENDPOINT]) or not key:
        return False
    try:
        _s3.delete_object(Bucket=S3_BUCKET, Key=key)
        return True
    except Exception as e:
        print(f"[s3] delete_object error for {key}: {str(e)[:120]}")
        return False


def s3_put_at_key(img_bytes: bytes, key: str, content_type: str = "image/jpeg") -> bool:
    """Upload to S3 at a specific fixed key (no random suffix)."""
    if not all([S3_BUCKET, S3_KEY_ID, S3_SECRET, S3_ENDPOINT]):
        return False
    try:
        _s3.put_object(Bucket=S3_BUCKET, Key=key, Body=img_bytes, ContentType=content_type)
        return True
    except Exception as e:
        print(f"S3 put_at_key error: {e}")
        return False


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

def enhance_face_codeformer(image_bytes: bytes, fidelity: float = 0.8, upscale: int = 2) -> bytes:
    if not CODEFORMER_MODEL or not image_bytes:
        return enhance_face_gfpgan(image_bytes)
    try:
        out = replicate.run(
            CODEFORMER_MODEL,
            input={
                "image": io.BytesIO(image_bytes),
                "codeformer_fidelity": fidelity,
                "background_enhance": upscale >= 4,
                "face_upsample": True,
                "upscale": upscale,
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

# ===== AI Caption Generator =====
def _fallback_captions(style_label: str) -> List[str]:
    tag = "#" + style_label.lower().replace(" ", "").replace("-", "")
    return [
        f"Living my best life ✨ {tag} #AIPhotos #PortraitPhotography",
        f"AI did that 🤖📸 {tag} #AIArt #DigitalArt",
        f"New look, who dis? 👀 {tag} #PhotoEdit #AIGenerated",
    ]

def generate_captions_gpt(style_label: str, mode_key: str) -> List[str]:
    if not OPENAI_API_KEY or OpenAI is None:
        return _fallback_captions(style_label)
    try:
        client = OpenAI(api_key=OPENAI_API_KEY)
        style_desc = style_label if style_label else mode_key
        sys_msg = (
            "You are a social media copywriter for AI portrait photography. "
            "Write punchy, authentic captions that feel human — not AI-generated. "
            "Each caption must be under 150 characters including hashtags. "
            "Include 3–5 relevant hashtags at the end of each caption."
        )
        user_msg = (
            f"Write 3 distinct captions for an AI portrait in the '{style_desc}' style. "
            "Vary the tone: one playful, one confident, one aspirational. "
            "Separate each caption with '---' on its own line. No numbering or labels."
        )
        resp = client.chat.completions.create(
            model=OPENAI_MODEL,
            messages=[{"role": "system", "content": sys_msg},
                      {"role": "user", "content": user_msg}],
            temperature=0.85,
            max_tokens=400,
            timeout=30,
        )
        raw = (resp.choices[0].message.content or "").strip()
        parts = [c.strip() for c in raw.split("---") if c.strip()]
        return parts[:3] if len(parts) >= 1 else _fallback_captions(style_label)
    except Exception as e:
        print("GPT caption error:", str(e)[:200])
        return _fallback_captions(style_label)


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

# ===== AI Vision Judge for Generation Tournament =====
_VISION_JUDGE_ENABLED = os.getenv("DISABLE_VISION_JUDGE", "0") != "1"

def _judge_candidate_vision(candidate_bytes: bytes, face_bytes: bytes, mode_key: str) -> float:
    """
    Score a tournament candidate using GPT-4o Vision.
    Evaluates face preservation (0-40) + technical quality (0-35) + style match (0-25).
    Falls back to size+noise stub if OpenAI unavailable or call fails.
    """
    if not _VISION_JUDGE_ENABLED or not OPENAI_API_KEY or OpenAI is None:
        return _score_candidate(candidate_bytes)
    if not candidate_bytes or not face_bytes:
        return _score_candidate(candidate_bytes)
    try:
        from photoshoot_modes import get_mode_config as _gmc
        cfg = _gmc(mode_key)
        mode_label = cfg["label"].get("en", mode_key)
        style_goal = cfg.get("prompt_layer") or "natural portrait"

        system_msg = (
            "You are a strict AI photo quality judge for a portrait generation system. "
            "Evaluate the generated portrait. Return ONLY valid JSON, nothing else."
        )
        user_text = (
            f'Mode: "{mode_label}"\n'
            f'Style goal: {style_goal}\n\n'
            "Score the generated photo (image 2) compared to the original face (image 1):\n"
            "• face_score 0-40: Identity preserved? Face sharp, natural, no deformations, no melted features\n"
            "• quality_score 0-35: Technical quality — sharpness, lighting, no artifacts, proper anatomy\n"
            "• style_score 0-25: Does it match the mode's aesthetic?\n\n"
            'Return ONLY this JSON with integers: {"face_score": 0, "quality_score": 0, "style_score": 0}'
        )

        face_b64 = base64.b64encode(face_bytes).decode()
        cand_b64 = base64.b64encode(candidate_bytes).decode()

        client = OpenAI(api_key=OPENAI_API_KEY)
        r = client.chat.completions.create(
            model=OPENAI_MODEL_VISION,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": "Image 1 — original face (identity reference):"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{face_b64}", "detail": "low"}},
                    {"type": "text", "text": "Image 2 — generated result to evaluate:"},
                    {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{cand_b64}", "detail": "low"}},
                    {"type": "text", "text": user_text},
                ],
            }],
            temperature=0.1,
            max_tokens=60,
            timeout=25,
        )
        raw = (r.choices[0].message.content or "").strip()
        import re as _re
        m = _re.search(r'\{[^}]+\}', raw)
        if not m:
            return _score_candidate(candidate_bytes)
        data = json.loads(m.group())
        total = (
            int(data.get("face_score", 0))
            + int(data.get("quality_score", 0))
            + int(data.get("style_score", 0))
        )
        stats_incr("vision_judge_ok", 1)
        return float(max(0, min(total, 100)))
    except Exception as e:
        stats_incr("vision_judge_fail", 1)
        print(f"Vision judge error: {str(e)[:120]}")
        return _score_candidate(candidate_bytes)


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
NUDGE_DAY_START_HOUR = int(os.getenv("NUDGE_DAY_START_HOUR", "10"))
NUDGE_DAY_END_HOUR = int(os.getenv("NUDGE_DAY_END_HOUR", "20"))
NUDGE_TZ_DEFAULT = os.getenv("NUDGE_TZ_DEFAULT", "UTC")
NUDGE_MAX_TOTAL = int(os.getenv("NUDGE_MAX_TOTAL", "7"))    # stop nudging after N total
NUDGE_WEEKLY_CAP = int(os.getenv("NUDGE_WEEKLY_CAP", "3"))  # max per 7-day window
NUDGE_SEND_DELAY = float(os.getenv("NUDGE_SEND_DELAY", "0.4"))  # seconds between sends (TG rate limit)
NUDGE_INFO: Dict[int, Dict[str, object]] = {}
NUDGE_FILE = os.getenv("NUDGE_FILE", os.path.join(DATA_DIR, "nudges.json"))

def _nudge_save():
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        tmp = NUDGE_FILE + ".tmp"
        payload = json.dumps({str(k): v for k, v in NUDGE_INFO.items()}, ensure_ascii=False)
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(payload)
        os.replace(tmp, NUDGE_FILE)
        _s3_put_text(STATE_PREFIX + "nudges.json", payload)
    except Exception as e:
        print("[nudge] save error:", str(e)[:160])

def _nudge_load():
    try:
        txt = _s3_get_text(STATE_PREFIX + "nudges.json")
        if not txt and os.path.exists(NUDGE_FILE):
            with open(NUDGE_FILE, "r", encoding="utf-8") as f:
                txt = f.read()
        if not txt:
            return
        for k, v in json.loads(txt).items():
            try:
                NUDGE_INFO[int(k)] = v
            except Exception:
                continue
    except Exception as e:
        print("[nudge] load error:", str(e)[:160])

_nudge_load()

# ── Broadcast campaigns ────────────────────────────────────────────────────────
BROADCAST_HISTORY: List[Dict[str, Any]] = []   # kept in memory; survives restart via DB
_broadcast_lock = asyncio.Lock()
_broadcast_running: Dict[str, Any] = {}        # at most one live campaign at a time

BROADCAST_SEGMENTS: Dict[str, str] = {
    "inactive_3_7d":    "Lapsed 3–7 days, ≥3 gens, 0 purchases",
    "inactive_7_14d":   "Lapsed 7–14 days, any gens",
    "zero_purchase":    "Active ≤14 days, ≥3 gens, 0 purchases",
    "paid":             "Buyers (payments > 0)",
    "new_7d":           "New users (joined last 7 days)",
    "all_active_30d":   "All active in last 30 days",
}

def _broadcast_segment_uids(segment: str) -> List[int]:
    now = time.time()
    out: List[int] = []
    for uid, ui in STATS_USERS_INFO.items():
        if NUDGE_INFO.get(uid, {}).get("blocked"):
            continue
        last_seen  = float(ui.get("last_seen", 0))
        first_seen = float(ui.get("first_seen", 0))
        gens_ok    = int(ui.get("gens_ok", 0))
        payments   = int(ui.get("payments", 0))
        age        = now - last_seen
        if segment == "inactive_3_7d":
            if 3 * 86400 <= age <= 7 * 86400 and gens_ok >= 3 and payments == 0:
                out.append(uid)
        elif segment == "inactive_7_14d":
            if 7 * 86400 <= age <= 14 * 86400 and gens_ok >= 1:
                out.append(uid)
        elif segment == "zero_purchase":
            if age <= 14 * 86400 and gens_ok >= 3 and payments == 0:
                out.append(uid)
        elif segment == "paid":
            if payments > 0:
                out.append(uid)
        elif segment == "new_7d":
            if first_seen > 0 and now - first_seen <= 7 * 86400:
                out.append(uid)
        elif segment == "all_active_30d":
            if age <= 30 * 86400:
                out.append(uid)
    return out

async def run_broadcast_job(campaign_id: str, uids: List[int], message: str, deep_link: str):
    global _broadcast_running
    sent = failed = blocked_count = 0
    total = len(uids)
    entry = {
        "campaign_id": campaign_id,
        "total": total,
        "sent": 0,
        "failed": 0,
        "blocked": 0,
        "status": "running",
        "started_at": time.time(),
        "finished_at": None,
    }
    BROADCAST_HISTORY.insert(0, entry)
    _broadcast_running = entry

    try:
        for uid in uids:
            if not _broadcast_running.get("status") == "running":
                break
            try:
                text = message
                if deep_link:
                    text += f"\n\n{deep_link}"
                await bot.send_message(uid, text)
                analytics_event(uid, "broadcast_sent", {"campaign_id": campaign_id})
                sent += 1
            except (TelegramForbiddenError, TelegramNotFound):
                NUDGE_INFO.setdefault(uid, {})["blocked"] = True
                blocked_count += 1
            except Exception:
                failed += 1
            entry["sent"] = sent
            entry["failed"] = failed
            entry["blocked"] = blocked_count
            await asyncio.sleep(NUDGE_SEND_DELAY)
    finally:
        entry["status"] = "done"
        entry["finished_at"] = time.time()
        _broadcast_running = {}
        stats_incr("broadcasts_sent", sent)
        print(f"[broadcast] {campaign_id} done: sent={sent} failed={failed} blocked={blocked_count}/{total}")

def _nudge_eligible(uid: int) -> bool:
    now = time.time()
    ui = STATS_USERS_INFO.get(uid) or {}
    last_seen = float(ui.get("last_seen", 0))
    if last_seen <= 0:
        return False
    # User was active recently — not lapsed
    if now - last_seen < NUDGE_INTERVAL_HOURS * 3600:
        return False
    ni = NUDGE_INFO.get(uid) or {}
    # Skip permanently blocked users
    if ni.get("blocked"):
        return False
    # Lifetime cap
    total = int(ni.get("count", 0))
    if total >= NUDGE_MAX_TOTAL:
        return False
    # Minimum gap since last nudge (per-user via experiment)
    last_sent = float(ni.get("last_sent", 0))
    gap_hours = nudge_interval_hours(uid)  # 24h or 48h via experiment
    if last_sent and now - last_sent < gap_hours * 3600:
        return False
    # Weekly cap: count sends in last 7 days
    sent_timestamps = ni.get("sent_timestamps") or []
    week_ago = now - 7 * 24 * 3600
    recent_week = [t for t in sent_timestamps if float(t) > week_ago]
    if len(recent_week) >= NUDGE_WEEKLY_CAP:
        return False
    return True

def _nudge_pick_segment(uid: int) -> str:
    """
    Segment users into 5 nudge types based on behavior:
      LAPSE_CREDITS    — has credits, been away 24-72h
      PREMIUM_UPSELL   — generated with everyday only, never tried a paid mode
      RETURNING_PAID   — previous payer, came back
      LAPSE_NOCREDITS  — 0 credits, inactive (give free credit)
      VIRAL_SHARE      — generated but probably never shared (no share event)
    """
    ui = STATS_USERS_INFO.get(uid) or {}
    now = time.time()
    last_seen = float(ui.get("last_seen", 0))
    hours_away = (now - last_seen) / 3600 if last_seen else 9999
    gens_ok = int(ui.get("gens_ok", 0))
    paid = int(ui.get("payments", 0)) > 0
    credits_left = USER_CREDITS.get(uid, 0)
    ni = NUDGE_INFO.get(uid) or {}
    nudge_count = int(ni.get("count", 0))

    if paid and hours_away > 48:
        return "RETURNING_PAID"
    if gens_ok >= 2 and credits_left >= 3 and hours_away < 72:
        # Has tried the bot, has credits, just drifted away — upsell premium mode
        return "PREMIUM_UPSELL"
    if credits_left > 0 and hours_away >= 24:
        return "LAPSE_CREDITS"
    if gens_ok >= 1 and nudge_count == 0:
        # Generated before, never nudged → viral share
        return "VIRAL_SHARE"
    return "LAPSE_NOCREDITS"

def _nudge_pick_offer(uid: int) -> Dict[str, object]:
    segment = _nudge_pick_segment(uid)
    credits_left = USER_CREDITS.get(uid, 0)
    return {"kind": segment, "credits_left": credits_left}

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

_NUDGE_COPY: Dict[str, Dict[str, list]] = {
    "LAPSE_CREDITS": {
        "ru": [
            "У вас ещё {n} генераций в запасе ✨ Пора создать новый образ!",
            "Ваши {n} генераций ждут — отправьте селфи и посмотрите результат.",
            "Не дайте кредитам пропасть! {n} генераций уже на балансе — попробуйте Vogue Mode 👑",
        ],
        "en": [
            "You still have {n} credits waiting ✨ Time to create a new look!",
            "Your {n} generations are sitting unused — drop a selfie and see the magic.",
            "Don't waste your credits! {n} left — try Vogue Mode for a stunning result 👑",
        ],
        "ro": ["Mai ai {n} credite disponibile ✨ E timpul pentru un nou look!", "Creditele tale ({n}) te așteaptă — trimite un selfie acum."],
        "de": ["Du hast noch {n} Credits ✨ Zeit für einen neuen Look!", "Deine {n} Generierungen warten — schick ein Selfie!"],
    },
    "PREMIUM_UPSELL": {
        "ru": [
            "👑 Vogue Mode: 8 AI-генераций, лучшие 3 + 4× апскейл. Результат как с обложки журнала. Попробуйте прямо сейчас!",
            "🤵 CEO Mode даёт 6 генераций + LinkedIn-портрет. Идеально для профиля. Всего 4 кредита.",
            "✨ Luxury Mode: ultra-luxury editorial, 6 генераций, лучшие 2 с апскейлом. Ваш Instagram оценит.",
        ],
        "en": [
            "👑 Vogue Mode: 8 AI shots, best 3 selected + 4× upscale. Magazine-cover quality. Try it now!",
            "🤵 CEO Mode: 6 generations → professional LinkedIn portrait. Just 4 credits.",
            "✨ Luxury Mode: ultra-luxury editorial, 6 shots, best 2 upscaled. Your Instagram will thank you.",
        ],
        "ro": ["👑 Modul Vogue: 8 fotografii AI, cele mai bune 3 + upscale 4×. Calitate de copertă!", "🤵 CEO Mode: 6 generații → portret profesional. Doar 4 credite."],
        "de": ["👑 Vogue Mode: 8 KI-Fotos, beste 3 + 4× Upscale. Magazin-Qualität!", "🤵 CEO Mode: 6 Generierungen → professionelles LinkedIn-Porträt. Nur 4 Credits."],
    },
    "RETURNING_PAID": {
        "ru": ["Соскучились? Держите промокод на +3 генерации: {code} — только для вас 🎁"],
        "en": ["Missed you! Here's a promo for +3 free generations: {code} — just for you 🎁"],
        "ro": ["Ne-a fost dor! Cod promo pentru +3 generații: {code} 🎁"],
        "de": ["Vermisst! Promo-Code für +3 Generierungen: {code} — nur für dich 🎁"],
    },
    "VIRAL_SHARE": {
        "ru": [
            "Понравился результат? Поделитесь в Историях — друзья точно захотят попробовать 📤",
            "Ваши AI-фото достойны Stories 🌟 Поделитесь и получите реакции!",
        ],
        "en": [
            "Loved your result? Share it to Stories — your friends will want to try too 📤",
            "Your AI photos deserve to be seen 🌟 Share and watch the reactions!",
        ],
        "ro": ["Ți-a plăcut rezultatul? Distribuie în Stories — prietenii vor vrea și ei 📤"],
        "de": ["Ergebnis gefallen? Teile es in Stories — deine Freunde werden es auch wollen 📤"],
    },
    "LAPSE_NOCREDITS": {
        "ru": ["Дарим +1 генерацию — возвращайтесь и создайте новый образ прямо сейчас! 🎁"],
        "en": ["We're giving you +1 free generation — come back and create something amazing! 🎁"],
        "ro": ["Îți oferim +1 generație gratuită — revino și creează ceva nou! 🎁"],
        "de": ["Wir schenken dir +1 Generierung — komm zurück und erstelle etwas Tolles! 🎁"],
    },
}

def _pick_nudge_text(segment: str, lang: str, **fmt) -> str:
    pool = _NUDGE_COPY.get(segment, {})
    msgs = pool.get(lang) or pool.get("en") or ["Come back to iModel ✨"]
    text = random.choice(msgs)
    try:
        return text.format(**fmt)
    except KeyError:
        return text

def _nudge_keyboard(uid: int) -> Optional[InlineKeyboardMarkup]:
    rows = []
    if WEBHOOK_BASE:
        rows.append([InlineKeyboardButton(
            text="📸 Open Studio",
            web_app=WebAppInfo(url=f"{WEBHOOK_BASE}/webapp"),
        )])
    elif BOT_USERNAME_GLOBAL:
        rows.append([InlineKeyboardButton(
            text="📸 Open Studio",
            url=f"https://t.me/{BOT_USERNAME_GLOBAL}",
        )])
    credits_left = USER_CREDITS.get(uid, 0)
    if credits_left <= 2:
        rows.append([InlineKeyboardButton(text="⚡ Buy Credits", callback_data="buy_stars_30")])
    if not rows:
        return None
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def _send_nudge(uid: int, lang: str):
    ni = NUDGE_INFO.setdefault(uid, {})
    offer = _nudge_pick_offer(uid)
    segment = str(offer["kind"])
    credits_left = int(offer.get("credits_left", 0))
    promo_code = None
    granted = 0

    if segment == "LAPSE_NOCREDITS":
        async with _credits_lock:
            USER_CREDITS[uid] = USER_CREDITS.get(uid, 0) + 1
        _credits_save()
        granted = 1
        text = _pick_nudge_text(segment, lang)
    elif segment == "RETURNING_PAID":
        promo_code = _create_user_promo(uid, add=3, ttl_uses=1)
        text = _pick_nudge_text(segment, lang, code=promo_code)
    elif segment == "LAPSE_CREDITS":
        text = _pick_nudge_text(segment, lang, n=credits_left)
    else:
        text = _pick_nudge_text(segment, lang)

    kb = _nudge_keyboard(uid)
    try:
        sent = await bot.send_message(uid, text, reply_markup=kb)
    except (TelegramForbiddenError, TelegramNotFound):
        # User blocked the bot — mark permanently and stop retrying
        ni["blocked"] = True
        ni["blocked_at"] = time.time()
        _nudge_save()
        stats_incr("nudges_blocked", 1)
        return
    except Exception:
        stats_incr("nudges_errors", 1)
        return
    if sent:
        now = time.time()
        ni["last_sent"] = now
        ni["count"] = int(ni.get("count", 0)) + 1
        ni["last_segment"] = segment
        # Keep rolling 7-day timestamp list (trim old entries)
        stamps: list = list(ni.get("sent_timestamps") or [])
        stamps.append(now)
        week_ago = now - 7 * 24 * 3600
        ni["sent_timestamps"] = [t for t in stamps if float(t) > week_ago]
        _nudge_save()
        analytics_event(uid, "nudge_sent", {
            "segment": segment, "granted": granted,
            "variant_nudge_interval": get_variant(uid, "nudge_interval"),
        })
        stats_incr("nudges_sent", 1)
        stats_incr(f"nudge_{segment.lower()}", 1)
        if granted:
            stats_incr("nudges_granted", 1)

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
            # Prune JOBS older than 48h that are no longer running
            job_cutoff = now - 48 * 3600
            stale_jobs = [
                jid for jid, j in list(JOBS.items())
                if j.get("status") not in ("running", "queued")
                and j.get("created_at", now) < job_cutoff
            ]
            for jid in stale_jobs:
                JOBS.pop(jid, None)
            if stale_jobs:
                print(f"[cleanup] pruned {len(stale_jobs)} old jobs from memory")
        except Exception as e:
            print("[cleanup] error:", str(e)[:160])
        await asyncio.sleep(3600)

async def streak_reminder_loop():
    """Check every 30 min; remind users whose streak will expire if they don't generate today."""
    await asyncio.sleep(60)
    while True:
        try:
            now = time.time()
            sent = 0
            for uid, streak in list(USER_STREAK.items()):
                if streak <= 0:
                    continue
                if NUDGE_INFO.get(uid, {}).get("blocked"):
                    continue
                last_bonus = USER_LAST_BONUS.get(uid, 0)
                hours_since = (now - last_bonus) / 3600
                # Window: 20-47h since last bonus (streak expires at 48h)
                if hours_since < 20 or hours_since >= 47:
                    continue
                # Only send once per day: skip if reminded in the last 20h
                last_reminded = USER_STREAK_REMINDED.get(uid, 0)
                if now - last_reminded < 20 * 3600:
                    continue
                lang = USER_LANG.get(uid, LANG_DEFAULT)
                if not _nudge_allowed_now(lang):
                    continue
                _msgs: Dict[str, str] = {
                    "ru": f"🔥 Ваш стрик {streak} дней под угрозой! Сделайте фото сегодня, чтобы не потерять.",
                    "en": f"🔥 Your {streak}-day streak is at risk! Generate a photo today to keep it.",
                    "ro": f"🔥 Seria ta de {streak} zile e în pericol! Generează o poză azi ca s-o păstrezi.",
                    "de": f"🔥 Dein {streak}-Tage-Streak ist in Gefahr! Erstelle heute ein Foto, um ihn zu bewahren.",
                    "ar": f"🔥 سلسلة {streak} يوم في خطر! أنشئ صورة اليوم للحفاظ عليها.",
                }
                text = _msgs.get(lang, _msgs["en"])
                webapp_url = f"{WEBHOOK_BASE}/webapp"
                markup = InlineKeyboardMarkup(inline_keyboard=[[
                    InlineKeyboardButton(text="📸 Generate now", web_app=WebAppInfo(url=webapp_url)),
                ]])
                try:
                    await bot.send_message(uid, text, reply_markup=markup)
                    USER_STREAK_REMINDED[uid] = now
                    analytics_event(uid, "streak_reminder_sent", {"streak": streak, "hours_since": round(hours_since, 1)})
                    sent += 1
                    if NUDGE_SEND_DELAY > 0:
                        await asyncio.sleep(NUDGE_SEND_DELAY)
                except (TelegramForbiddenError, TelegramNotFound):
                    NUDGE_INFO.setdefault(uid, {})["blocked"] = True
                except Exception:
                    pass
            if sent:
                print(f"[streak_reminder_loop] sent {sent} reminders")
        except Exception as e:
            print("streak_reminder_loop error:", str(e)[:200])
        await asyncio.sleep(1800)


async def quest_reminder_loop():
    """At 19-22 UTC each day, remind users with incomplete daily quests or claimable rewards."""
    import datetime as _dt
    await asyncio.sleep(180)
    while True:
        try:
            now = time.time()
            utc_hour = _dt.datetime.utcnow().hour
            if 19 <= utc_hour < 22:
                today = _dt.date.today().isoformat()
                sent = 0
                for uid in list(STATS_USERS_INFO.keys()):
                    if NUDGE_INFO.get(uid, {}).get("blocked"):
                        continue
                    last_reminded = USER_QUEST_REMINDED.get(uid, 0)
                    if now - last_reminded < 20 * 3600:
                        continue
                    lang = USER_LANG.get(uid, LANG_DEFAULT)
                    if not _nudge_allowed_now(lang):
                        continue
                    quests = _quest_progress_for_user(uid, today)
                    claimable = [q for q in quests if q["type"] == "daily" and q["claimable"]]
                    incomplete = [q for q in quests if q["type"] == "daily" and not q["claimed"] and not q["claimable"]]
                    if not claimable and not incomplete:
                        continue
                    if claimable:
                        n = len(claimable)
                        _msgs: Dict[str, str] = {
                            "ru": f"✨ {'Задание выполнено' if n == 1 else f'{n} задания выполнены'}! Заберите кредиты до полуночи.",
                            "en": f"✨ Quest reward{'s' if n > 1 else ''} ready to claim! Don't let them expire at midnight.",
                            "ro": f"✨ {'Recompensă de misiune gata' if n == 1 else f'{n} recompense gata'}! Revendică înainte de miezul nopții.",
                            "de": f"✨ {'Quest-Belohnung bereit' if n == 1 else f'{n} Quest-Belohnungen bereit'}! Hol sie vor Mitternacht.",
                            "ar": f"✨ {'مكافأة مهمة جاهزة' if n == 1 else f'{n} مكافآت جاهزة'}! احصل عليها قبل منتصف الليل.",
                        }
                    else:
                        _msgs = {
                            "ru": "⚡ Дневные задания сбрасываются в полночь! Успейте заработать награды.",
                            "en": "⚡ Daily quests reset at midnight! Complete them now for bonus credits.",
                            "ro": "⚡ Misiunile zilnice se resetează la miezul nopții! Completează-le acum.",
                            "de": "⚡ Tägliche Quests werden um Mitternacht zurückgesetzt! Erledige sie jetzt.",
                            "ar": "⚡ تتجدد المهام اليومية عند منتصف الليل! أكملها الآن.",
                        }
                    text = _msgs.get(lang, _msgs["en"])
                    webapp_url = f"{WEBHOOK_BASE}/webapp"
                    markup = InlineKeyboardMarkup(inline_keyboard=[[
                        InlineKeyboardButton(text="🎯 Open quests", web_app=WebAppInfo(url=webapp_url)),
                    ]])
                    try:
                        await bot.send_message(uid, text, reply_markup=markup)
                        USER_QUEST_REMINDED[uid] = now
                        analytics_event(uid, "quest_reminder_sent", {"claimable": len(claimable), "incomplete": len(incomplete)})
                        sent += 1
                        if NUDGE_SEND_DELAY > 0:
                            await asyncio.sleep(NUDGE_SEND_DELAY)
                    except (TelegramForbiddenError, TelegramNotFound):
                        NUDGE_INFO.setdefault(uid, {})["blocked"] = True
                    except Exception:
                        pass
                if sent:
                    print(f"[quest_reminder_loop] sent {sent} quest reminders")
        except Exception as e:
            print("quest_reminder_loop error:", str(e)[:200])
        await asyncio.sleep(1800)


async def nudge_loop():
    # Run hourly; send up to NUDGE_BATCH_LIMIT eligible nudges
    await asyncio.sleep(5)
    while True:
        try:
            if NUDGE_ENABLED and STATS_USERS_INFO:
                eligible = [uid for uid in list(STATS_USERS_INFO.keys()) if _nudge_eligible(uid)]
                random.shuffle(eligible)
                sent_count = 0
                for uid in eligible:
                    if sent_count >= NUDGE_BATCH_LIMIT:
                        break
                    lang = USER_LANG.get(uid, LANG_DEFAULT)
                    if not _nudge_allowed_now(lang):
                        continue
                    await _send_nudge(uid, lang)
                    sent_count += 1
                    if NUDGE_SEND_DELAY > 0:
                        await asyncio.sleep(NUDGE_SEND_DELAY)
                if sent_count:
                    print(f"[nudge_loop] sent {sent_count} nudges (eligible={len(eligible)})")
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

    latency_ms = int((time.time() - t0) * 1000)
    stats_incr("generation_latency_total_ms", latency_ms)
    stats_incr("generation_latency_count", 1)
    record_job(job_id, status="generated")
    job_event(job_id, "generation_done", latency_ms=latency_ms, output_bytes=len(nano_bytes))
    # Professional face retouch: CodeFormer (fidelity=0.8 → subtle, identity-preserving)
    # falls back to GFPGAN, then original on any error
    nano_bytes = enhance_face_codeformer(nano_bytes, fidelity=0.8)
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
    from urllib.parse import quote as _q
    lang = L(chat_id)
    user_lang = USER_LANG.get(chat_id, LANG_DEFAULT)
    share_text = {
        "ru": "Посмотри, что AI сделал из моего селфи! 🤩",
        "en": "Look what AI made from my selfie! 🤩",
        "ro": "Uită-te ce a făcut AI din selfie-ul meu! 🤩",
        "de": "Schau, was KI aus meinem Selfie gemacht hat! 🤩",
        "ar": "انظر ما صنعه الذكاء الاصطناعي من صورتي! 🤩",
    }.get(user_lang, "Look what AI made from my selfie! 🤩")
    bot_url = f"https://t.me/{BOT_USERNAME_GLOBAL}" if BOT_USERNAME_GLOBAL else "https://t.me/imodelapp_bot"
    output_url = USER_LAST_OUTPUT_URL.get(chat_id)
    if output_url:
        share_url = f"https://t.me/share/url?url={_q(output_url)}&text={_q(share_text + ' → ' + bot_url)}"
    else:
        share_url = f"https://t.me/share/url?url={_q(bot_url)}&text={_q(share_text)}"
    rows = [
        [
            InlineKeyboardButton(text="📤 " + lang.get("btn_share", "Share"),         url=share_url),
            InlineKeyboardButton(text="🔄 " + lang.get("btn_more", "More"),           callback_data="more"),
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
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=lang.get("buy_btn_10", "✨ 10 gens — 200★"), callback_data="buy_stars_10"),
             InlineKeyboardButton(text=lang.get("buy_btn_30", "⚡ 30 gens — 500★"), callback_data="buy_stars_30")],
        ])
        try:
            await m.answer(txt, reply_markup=kb)
        except Exception:
            pass
    elif n <= 3:
        gen_word = _pluralize_ru(n, lang)
        txt = lang.get("credits_low", "🔋 Remaining: {n} {gen}").format(n=n, gen=gen_word)
        try:
            await m.answer(txt)
        except Exception:
            pass

def _smart_paywall_text(uid: int) -> str:
    """Return segment-aware paywall copy."""
    ui = STATS_USERS_INFO.get(uid) or {}
    payments = int(ui.get("payments", 0))
    gens_ok = int(ui.get("gens_ok", 0)) + int(ui.get("gens_copy_ok", 0))
    lang = L(uid)
    if payments > 0:
        return lang.get("credits_none_paid", lang["credits_none"])
    if gens_ok >= 3:
        return lang.get("credits_none_active", lang["credits_none"])
    return lang.get("credits_none_first", lang["credits_none"])

def kb_invite_buy(chat_id: int) -> InlineKeyboardMarkup:
    lang = L(chat_id)
    invite_text = lang.get("btn_invite", "👥 Invite a friend (+{n} free)").format(n=REF_BONUS_REF)
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=lang.get("btn_sub", "📅 Subscription"), callback_data="sub_open")],
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

async def send_subscription_invoice(chat_id: int, plan: str):
    lang = L(chat_id)
    if plan == "pro":
        title = "iModel Pro"
        desc = lang.get("sub_pro_btn", f"Pro — {SUB_PRO_STARS}★/мес · {SUB_PRO_CREDITS} ген")
        payload = "sub_pro"
        stars = SUB_PRO_STARS
    else:
        title = "iModel Elite"
        desc = lang.get("sub_elite_btn", f"Elite — {SUB_ELITE_STARS}★/мес · {SUB_ELITE_CREDITS} ген")
        payload = "sub_elite"
        stars = SUB_ELITE_STARS
    prices = [LabeledPrice(label=title, amount=stars)]
    await bot.send_invoice(
        chat_id=chat_id,
        title=title,
        description=desc,
        payload=payload,
        provider_token="",
        currency="XTR",
        prices=prices,
        subscription_period=SUB_PERIOD,
    )

@dp.message(Command("buy"))
async def cmd_buy(m: Message):
    lang = L(m.chat.id)
    uid = m.chat.id
    n = USER_CREDITS.get(uid, FREE_QUOTA)
    invite_text = lang.get("btn_invite", "👥 Invite a friend (+{n} free)").format(n=REF_BONUS_REF)
    sub = get_active_sub(uid)
    sub_btn_text = lang.get("btn_sub", "📅 Subscription")
    if sub:
        import datetime
        exp_str = datetime.datetime.fromtimestamp(sub["expires"]).strftime("%d.%m.%Y")
        sub_btn_text = lang.get("sub_active", "📅 {plan} — active until {date}").format(plan=sub["plan"].capitalize(), date=exp_str)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=sub_btn_text, callback_data="sub_open")],
        [InlineKeyboardButton(text=lang["buy_btn_10"],  callback_data="buy_stars_10")],
        [InlineKeyboardButton(text=lang["buy_btn_30"],  callback_data="buy_stars_30")],
        [InlineKeyboardButton(text=lang["buy_btn_100"], callback_data="buy_stars_100")],
        [InlineKeyboardButton(text=lang.get("buy_btn_300", "💎 300 gens — 2500★"), callback_data="buy_stars_300")],
        [InlineKeyboardButton(text=invite_text, callback_data="refer_open")],
    ])
    balance_line = f"\n\n🔋 Баланс: {n} ген." if not is_free_user(uid, getattr(m.from_user, "username", None)) else ""
    await safe_answer(m, lang["buy_title"] + balance_line, reply_markup=kb)

@dp.callback_query(F.data.startswith("buy_stars_"))
async def cb_buy_stars(c: CallbackQuery):
    pack = c.data.split("_")[-1]
    # subtle referral tooltip
    txt = L(c.message.chat.id).get("hint_refer_pay", "Invite a friend for free credits").format(ref_new=REF_BONUS_NEW, ref_ref=REF_BONUS_REF)
    if pack == "10":
        await send_stars_invoice(c.message.chat.id, "iModel — 10 фото", "10 профессиональных фото", "pack_10", 199)
    elif pack == "30":
        await send_stars_invoice(c.message.chat.id, "iModel — 30 фото", "30 профессиональных фото (−18%)", "pack_30", 490)
    elif pack == "100":
        await send_stars_invoice(c.message.chat.id, "iModel — 100 фото", "100 профессиональных фото (−35%)", "pack_100", 1290)
    elif pack == "300":
        await send_stars_invoice(c.message.chat.id, "iModel — 300 фото", "300 профессиональных фото (−50%)", "pack_300", 2990)
    await safe_cb_answer(c, txt)

@dp.callback_query(F.data == "sub_open")
async def cb_sub_open(c: CallbackQuery):
    lang = L(c.message.chat.id)
    uid = c.message.chat.id
    sub = get_active_sub(uid)
    text = lang.get("sub_title", "📅 iModel Subscription\n\nAuto-renews monthly.")
    if sub:
        import datetime
        exp_str = datetime.datetime.fromtimestamp(sub["expires"]).strftime("%d.%m.%Y")
        active_line = "\n\n" + lang.get("sub_active", "📅 {plan} — active until {date}").format(
            plan=sub["plan"].capitalize(), date=exp_str
        )
        text += active_line
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=lang.get("sub_pro_btn",   f"⚡ Pro — {SUB_PRO_STARS}★/мес"),   callback_data="sub_buy_pro")],
        [InlineKeyboardButton(text=lang.get("sub_elite_btn", f"💎 Elite — {SUB_ELITE_STARS}★/мес"), callback_data="sub_buy_elite")],
    ])
    await safe_cb_answer(c)
    try:
        await c.message.answer(text, reply_markup=kb, parse_mode="Markdown")
    except Exception:
        await c.message.answer(text, reply_markup=kb)

@dp.callback_query(F.data.startswith("sub_buy_"))
async def cb_sub_plan(c: CallbackQuery):
    plan = c.data.split("_")[-1]  # "pro" or "elite"
    await safe_cb_answer(c)
    try:
        await send_subscription_invoice(c.message.chat.id, plan)
    except Exception as e:
        print(f"[sub invoice] error: {e}")
        await c.message.answer("⚠️ Ошибка создания подписки. Попробуйте позже.")

@dp.pre_checkout_query()
async def process_pre_checkout_q(pcq: PreCheckoutQuery):
    known = _build_payment_sku_map()
    payload = str(pcq.invoice_payload or "")
    expected_stars = known.get(payload)
    if (
        not expected_stars
        or pcq.currency != "XTR"
        or pcq.total_amount != expected_stars
    ):
        log_event("pre_checkout_rejected", uid=pcq.from_user.id,
                  payload=payload, amount=pcq.total_amount)
        await bot.answer_pre_checkout_query(pcq.id, ok=False,
                                             error_message="Invalid order. Please restart the purchase.")
        return
    await bot.answer_pre_checkout_query(pcq.id, ok=True)

@dp.message(F.successful_payment)
async def got_payment(m: Message):
    import datetime
    payload = m.successful_payment.invoice_payload
    uid = m.chat.id
    lang = L(uid)
    add = 0
    _touch_user(uid, getattr(m.from_user, "username", None))

    # Idempotency: skip if this charge was already processed
    charge_id = str(getattr(m.successful_payment, "telegram_payment_charge_id", "") or "")
    if charge_id and _db_is_payment_processed(charge_id):
        log_event("payment_duplicate_skipped", uid=uid, charge_id=charge_id, payload=payload)
        return

    is_sub = payload in ("sub_pro", "sub_elite", "sub_weekly", "sub_creator")
    if is_sub:
        if payload == "sub_weekly":
            plan, credits_per_month, period = "weekly", SUB_WEEKLY_CREDITS, SUB_WEEKLY_PERIOD
        elif payload == "sub_pro":
            plan, credits_per_month, period = "pro", SUB_PRO_CREDITS, SUB_PERIOD
        elif payload == "sub_creator":
            plan, credits_per_month, period = "creator", SUB_CREATOR_CREDITS, SUB_PERIOD
        else:
            plan, credits_per_month, period = "elite", SUB_ELITE_CREDITS, SUB_PERIOD
        add = credits_per_month
        USER_SUBSCRIPTION[uid] = {
            "plan": plan,
            "expires": time.time() + period + 3600,  # +1h buffer
            "credits_per_month": credits_per_month,
        }
        _subs_save()
        async with _credits_lock:
            USER_CREDITS[uid] = USER_CREDITS.get(uid, 0) + add
        _credits_save()
        is_first = True
        try:
            is_first = bool(getattr(m.successful_payment, "is_first_recurring", True))
        except Exception:
            pass
        msg_key = "sub_bought" if is_first else "sub_renewed"
        await safe_answer(m, lang.get(msg_key, "✅ Подписка активна! +{add} ген.").format(
            plan=plan.capitalize(), add=add, all=USER_CREDITS[uid]
        ))
    elif payload == "premium_pack_1":
        USER_STYLE_PACKS.setdefault(uid, set()).add("premium_pack_1")
        _style_packs_save()
        await safe_answer(m, "✅ Premium Style Pack разблокирован! 15 эксклюзивных стилей доступны в iModel Studio.")
    elif payload == "age_pack":
        USER_AGE_PACKS[uid] = True
        _style_packs_save()
        await safe_answer(m, "✅ Age Magic Pack разблокирован! 4 стиля трансформации возраста доступны.")
    elif payload in PRESET_PACKS:
        USER_STYLE_PACKS.setdefault(uid, set()).add(payload)
        _style_packs_save()
        pack = PRESET_PACKS[payload]
        count = len(pack["presets"])
        name = pack["label_en"]
        await safe_answer(m, f"✅ {name} unlocked! {count} new presets available in iModel Studio.")
    else:
        if payload == "pack_10": add = 10
        elif payload == "pack_30": add = 30
        elif payload == "pack_100": add = 100
        elif payload == "pack_300": add = 300
        async with _credits_lock:
            USER_CREDITS[uid] = USER_CREDITS.get(uid, 0) + add
        _credits_save()
        await safe_answer(m, lang["bought"].format(add=add, all=USER_CREDITS[uid]))

    if charge_id:
        _db_mark_payment_processed(charge_id, uid, payload)

    stats_incr("payments", 1)
    _uadd(uid, "payments", 1)
    try:
        uname = getattr(m.from_user, "username", None)
        name = getattr(m.from_user, "full_name", None) or getattr(m.from_user, "first_name", "")
        xtr = None
        try:
            xtr = int(getattr(m.successful_payment, "total_amount", 0))
        except Exception:
            xtr = None
        await notify_admins_payment(
            user_id=uid,
            username=("@" + uname) if uname else None,
            name=name,
            pack=payload,
            gens=add,
            balance=USER_CREDITS.get(uid, 0),
            stars=xtr,
        )
        analytics_event(uid, "purchase_completed", {"pack": payload, "credits_added": add, "stars": xtr, "source": "telegram_stars"})
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

@dp.message(Command("nudgestats"))
async def cmd_nudgestats(m: Message):
    if m.chat.id not in ADMIN_IDS:
        return
    now = time.time()
    total_users = len(STATS_USERS_INFO)
    eligible = sum(1 for uid in STATS_USERS_INFO if _nudge_eligible(uid))
    blocked = sum(1 for ni in NUDGE_INFO.values() if ni.get("blocked"))
    total_sent = sum(int(ni.get("count", 0)) for ni in NUDGE_INFO.values())
    capped_total = sum(1 for ni in NUDGE_INFO.values() if int(ni.get("count", 0)) >= NUDGE_MAX_TOTAL)
    week_ago = now - 7 * 24 * 3600
    capped_weekly = sum(
        1 for ni in NUDGE_INFO.values()
        if len([t for t in (ni.get("sent_timestamps") or []) if float(t) > week_ago]) >= NUDGE_WEEKLY_CAP
    )
    lines = [
        f"🔔 Nudge stats",
        f"Enabled: {NUDGE_ENABLED}",
        f"Total users: {total_users}",
        f"Eligible now: {eligible}",
        f"Blocked (bot): {blocked}",
        f"Total nudges sent: {total_sent}",
        f"Lifetime capped: {capped_total} (max {NUDGE_MAX_TOTAL})",
        f"Weekly capped: {capped_weekly} (max {NUDGE_WEEKLY_CAP}/7d)",
        f"Batch limit: {NUDGE_BATCH_LIMIT}/hr",
        f"Gap: {NUDGE_MIN_GAP_HOURS}h | Window: {NUDGE_DAY_START_HOUR}-{NUDGE_DAY_END_HOUR}",
    ]
    await safe_answer(m, "\n".join(lines))

@dp.message(Command("nudge_test"))
async def cmd_nudge_test(m: Message):
    """Admin: fire a test nudge to yourself."""
    if m.chat.id not in ADMIN_IDS:
        return
    lang = USER_LANG.get(m.chat.id, LANG_DEFAULT)
    await _send_nudge(m.chat.id, lang)
    await safe_answer(m, "✅ Test nudge sent (check above)")

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
                async with _credits_lock:
                    USER_CREDITS[invited_id] += REF_BONUS_NEW
                _credits_save()
                REF_STATS.setdefault(ref_id, {"count": 0, "earned": 0})
                REF_STATS[ref_id]["count"] += 1
                REF_STATS[ref_id]["earned"] += REF_BONUS_REF
                # Sync referrals_sent so invite_1 quest/achievement can read it
                STATS_USERS_INFO.setdefault(ref_id, {})["referrals_sent"] = REF_STATS[ref_id]["count"]
                async with _credits_lock:
                    USER_CREDITS[ref_id] = USER_CREDITS.get(ref_id, FREE_QUOTA) + REF_BONUS_REF
                _credits_save()
                _ref_save()
                _check_and_unlock_achievements(ref_id)
                stats_incr("referrals", 1)
                stats_incr("ref_bonus_ref", REF_BONUS_REF)
                stats_incr("ref_bonus_invited", REF_BONUS_NEW)
                analytics_event(invited_id, "referral_joined", {"ref_id": ref_id})
                new_count = REF_STATS[ref_id]["count"]
                # Notify referrer
                ref_lang = USER_LANG.get(ref_id, LANG_DEFAULT)
                notif = {
                    "ru": f"🎉 По вашей ссылке зарегистрировался новый друг! +{REF_BONUS_REF} кредита. Всего приглашено: {new_count}",
                    "en": f"🎉 Someone joined via your link! +{REF_BONUS_REF} credits added. Total invited: {new_count}",
                    "ro": f"🎉 Cineva s-a alăturat prin linkul tău! +{REF_BONUS_REF} credite. Total invitați: {new_count}",
                    "de": f"🎉 Jemand ist über deinen Link beigetreten! +{REF_BONUS_REF} Credits. Eingeladen gesamt: {new_count}",
                    "ar": f"🎉 انضم شخص عبر رابطك! +{REF_BONUS_REF} رصيد. إجمالي المدعوين: {new_count}",
                }.get(ref_lang, f"🎉 Someone joined via your link! +{REF_BONUS_REF} credits. Total: {new_count}")
                try:
                    await bot.send_message(ref_id, notif)
                except Exception:
                    pass
                # Milestone bonus (fire-and-forget)
                asyncio.create_task(_maybe_give_milestone_bonus(ref_id, new_count))
        except Exception:
            pass

    # Deep-link: start=bc_<campaign_id> → broadcast attribution
    if len(parts) > 1 and parts[1].startswith("bc_"):
        campaign_id = parts[1]
        analytics_event(m.chat.id, "broadcast_opened", {"campaign_id": campaign_id})

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

    # Deep-link: start=gift_XXXXXXXX → claim gift credits
    if len(parts) > 1 and parts[1].startswith("gift_"):
        code = parts[1].strip()
        gift = GIFT_CODES.get(code)
        recipient_uid = m.chat.id
        _glang = USER_LANG.get(recipient_uid, LANG_DEFAULT)
        if not gift:
            pass  # silently ignore unknown codes
        elif gift.get("claimed"):
            _already: Dict[str, str] = {
                "ru": "🎁 Эта подарочная ссылка уже была использована.",
                "en": "🎁 This gift link has already been claimed.",
                "ro": "🎁 Acest link cadou a fost deja folosit.",
                "de": "🎁 Dieser Geschenklink wurde bereits eingelöst.",
                "ar": "🎁 تم استخدام رابط الهدية هذا بالفعل.",
            }
            await safe_answer(m, _already.get(_glang, _already["en"]))
        elif gift["from_uid"] == recipient_uid:
            _selfgift: Dict[str, str] = {
                "ru": "🎁 Нельзя воспользоваться собственным подарком.",
                "en": "🎁 You can't claim your own gift.",
                "ro": "🎁 Nu poți folosi propriul tău cadou.",
                "de": "🎁 Du kannst dein eigenes Geschenk nicht einlösen.",
                "ar": "🎁 لا يمكنك المطالبة بهديتك الخاصة.",
            }
            await safe_answer(m, _selfgift.get(_glang, _selfgift["en"]))
        else:
            credits = int(gift["credits"])
            ensure_user_credit(recipient_uid)
            async with _credits_lock:
                USER_CREDITS[recipient_uid] = USER_CREDITS.get(recipient_uid, 0) + credits
            _credits_save()
            GIFT_CODES[code]["claimed"] = True
            GIFT_CODES[code]["claimed_by"] = recipient_uid
            GIFT_CODES[code]["claimed_at"] = time.time()
            _gifts_save()
            analytics_event(recipient_uid, "gift_claimed", {"credits": credits, "from_uid": gift["from_uid"]})
            _claimed: Dict[str, str] = {
                "ru": f"🎁 Вы получили {credits}⚡ кредитов в подарок! Приятного использования.",
                "en": f"🎁 You received {credits}⚡ gift credits! Enjoy your photoshoots.",
                "ro": f"🎁 Ai primit {credits}⚡ credite cadou! Distracție plăcută.",
                "de": f"🎁 Du hast {credits}⚡ Geschenk-Credits erhalten! Viel Spaß.",
                "ar": f"🎁 حصلت على {credits}⚡ رصيد هدية! استمتع بالتصوير.",
            }
            await safe_answer(m, _claimed.get(_glang, _claimed["en"]))
            # Notify sender + give bonus
            from_uid = int(gift["from_uid"])
            _slang = USER_LANG.get(from_uid, LANG_DEFAULT)
            async with _credits_lock:
                USER_CREDITS[from_uid] = USER_CREDITS.get(from_uid, 0) + GIFT_SENDER_BONUS
            _credits_save()
            analytics_event(from_uid, "gift_sender_bonus", {"credits": GIFT_SENDER_BONUS, "claimed_by": recipient_uid})
            recipient_name = getattr(m.from_user, "first_name", None) or "Someone"
            _notif: Dict[str, str] = {
                "ru": f"🎁 {recipient_name} воспользовался вашим подарком! +{GIFT_SENDER_BONUS}⚡ бонус вам.",
                "en": f"🎁 {recipient_name} claimed your gift! +{GIFT_SENDER_BONUS}⚡ bonus for you.",
                "ro": f"🎁 {recipient_name} a folosit cadoul tău! +{GIFT_SENDER_BONUS}⚡ bonus pentru tine.",
                "de": f"🎁 {recipient_name} hat dein Geschenk eingelöst! +{GIFT_SENDER_BONUS}⚡ Bonus für dich.",
                "ar": f"🎁 {recipient_name} طالب بهديتك! +{GIFT_SENDER_BONUS}⚡ مكافأة لك.",
            }
            try:
                await bot.send_message(from_uid, _notif.get(_slang, _notif["en"]))
            except Exception:
                pass

    ensure_user_credit(m.chat.id)
    USER_SEEN_TEXT.discard(m.chat.id)
    if m.chat.id not in USER_ONBOARDED:
        _onb_variant = get_variant(m.chat.id, "onboarding_cta")
        analytics_event(m.chat.id, "onboarding_viewed", {"source": "bot", "variant": _onb_variant})
        lang = L(m.chat.id)
        welcome_text = lang["onboard_welcome"].format(quota=FREE_QUOTA)
        _onb_btn = (
            lang.get("onboard_btn_examples", "📸 See AI examples →")
            if _onb_variant == "see_examples"
            else lang["onboard_btn"]
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=_onb_btn, callback_data="onboard_go")],
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
    import datetime
    uid = m.chat.id
    lang = L(uid)
    free = lang["balance_free"] if is_free_user(uid, getattr(m.from_user, "username", None)) else ""
    n = USER_CREDITS.get(uid, FREE_QUOTA)
    text = lang["balance"].format(n=n, free=free)
    sub = get_active_sub(uid)
    if sub:
        exp_str = datetime.datetime.fromtimestamp(sub["expires"]).strftime("%d.%m.%Y")
        sub_line = "\n" + lang.get("sub_active", "📅 {plan} — active until {date}").format(
            plan=sub["plan"].capitalize(), date=exp_str
        )
        text += sub_line
    await safe_answer(m, text)
    if n <= 0 and not is_free_user(uid, getattr(m.from_user, "username", None)):
        lang = L(m.chat.id)
        hint = lang.get("hint_refer_zero", "Invite a friend: /refer").format(ref_new=REF_BONUS_NEW, ref_ref=REF_BONUS_REF)
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=lang.get("btn_invite", "👥 Invite"), callback_data="refer_open")],
            [InlineKeyboardButton(text="⭐ " + lang["btn_buy"], callback_data="buy_open")],
        ])
        await safe_answer(m, hint, reply_markup=kb)

@dp.message(Command("photo"))
async def cmd_photo(m: Message):
    """Show photoshoot mode picker as inline keyboard."""
    uid = m.chat.id
    lang_code = USER_LANG.get(uid, LANG_DEFAULT)
    txt_map = {
        "ru": "🎬 Выберите режим фотосессии:",
        "en": "🎬 Choose your photoshoot mode:",
        "de": "🎬 Wählen Sie Ihren Fotoshoot-Modus:",
        "ar": "🎬 اختر وضع جلسة التصوير:",
    }
    txt = txt_map.get(lang_code, txt_map["en"])
    kb = _kb_photoshoot_modes(uid)
    await safe_answer(m, txt, reply_markup=kb)


def _kb_photoshoot_modes(chat_id: int) -> InlineKeyboardMarkup:
    lang_code = USER_LANG.get(chat_id, LANG_DEFAULT)
    rows = []
    for key, cfg in PHOTOSHOOT_MODES.items():
        label = cfg["label"].get(lang_code, cfg["label"].get("en", key))
        emoji = cfg.get("emoji", "✦")
        cost = cfg["credits"]
        badge = cfg.get("badge")
        badge_str = {"popular": " 🔥", "best_quality": " 👑", "for_business": " 💼", "viral": " ✨"}.get(badge or "", "")
        rows.append([InlineKeyboardButton(
            text=f"{emoji} {label}{badge_str} · {cost}⚡",
            callback_data=f"photoshoot_mode_{key}",
        )])
    return InlineKeyboardMarkup(inline_keyboard=rows)


@dp.callback_query(F.data.startswith("photoshoot_mode_"))
async def cb_photoshoot_mode(c: CallbackQuery):
    await safe_cb_answer(c)
    chat_id = c.message.chat.id
    mode_key = c.data.split("photoshoot_mode_")[-1]
    if mode_key not in PHOTOSHOOT_MODES:
        return
    lang_code = USER_LANG.get(chat_id, LANG_DEFAULT)
    USER_PHOTOSHOOT_MODE[chat_id] = mode_key
    cfg = PHOTOSHOOT_MODES[mode_key]
    label = cfg["label"].get(lang_code, cfg["label"].get("en", mode_key))
    cost = cfg["credits"]
    n_gen = cfg["n_generations"]
    select_k = cfg["select_best"]

    if mode_key == "custom":
        desc_prompt = {
            "ru": f"✅ Режим: {label} ({cost}⚡)\n\n✍️ Опишите ваш образ или идею фотосессии:\n(например: «деловой портрет в офисе», «лето в Майами», «модный editorial»)",
            "en": f"✅ Mode: {label} ({cost}⚡)\n\n✍️ Describe your photoshoot vision:\n(e.g. «business portrait in office», «summer in Miami», «fashion editorial»)",
        }
        await c.message.answer(desc_prompt.get(lang_code, desc_prompt["en"]))
    else:
        info = {
            "ru": f"✅ Режим: {label} ({cost}⚡)\n\nВнутри система создаст {n_gen} вариантов и выберет лучшие {select_k}.\nТеперь отправьте своё селфи.",
            "en": f"✅ Mode: {label} ({cost}⚡)\n\nThe system will create {n_gen} variations internally and select the best {select_k}.\nNow send your selfie.",
        }
        await c.message.answer(info.get(lang_code, info["en"]))


@dp.message(Command("daily"))
async def cmd_daily(m: Message):
    import datetime
    uid = m.chat.id
    lang = L(uid)
    if is_free_user(uid, getattr(m.from_user, "username", None)):
        await safe_answer(m, lang.get("daily_already", "✅ Already claimed.").format(h=0))
        return
    result = _claim_daily_bonus(uid)
    if result:
        add, streak, _milestone_bonus = result
        milestone_key = f"daily_milestone_{streak}" if streak in DAILY_STREAK_MILESTONES else None
        if milestone_key and milestone_key in lang:
            txt = lang[milestone_key].format(n=add, streak=streak)
        else:
            txt = lang.get("daily_claimed", "🎁 +{n} gen! Day {streak} in a row.").format(n=add, streak=streak)
        await safe_answer(m, txt)
    else:
        now = time.time()
        last = USER_LAST_BONUS.get(uid, now)
        streak = USER_STREAK.get(uid, 1)
        next_h = max(0, int((last + DAILY_WINDOW - now) / 3600) + 1)
        next_streak = streak + 1
        next_n = DAILY_STREAK_MILESTONES.get(next_streak, DAILY_BONUS_BASE)
        txt = lang.get("daily_cmd", "🔥 Streak: {streak} days\n🎁 Bonus: +{next_n} gens in {h}h.").format(
            streak=streak, next_n=next_n, h=next_h
        )
        await safe_answer(m, txt)

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

@dp.message(Command("top"))
async def cmd_top(m: Message):
    uid = m.chat.id
    lang_code = USER_LANG.get(uid, LANG_DEFAULT)
    top = _weekly_top_generators(10)
    if not top:
        return await safe_answer(m, "📊 Not enough data yet — generate more photos!")
    period_label = "this week" if top[0].get("period") == "7d" else "all time"
    medals = ["🥇", "🥈", "🥉"] + ["🏅"] * 7
    lines = [f"🏆 *Top generators ({period_label})*\n"]
    my_rank_line = None
    for i, entry in enumerate(top):
        name = _leaderboard_display_name(entry["uid"], entry["username"])
        is_me = entry["uid"] == uid
        suffix = " ← you" if is_me else ""
        line = f"{medals[i]} {name} — {entry['gens']} gens{suffix}"
        lines.append(line)
        if is_me:
            my_rank_line = i + 1
    if my_rank_line is None:
        # Not in top 10
        my_ui = STATS_USERS_INFO.get(uid) or {}
        my_gens = int(my_ui.get("gens_ok", 0))
        lines.append(f"\n_You: #{len(top)+1}+ — {my_gens} gens_")
    text = "\n".join(lines)
    await safe_answer(m, text, parse_mode="Markdown")
    analytics_event(uid, "leaderboard_viewed", {"source": "bot"})

@dp.message(Command("refer"))
async def cmd_refer(m: Message):
    if not BOT_USERNAME_GLOBAL:
        return await safe_answer(m, L(m.chat.id)["ref_link_fail"])
    my_id = m.chat.id
    link = f"https://t.me/{BOT_USERNAME_GLOBAL}?start=ref_{my_id}"
    st = REF_STATS.get(my_id, {"count": 0, "earned": 0})
    count = st["count"]
    earned = st["earned"]

    # Find next milestone
    next_ms = next((n for n in sorted(REFERRAL_MILESTONES) if n > count), None)
    lang = USER_LANG.get(my_id, LANG_DEFAULT)
    if next_ms:
        ms_bonus = REFERRAL_MILESTONES[next_ms]
        ms_hint = {
            "ru": f"\n🎯 До следующей награды: {next_ms - count} приглашений → +{ms_bonus} кредитов",
            "en": f"\n🎯 Next milestone: {next_ms - count} more invite(s) → +{ms_bonus} credits",
            "ro": f"\n🎯 Până la următoarea recompensă: {next_ms - count} invitații → +{ms_bonus} credite",
            "de": f"\n🎯 Nächste Belohnung: noch {next_ms - count} Einladung(en) → +{ms_bonus} Credits",
            "ar": f"\n🎯 الهدف التالي: {next_ms - count} دعوات → +{ms_bonus} رصيد",
        }.get(lang, f"\n🎯 Next milestone: {next_ms - count} more → +{ms_bonus} credits")
    else:
        ms_hint = ""

    msg = L(m.chat.id)["refer_msg"].format(link=link, count=count, earned=earned) + ms_hint

    from urllib.parse import quote as _quote
    share_text = {
        "ru": f"Попробуй AI-фотосессии — создаёт крутые фото из твоего селфи!",
        "en": f"Try AI photoshoots — turns your selfie into stunning photos!",
        "ro": f"Încearcă ședințele foto AI — transformă selfie-ul tău în poze uimitoare!",
        "de": f"Probiere KI-Fotoshootings — verwandelt dein Selfie in tolle Fotos!",
        "ar": f"جرّب جلسات التصوير بالذكاء الاصطناعي — تحوّل صورة السيلفي إلى صور رائعة!",
    }.get(lang, "Try AI photoshoots — turns your selfie into stunning photos!")
    share_url = f"https://t.me/share/url?url={_quote(link)}&text={_quote(share_text)}"

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(
            text={
                "ru": f"📤 Поделиться (+{REF_BONUS_REF} вам)",
                "en": f"📤 Share link (+{REF_BONUS_REF} you)",
                "ro": f"📤 Distribuie (+{REF_BONUS_REF} ție)",
                "de": f"📤 Teilen (+{REF_BONUS_REF} dir)",
                "ar": f"📤 مشاركة الرابط (+{REF_BONUS_REF} لك)",
            }.get(lang, f"📤 Share link (+{REF_BONUS_REF} you)"),
            url=share_url,
        )],
    ])
    await safe_answer(m, msg, reply_markup=kb)

@dp.message(Command("gift"))
async def cmd_gift(m: Message):
    uid = m.chat.id
    lang = USER_LANG.get(uid, LANG_DEFAULT)
    parts = (m.text or "").split(maxsplit=1)
    amount_str = parts[1].strip() if len(parts) > 1 else ""
    _usage: Dict[str, str] = {
        "ru": f"Использование: /gift <кол-во> (от 1 до {GIFT_MAX_CREDITS})\nПример: /gift 10",
        "en": f"Usage: /gift <amount> (1–{GIFT_MAX_CREDITS})\nExample: /gift 10",
        "ro": f"Utilizare: /gift <sumă> (1–{GIFT_MAX_CREDITS})\nExemplu: /gift 10",
        "de": f"Nutzung: /gift <Anzahl> (1–{GIFT_MAX_CREDITS})\nBeispiel: /gift 10",
        "ar": f"الاستخدام: /gift <كمية> (١–{GIFT_MAX_CREDITS})\nمثال: /gift 10",
    }
    if not amount_str.isdigit():
        return await safe_answer(m, _usage.get(lang, _usage["en"]))
    amount = int(amount_str)
    if amount < 1 or amount > GIFT_MAX_CREDITS:
        return await safe_answer(m, _usage.get(lang, _usage["en"]))
    balance = USER_CREDITS.get(uid, 0)
    _insuff: Dict[str, str] = {
        "ru": f"⚡ Недостаточно кредитов. Ваш баланс: {balance}",
        "en": f"⚡ Not enough credits. Your balance: {balance}",
        "ro": f"⚡ Credite insuficiente. Soldul tău: {balance}",
        "de": f"⚡ Nicht genug Credits. Dein Kontostand: {balance}",
        "ar": f"⚡ رصيد غير كافٍ. رصيدك: {balance}",
    }
    if balance < amount:
        return await safe_answer(m, _insuff.get(lang, _insuff["en"]))
    # Deduct and create gift
    async with _credits_lock:
        if USER_CREDITS.get(uid, 0) < amount:
            return await safe_answer(m, _insuff.get(lang, _insuff["en"]))
        USER_CREDITS[uid] -= amount
    _credits_save()
    code = _make_gift_code()
    GIFT_CODES[code] = {
        "from_uid": uid,
        "credits": amount,
        "created_at": time.time(),
        "claimed": False,
        "claimed_by": None,
        "claimed_at": None,
    }
    _gifts_save()
    analytics_event(uid, "gift_created", {"credits": amount, "code": code})
    if not BOT_USERNAME_GLOBAL:
        link = f"[set BOT_USERNAME_GLOBAL]?start={code}"
    else:
        link = f"https://t.me/{BOT_USERNAME_GLOBAL}?start={code}"
    _msg: Dict[str, str] = {
        "ru": f"🎁 Подарочная ссылка создана!\nПодели ею с другом — он получит {amount}⚡ кредитов:\n\n{link}",
        "en": f"🎁 Gift link created!\nShare it with a friend — they'll get {amount}⚡ credits:\n\n{link}",
        "ro": f"🎁 Link cadou creat!\nTrimite-l unui prieten — va primi {amount}⚡ credite:\n\n{link}",
        "de": f"🎁 Geschenklink erstellt!\nTeile ihn mit einem Freund — er bekommt {amount}⚡ Credits:\n\n{link}",
        "ar": f"🎁 تم إنشاء رابط الهدية!\nشاركه مع صديق — سيحصل على {amount}⚡ رصيد:\n\n{link}",
    }
    from urllib.parse import quote as _quote_gift
    _gift_share_text = "🎁 I'm gifting you AI photo credits!"
    share_url = f"https://t.me/share/url?url={_quote_gift(link)}&text={_quote_gift(_gift_share_text)}"
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="📤 Share gift", url=share_url),
    ]])
    await safe_answer(m, _msg.get(lang, _msg["en"]), reply_markup=kb)


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

def _build_modes_list(lang_code: str) -> str:
    """Short mode list for onboarding (top 4 by credit cost ascending)."""
    label_key = "ru" if lang_code == "ru" else "ro" if lang_code == "ro" else "de" if lang_code == "de" else "en"
    lines = []
    for key, cfg in PHOTOSHOOT_MODES.items():
        if key == "custom":
            continue
        label = cfg["label"].get(label_key) or cfg["label"].get("en", key)
        credits = cfg["credits"]
        emoji = cfg["emoji"]
        lines.append((credits, f"{emoji} {label} — {credits}⚡"))
    lines.sort()
    return "\n".join(l for _, l in lines[:5])

@dp.callback_query(F.data == "onboard_go")
async def cb_onboard_go(c: CallbackQuery):
    chat_id = c.message.chat.id
    USER_ONBOARDED.add(chat_id)
    await safe_cb_answer(c)
    lang = L(chat_id)
    lang_code = USER_LANG.get(chat_id, LANG_DEFAULT)
    analytics_event(chat_id, "onboarding_started", {"source": "bot"})

    # Step 1: modes overview with credit balance
    credits = USER_CREDITS.get(chat_id, FREE_QUOTA)
    modes_list = _build_modes_list(lang_code)
    modes_text = lang.get("onboard_modes_intro", "🎨 *What iModel can do:*\n\n{modes_list}\n\nYour starting balance: *{credits}⚡*")
    await c.message.answer(modes_text.format(modes_list=modes_list, credits=credits), parse_mode="Markdown")
    await asyncio.sleep(0.4)

    # Step 2: selfie prompt + Open Studio button
    selfie_prompt = lang.get("onboard_send_selfie", "📷 Send your selfie — I'll create your first photo right now.")
    rows = []
    if WEBHOOK_BASE:
        rows.append([InlineKeyboardButton(
            text="📱 Open Studio",
            web_app=WebAppInfo(url=f"{WEBHOOK_BASE}/webapp"),
        )])
    kb = InlineKeyboardMarkup(inline_keyboard=rows) if rows else None
    await c.message.answer(selfie_prompt, reply_markup=kb, parse_mode="Markdown")
    analytics_event(chat_id, "onboarding_completed", {"source": "bot"})


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

    # Auto-claim daily bonus (silent if free user)
    if not is_free_user(m.chat.id, getattr(m.from_user, "username", None)):
        result = _claim_daily_bonus(m.chat.id)
        if result:
            add, streak, _mb = result
            lang = L(m.chat.id)
            milestone_key = f"daily_milestone_{streak}" if streak in DAILY_STREAK_MILESTONES else None
            if milestone_key and milestone_key in lang:
                txt = lang[milestone_key].format(n=add, streak=streak)
            else:
                txt = lang.get("daily_claimed", "🎁 +{n} gen! Day {streak} in a row.").format(n=add, streak=streak)
            try:
                await m.answer(txt)
            except Exception:
                pass

    # ----- Photoshoot Tournament Mode (non-everyday) -----
    _ps_mode = USER_PHOTOSHOOT_MODE.get(m.chat.id, "everyday")
    if _ps_mode != "everyday":
        uid = m.chat.id
        lang = L(uid)
        _uname_ps = getattr(m.from_user, "username", None)
        _lang_ps = USER_LANG.get(uid, LANG_DEFAULT)
        cost = get_mode_credit_cost(_ps_mode)
        if not await _try_use_credits_n(uid, cost, _uname_ps):
            return await safe_answer(m, lang["credits_none"], reply_markup=kb_invite_buy(uid))
        mode_label = get_mode_label(_ps_mode, _lang_ps)
        wait_texts = {
            "ru": f"🎬 Запускаем {mode_label} фотосессию...\nЯ пришлю результаты, когда всё готово.",
            "en": f"🎬 Starting {mode_label} photoshoot...\nI'll send the results when ready.",
        }
        await safe_answer(m, wait_texts.get(_lang_ps, wait_texts["en"]))
        job = record_job(
            kind="tg_photoshoot",
            status="queued",
            chat_id=uid,
            username=_uname_ps or "",
            prompt=USER_LAST_PROMPT.get(uid, ""),
            model=INSTANTID_MODEL,
            image_bytes=img_bytes,
            lang=_lang_ps,
            photoshoot_mode=_ps_mode,
            custom_desc=USER_PHOTOSHOOT_CUSTOM_DESC.get(uid, ""),
        )
        USER_PHOTOSHOOT_MODE.pop(uid, None)
        USER_PHOTOSHOOT_CUSTOM_DESC.pop(uid, None)
        USER_LAST_JOB[uid] = str(job["job_id"])
        asyncio.create_task(run_photoshoot_tournament_job(str(job["job_id"])))
        return

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
        try:
            _su = s3_put_and_presign(result_bytes, key_prefix=f"shares/tg/{uid}_swap_")
            if _su:
                USER_LAST_OUTPUT_URL[uid] = _su
        except Exception:
            pass
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
        ui = STATS_USERS_INFO.get(m.chat.id) or {}
        analytics_event(m.chat.id, "paywall_hit", {
            "source": "bot", "mode": "everyday",
            "gens_ok": int(ui.get("gens_ok", 0)), "payments": int(ui.get("payments", 0)),
        })
        return await safe_answer(m, _smart_paywall_text(m.chat.id), reply_markup=kb_invite_buy(m.chat.id))

    _t0 = time.time()
    analytics_event(m.chat.id, "generation_started", {"source": "bot", "mode": "everyday"})
    # Check nudge conversion (generated within 24h of nudge)
    _ni = NUDGE_INFO.get(m.chat.id) or {}
    _last_nudge = float(_ni.get("last_sent", 0))
    if _last_nudge and time.time() - _last_nudge < 86400:
        analytics_event(m.chat.id, "nudge_converted", {"segment": _ni.get("last_segment", "unknown"), "hours": round((time.time() - _last_nudge) / 3600, 1)})

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
    # Upload to S3 for share URL (best-effort, non-blocking)
    try:
        _share_url = s3_put_and_presign(final_bytes, key_prefix=f"shares/tg/{m.chat.id}_")
        if _share_url:
            USER_LAST_OUTPUT_URL[m.chat.id] = _share_url
    except Exception:
        pass
    analytics_event(m.chat.id, "generation_completed", {"source": "bot", "mode": "everyday", "latency_ms": int((time.time() - _t0) * 1000)})
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
    # Custom photoshoot mode: first text message = vision description
    if (USER_PHOTOSHOOT_MODE.get(m.chat.id) == "custom"
            and not USER_PHOTOSHOOT_CUSTOM_DESC.get(m.chat.id)):
        USER_PHOTOSHOOT_CUSTOM_DESC[m.chat.id] = m.text.strip()
        lang_code = USER_LANG.get(m.chat.id, LANG_DEFAULT)
        ok_text = {
            "ru": "✅ Образ сохранён. Теперь отправьте своё селфи.",
            "en": "✅ Vision saved. Now send your selfie.",
            "de": "✅ Vision gespeichert. Senden Sie jetzt ein Selfie.",
            "ar": "✅ تم حفظ الفكرة. الآن أرسل صورتك الشخصية.",
        }
        await safe_answer(m, ok_text.get(lang_code, ok_text["en"]))
        return

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


@dp.callback_query(F.data.startswith("hd_notify:"))
async def cb_hd_notify(c: CallbackQuery):
    """HD upgrade button from completion notification."""
    job_id = c.data.split(":", 1)[1]
    uid = c.from_user.id
    uname = getattr(c.from_user, "username", None)
    await safe_cb_answer(c)
    # 2 credits for HD
    if not await _try_use_credits_n(uid, 2, uname):
        lang = USER_LANG.get(uid, LANG_DEFAULT)
        _insuff: Dict[str, str] = {
            "ru": "⚡ Недостаточно кредитов для HD. Пополните баланс!",
            "en": "⚡ Not enough credits for HD. Top up your balance!",
            "ro": "⚡ Credite insuficiente pentru HD. Reîncarcă!",
            "de": "⚡ Nicht genug Credits für HD. Lade auf!",
            "ar": "⚡ رصيد غير كافٍ للـ HD. أعد الشحن!",
        }
        await c.message.answer(_insuff.get(lang, _insuff["en"]), reply_markup=kb_invite_buy(uid))
        return
    hd_job_id = f"{job_id}_hd_{int(time.time())}"
    record_job(hd_job_id, status="pending", kind="hd", parent_job_id=job_id, chat_id=uid)
    asyncio.create_task(_run_hd_upscale_job(hd_job_id, job_id))
    lang = USER_LANG.get(uid, LANG_DEFAULT)
    _hd_started: Dict[str, str] = {
        "ru": "⬆️ HD апскейл запущен! Пришлём результат через минуту.",
        "en": "⬆️ HD upscale started! We'll send the result in a minute.",
        "ro": "⬆️ HD pornit! Îți trimitem rezultatul în câteva minute.",
        "de": "⬆️ HD-Upscale gestartet! Wir senden das Ergebnis gleich.",
        "ar": "⬆️ بدأ تحسين الدقة! سنرسل النتيجة خلال دقيقة.",
    }
    await c.message.answer(_hd_started.get(lang, _hd_started["en"]))
    analytics_event(uid, "hd_from_notif", {"job_id": job_id})


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
    if not os.getenv("WEBHOOK_SECRET"):
        print("🚨 CRITICAL: WEBHOOK_SECRET is not set — any IP can inject fake Telegram updates including payments!")
    # DB connection pool + init with retry (transient network failures on Railway cold-start)
    _init_db_pool()
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
            BotCommand(command="daily",   description="Ежедневный бонус"),
            BotCommand(command="promo",   description="Промокод"),
            BotCommand(command="balance", description="Баланс"),
            BotCommand(command="presets", description="Идеи описаний"),
            BotCommand(command="lang",    description="Сменить язык"),
            BotCommand(command="gallery", description="Моя галерея"),
            BotCommand(command="refer",   description="Реферальная ссылка"),
            BotCommand(command="gift",    description="Подарить кредиты другу"),
            BotCommand(command="top",     description="Топ генераций недели"),
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
        t = asyncio.create_task(_stats_flush_loop(), name="stats_flush")
        t.add_done_callback(_bg_task_error_handler)
        t = asyncio.create_task(_posthog_worker(), name="posthog_worker")
        t.add_done_callback(_bg_task_error_handler)
        t = asyncio.create_task(memory_cleanup_loop(), name="memory_cleanup")
        t.add_done_callback(_bg_task_error_handler)
        if NUDGE_ENABLED:
            t = asyncio.create_task(nudge_loop(), name="nudge_loop")
            t.add_done_callback(_bg_task_error_handler)
            print("Nudge loop started")
            t = asyncio.create_task(streak_reminder_loop(), name="streak_reminder_loop")
            t.add_done_callback(_bg_task_error_handler)
            print("Streak reminder loop started")
            t = asyncio.create_task(quest_reminder_loop(), name="quest_reminder_loop")
            t.add_done_callback(_bg_task_error_handler)
            print("Quest reminder loop started")
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
        log_event("webhook_no_secret_warning", note="accepting all webhook requests — WEBHOOK_SECRET not set")
        return True
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
    if auth.lower().startswith("tma "):
        validated = validate_webapp_init_data(auth.split(" ", 1)[1].strip())
        if validated:
            return {"uid": validated["uid"], "username": validated.get("username", "")}
    init_data = request.headers.get("X-Telegram-Init-Data", "")
    validated = validate_webapp_init_data(init_data)
    if validated:
        return {"uid": validated["uid"], "username": validated.get("username", "")}
    return None

def public_job_snapshot(job: Dict[str, Any]) -> Dict[str, Any]:
    hidden = {"image_bytes", "style_bytes"}
    return {k: v for k, v in job.items() if k not in hidden and not isinstance(v, (bytes, bytearray))}

async def _notify_webapp_completion(
    uid: int,
    job_id: str,
    output_urls: List[str],
    mode_key: str,
    lang: str,
) -> None:
    """Push the first result photo to the user's Telegram chat after a webapp generation finishes."""
    if not uid or not output_urls:
        return
    if NUDGE_INFO.get(uid, {}).get("blocked"):
        return
    try:
        first_url = output_urls[0]
        img_dl = await asyncio.to_thread(_download_with_retries, first_url)
        if not img_dl:
            return
        mode_label = get_mode_label(mode_key, lang)
        _msgs: Dict[str, str] = {
            "ru": f"✨ {mode_label} готово! Посмотрите результат:",
            "en": f"✨ {mode_label} ready! Your photo is here:",
            "ro": f"✨ {mode_label} gata! Fotografia ta este aici:",
            "de": f"✨ {mode_label} fertig! Dein Foto ist bereit:",
            "ar": f"✨ {mode_label} جاهز! صورتك هنا:",
        }
        caption = _msgs.get(lang, _msgs["en"])
        if len(output_urls) > 1:
            caption += f" ({len(output_urls)} photos)"
        webapp_url = f"{WEBHOOK_BASE}/webapp"
        markup = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="🔄 Generate again", web_app=WebAppInfo(url=webapp_url)),
            InlineKeyboardButton(text="⬆️ HD upgrade", callback_data=f"hd_notify:{job_id}"),
        ]])
        await bot.send_photo(
            uid,
            types.BufferedInputFile(img_dl, filename="result.jpg"),
            caption=caption,
            reply_markup=markup,
        )
        analytics_event(uid, "completion_notif_sent", {"job_id": job_id, "mode": mode_key})
    except (TelegramForbiddenError, TelegramNotFound):
        NUDGE_INFO.setdefault(uid, {})["blocked"] = True
    except Exception as e:
        log_event("completion_notif_error", uid=uid, job_id=job_id, error=str(e)[:200])

async def run_webapp_generation_job(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        return
    uid = int(job.get("chat_id") or 0)
    mode = str(job.get("mode") or "portrait")
    record_job(job_id, status="running")
    try:
        prompt = str(job.get("prompt") or "")
        img_bytes = job.get("image_bytes")
        style_bytes = job.get("style_bytes")

        # Mirror bot behavior: derive scene description from reference when prompt is empty
        if mode == "copy_scene" and style_bytes and not prompt:
            try:
                prompt = await asyncio.to_thread(craft_mj_prompt_from_image, style_bytes) or ""
                if not prompt:
                    prompt = await asyncio.to_thread(craft_scene_spec_from_image, style_bytes) or "person, same scene and style"
            except Exception:
                prompt = "person, same scene and style"

        # Inject Age Pack prompt if applicable
        age_key = str(job.get("age_key") or "")
        if age_key:
            age_info = next((a for a in AGE_STYLES if a["key"] == age_key), None)
            if age_info:
                prompt = age_info["prompt"] + (", " + prompt if prompt else "")

        if mode == "face_swap" and style_bytes:
            def _do_swap():
                return face_swap(img_bytes, style_bytes)
            result_bytes = await asyncio.to_thread(_do_swap)
            if result_bytes:
                result_bytes = await asyncio.to_thread(enhance_face_codeformer, result_bytes, 0.85)
            final_bytes = result_bytes
        else:
            final_bytes = await asyncio.to_thread(
                generate_image_from_bytes,
                img_bytes,
                prompt,
                lang=str(job.get("lang") or LANG_DEFAULT),
                strict=(mode == "copy_scene"),
                style_bytes=style_bytes if mode == "copy_scene" else None,
                lock_scene=(mode == "copy_scene"),
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
    output_url, output_s3_key = s3_upload_and_key(final_bytes, key_prefix=f"outputs/webapp/{job_id}_")
    if not output_url:
        stats_incr("jobs_failed", 1)
        record_job(job_id, status="failed", error="s3_upload_failed")
        credit_cost = get_mode_credit_cost(str(job.get("photoshoot_mode") or "everyday"))
        if uid:
            await _refund_credits_n(uid, credit_cost, str(job.get("username") or ""))
        return
    stats_incr("jobs_done", 1)
    # Variable reward: 10% chance of +1–3 bonus credits
    bonus_credits = 0
    if uid and random.random() < 0.10:
        bonus_credits = random.randint(1, 3)
        async with _credits_lock:
            USER_CREDITS[uid] = int(USER_CREDITS.get(uid, 0)) + bonus_credits
        analytics_event(uid, "bonus_credits_awarded", {"credits": bonus_credits, "trigger": "generation"})
    # Track last generation timestamp for streak-at-risk
    if uid:
        ui = STATS_USERS_INFO.setdefault(uid, {})
        ui["last_gen_at"] = time.time()
    record_job(job_id, status="ready", output_url=output_url, output_s3_key=output_s3_key,
               output_bytes=len(final_bytes), bonus_credits=bonus_credits if bonus_credits else None)
    _wjob = JOBS.get(job_id, {})
    analytics_event(_wjob.get("chat_id"), "generation_completed", {"source": "webapp", "mode": "everyday", "job_id": job_id})
    if uid:
        import datetime as _dt
        _today = _dt.date.today().isoformat()
        _quest_incr_daily(uid, "gen_daily_2", _today)
        _quest_incr_daily(uid, "gen_daily_5", _today)
        _preset_key = str(job.get("preset_key") or "")
        if _preset_key:
            _quest_incr_daily(uid, "try_preset", _today)
            _ui = STATS_USERS_INFO.setdefault(uid, {})
            _used = _ui.get("presets_used") if isinstance(_ui.get("presets_used"), list) else []
            if _preset_key not in _used:
                _ui["presets_used"] = (_used + [_preset_key])[-50:]
        # Persist quest progress to DB
        _pj = USER_QUEST_PROGRESS.get(uid, {})
        for _qid in ("gen_daily_2", "gen_daily_5", "try_preset"):
            _db_save_quest(uid, _qid, 0, "", json.dumps(_pj, ensure_ascii=False))
        _check_and_unlock_achievements(uid)
        _lang = str(job.get("lang") or LANG_DEFAULT)
        asyncio.create_task(_notify_webapp_completion(uid, job_id, [output_url], mode, _lang))


async def _run_hd_upscale_job(hd_job_id: str, parent_job_id: str):
    hd_job = JOBS.get(hd_job_id) or {}
    uid = int(hd_job.get("chat_id") or 0)
    username = str(hd_job.get("username") or "")
    HD_COST = 2

    async def _hd_refund():
        if uid:
            await _refund_credits_n(uid, HD_COST, username)

    record_job(hd_job_id, status="running")
    try:
        parent = JOBS.get(parent_job_id) or (_db_load_job(parent_job_id) if DB_READY else None)
        if not parent:
            record_job(hd_job_id, status="failed", error="parent_not_ready")
            await _hd_refund()
            return
        # Use fresh presigned URL from s3_key to avoid 7-day expiry
        download_url = None
        parent_s3_key = parent.get("output_s3_key")
        if parent_s3_key:
            download_url = s3_presign_key(parent_s3_key)
        if not download_url:
            download_url = parent.get("output_url")
        if not download_url:
            record_job(hd_job_id, status="failed", error="parent_not_ready")
            await _hd_refund()
            return
        parent_bytes = await asyncio.to_thread(_download_with_retries, download_url)
        if not parent_bytes:
            record_job(hd_job_id, status="failed", error="download_failed")
            await _hd_refund()
            return
        hd_bytes = await asyncio.to_thread(enhance_face_codeformer, parent_bytes, 0.6, upscale=4)
        if not hd_bytes:
            record_job(hd_job_id, status="failed", error="enhance_failed")
            await _hd_refund()
            return
        output_url, output_s3_key = s3_upload_and_key(hd_bytes, key_prefix=f"outputs/webapp/{hd_job_id}_hd_")
        if not output_url:
            record_job(hd_job_id, status="failed", error="s3_upload_failed")
            await _hd_refund()
            return
        record_job(hd_job_id, status="ready", output_url=output_url, output_s3_key=output_s3_key,
                   output_bytes=len(hd_bytes))
    except Exception as e:
        record_job(hd_job_id, status="failed", error=str(e)[:400])
        await _hd_refund()


async def run_photoshoot_tournament_job(job_id: str):
    """
    Generation Tournament for multi-level photoshoot modes (premium/vogue/ceo/dating/luxury/custom).
    Runs N sequential generations, scores candidates, selects best K, optionally upscales.
    For kind="tg_photoshoot": also delivers results via bot.send_photo.
    """
    job = JOBS.get(job_id)
    if not job:
        return

    uid = int(job.get("chat_id") or 0)
    username = str(job.get("username") or "")
    mode_key = str(job.get("photoshoot_mode") or "everyday")
    cfg = get_mode_config(mode_key)
    n_gen: int = int(cfg["n_generations"])
    select_k: int = int(cfg["select_best"])
    do_upscale: bool = bool(cfg["upscale"])
    upscale_factor: int = int(cfg.get("upscale_factor", 2))
    upscale_fidelity: float = float(cfg.get("upscale_fidelity", 0.8))
    lang: str = str(job.get("lang") or LANG_DEFAULT)

    img_bytes: Optional[bytes] = job.get("image_bytes")
    base_prompt: str = str(job.get("prompt") or "")
    custom_desc: str = str(job.get("custom_desc") or "")

    if not img_bytes:
        record_job(job_id, status="failed", error="no_image_bytes")
        return

    record_job(job_id, status="running", step_label="analyzing")
    job_event(job_id, "tournament_start", mode=mode_key, n_gen=n_gen, select_k=select_k)

    # For custom mode: build GPT prompt from user's vision description
    if mode_key == "custom" and custom_desc:
        record_job(job_id, step_label="crafting_prompt")
        try:
            base_prompt = await asyncio.to_thread(craft_prompt_gpt, custom_desc, lang, True)
            job_event(job_id, "custom_prompt_crafted", prompt=base_prompt[:200])
        except Exception as e:
            job_event(job_id, "custom_prompt_error", error=str(e)[:120])

    effective_prompt = apply_prompt_layer(base_prompt, mode_key)

    candidates: List[tuple] = []  # List of (score, img_bytes)

    for i in range(n_gen):
        step = f"generating_{i + 1}_of_{n_gen}"
        record_job(job_id, step_label=step)
        job_event(job_id, "tournament_step", step=i + 1, total=n_gen)
        try:
            # Pass job_id=None to avoid inner call overwriting tournament job status
            result_bytes = await asyncio.to_thread(
                generate_image_from_bytes,
                img_bytes,
                effective_prompt,
                lang,
                False,   # strict
                None,    # style_bytes
                False,   # lock_scene
                uid,
                None,    # job_id=None — critical: prevent inner call clobbering outer job
            )
            if result_bytes:
                score = await asyncio.to_thread(
                    _judge_candidate_vision, result_bytes, img_bytes, mode_key
                )
                candidates.append((score, result_bytes))
                job_event(job_id, "candidate_ok", index=i + 1, score=round(score, 1), size=len(result_bytes))
            else:
                job_event(job_id, "candidate_empty", index=i + 1)
        except Exception as e:
            job_event(job_id, "candidate_failed", index=i + 1, error=str(e)[:120])

    if not candidates:
        await _refund_credits_n(uid, get_mode_credit_cost(mode_key), username)
        record_job(job_id, status="failed", error="all_candidates_failed")
        stats_incr("tournament_all_failed", 1)
        return

    record_job(job_id, step_label="selecting")
    candidates.sort(key=lambda x: x[0], reverse=True)
    best = candidates[:select_k]
    job_event(job_id, "selection_done", selected=len(best), from_total=len(candidates))

    output_urls: List[str] = []
    for idx, (score, img) in enumerate(best):
        if do_upscale:
            record_job(job_id, step_label="upscaling")
            try:
                img = await asyncio.to_thread(
                    enhance_face_codeformer, img, upscale_fidelity, upscale_factor
                )
            except Exception as e:
                job_event(job_id, "upscale_failed", idx=idx, error=str(e)[:120])

        url = s3_put_and_presign(img, key_prefix=f"outputs/webapp/{job_id}_result{idx}_")
        if url:
            output_urls.append(url)
            job_event(job_id, "result_uploaded", idx=idx, url=url[:80])

    if not output_urls:
        await _refund_credits_n(uid, get_mode_credit_cost(mode_key), username)
        record_job(job_id, status="failed", error="upload_failed")
        return

    record_job(
        job_id,
        status="ready",
        output_url=output_urls[0],
        output_urls=output_urls,
        step_label="ready",
        output_bytes=len(best[0][1]),
    )
    stats_incr("tournament_done", 1)
    _uadd(uid, "photoshoot_count", 1)
    analytics_event(uid, "generation_completed", {"source": "webapp", "mode": mode_key, "results": len(output_urls), "job_id": job_id})

    # Deliver results to Telegram for tg_photoshoot jobs
    if job.get("kind") == "tg_photoshoot" and uid:
        try:
            mode_label = get_mode_label(mode_key, lang)
            caption_prefix = f"✦ {mode_label} Photoshoot"
            for i, url in enumerate(output_urls):
                img_dl = await asyncio.to_thread(_download_with_retries, url)
                if img_dl:
                    cap = f"{caption_prefix} · {i + 1}/{len(output_urls)}" if len(output_urls) > 1 else caption_prefix
                    markup = None
                    if i == len(output_urls) - 1:
                        markup = InlineKeyboardMarkup(inline_keyboard=[[
                            InlineKeyboardButton(text="🔄 Ещё", callback_data="cb_more"),
                            InlineKeyboardButton(text="🛍 Купить кредиты", callback_data="sub_open"),
                        ]])
                    await bot.send_photo(
                        uid,
                        types.BufferedInputFile(img_dl, filename=f"photoshoot_{i}.jpg"),
                        caption=cap,
                        reply_markup=markup,
                    )
        except Exception as e:
            log_event("tournament_delivery_error", job_id=job_id, error=str(e)[:200])
    elif uid:
        # Webapp-initiated tournament job: push first result as Telegram notification
        asyncio.create_task(_notify_webapp_completion(uid, job_id, output_urls, mode_key, lang))


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

@app.get("/webapp_legacy_redirect")
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
    try:
        data = await request.json()
    except Exception:
        data = {}
    init_data = str(data.get("initData") or "")
    # fallback: accept initData from Authorization: tma header
    if not init_data:
        auth = request.headers.get("Authorization", "")
        if auth.lower().startswith("tma "):
            init_data = auth.split(" ", 1)[1].strip()
    validated = validate_webapp_init_data(init_data)
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
    _touch_user(uid, username)
    ui = STATS_USERS_INFO.get(uid) or {}
    active_sub = get_active_sub(uid)
    _plan_raw = (active_sub or {}).get("plan", "free")
    _plan = "sub_weekly" if _plan_raw == "weekly" else _plan_raw
    _plan_expiry = None
    if active_sub:
        import datetime as _dt
        _plan_expiry = _dt.datetime.utcfromtimestamp(active_sub["expires"]).strftime("%Y-%m-%dT%H:%M:%SZ")
    return {
        "uid": uid,
        "chat_id": uid,
        "username": username,
        "credits": USER_CREDITS.get(uid, FREE_QUOTA),
        "plan": _plan,
        "plan_expiry": _plan_expiry,
        "role": role_for_user(uid, username),
        "grants": sorted(grants_for_user(uid, username)),
        "bot_link": f"https://t.me/{BOT_USERNAME_GLOBAL}" if BOT_USERNAME_GLOBAL else None,
        "gens_ok": int(ui.get("gens_ok", 0)) + int(ui.get("gens_copy_ok", 0)),
        "payments": int(ui.get("payments", 0)),
        "streak": int(ui.get("streak", 0)),
        "portfolio_public": USER_PORTFOLIO_PUBLIC.get(uid, False),
        "portfolio_url": f"{WEBHOOK_BASE.rstrip('/')}/p/{uid}" if USER_PORTFOLIO_PUBLIC.get(uid) else None,
        "last_gen_at": float(ui.get("last_gen_at", 0)) or None,
        "can_claim_daily": (time.time() - USER_LAST_BONUS.get(uid, 0)) >= DAILY_WINDOW,
        "next_daily_credits": DAILY_STREAK_MILESTONES.get(int(ui.get("streak", 0)) + 1, DAILY_BONUS_BASE),
        "age_pack": USER_AGE_PACKS.get(uid, False),
        "unlocked_packs": sorted(USER_STYLE_PACKS.get(uid, set())),
        "total_generated": int(ui.get("gens_ok", 0)) + int(ui.get("gens_copy_ok", 0)),
        "friends_invited": int(ui.get("referrals_sent", 0)),
        "language": USER_LANG.get(uid, LANG_DEFAULT),
    }

@app.post("/api/v1/me/language")
async def api_set_language(request: Request):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    uid = int(user["uid"])
    try:
        data = await request.json()
        lang = str(data.get("language") or "").strip().lower()[:8]
    except Exception:
        return JSONResponse({"error": "invalid body"}, status_code=400)
    allowed = {"en", "ru", "ro", "de", "ar"}
    if lang not in allowed:
        return JSONResponse({"error": "unsupported language"}, status_code=400)
    USER_LANG[uid] = lang
    return {"ok": True, "language": lang}


_LEADERBOARD_CACHE: Optional[List[Dict]] = None
_LEADERBOARD_CACHE_AT: float = 0.0
_LEADERBOARD_TTL = 300  # 5 minutes

def _weekly_top_generators(n: int = 10) -> List[Dict[str, Any]]:
    """Return top-N users by generation_completed events in the last 7 days.
    Falls back to lifetime STATS_USERS_INFO gens when DB is unavailable."""
    now = time.time()
    if DB_READY:
        try:
            cutoff = _date_key(now - 7 * 86400)
            rows = _db_fetchall(
                "SELECT uid, COUNT(*) AS gens FROM imodel_events "
                "WHERE event='generation_completed' AND day >= %s "
                "GROUP BY uid ORDER BY gens DESC LIMIT %s",
                (cutoff, n),
            )
            result = []
            for uid, gens in rows:
                uid = int(uid)
                ui = STATS_USERS_INFO.get(uid) or {}
                uname = str(ui.get("username") or "")
                result.append({"uid": uid, "username": uname, "gens": int(gens), "period": "7d"})
            return result
        except Exception as e:
            print(f"[leaderboard] db error: {str(e)[:120]}")
    # Fallback: use lifetime counts from in-memory stats
    items = []
    for uid, ui in STATS_USERS_INFO.items():
        gens = int(ui.get("gens_ok", 0)) + int(ui.get("gens_copy_ok", 0))
        if gens > 0:
            items.append({"uid": uid, "username": str(ui.get("username") or ""), "gens": gens, "period": "all"})
    items.sort(key=lambda x: x["gens"], reverse=True)
    return items[:n]

def _leaderboard_display_name(uid: int, username: str) -> str:
    """Anonymised name: @user if available, else 'User #NNN' (deterministic short id)."""
    if username:
        # Show first 2 chars + *** to preserve some identity without full dox
        visible = username[:3] if len(username) >= 3 else username
        return f"@{visible}***"
    return f"User #{uid % 10000:04d}"

@app.get("/api/v1/experiments")
async def api_experiments(request: Request):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    uid = int(user["uid"])
    assignments = all_variants(uid)
    # Log exposure for any newly-seen variants
    for exp_name, variant in assignments.items():
        analytics_event(uid, "experiment_exposure", {"experiment": exp_name, "variant": variant})
    return {"assignments": assignments}

@app.get("/api/v1/leaderboard")
async def api_leaderboard(request: Request):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    global _LEADERBOARD_CACHE, _LEADERBOARD_CACHE_AT
    caller_uid = int(user["uid"])
    now_ts = time.time()
    if _LEADERBOARD_CACHE is None or now_ts - _LEADERBOARD_CACHE_AT > _LEADERBOARD_TTL:
        _LEADERBOARD_CACHE = _weekly_top_generators(10)
        _LEADERBOARD_CACHE_AT = now_ts
    top = _LEADERBOARD_CACHE
    # Determine caller's rank
    caller_rank: Optional[int] = None
    caller_gens = 0
    for i, entry in enumerate(top):
        if entry["uid"] == caller_uid:
            caller_rank = i + 1
            caller_gens = entry["gens"]
            break
    if caller_rank is None:
        # Caller not in top 10 — compute their own weekly count
        if DB_READY:
            try:
                cutoff = _date_key(time.time() - 7 * 86400)
                rows = _db_fetchall(
                    "SELECT COUNT(*) FROM imodel_events WHERE event='generation_completed' AND uid=%s AND day>=%s",
                    (caller_uid, cutoff),
                )
                caller_gens = int(rows[0][0]) if rows else 0
            except Exception:
                pass
        else:
            ui = STATS_USERS_INFO.get(caller_uid) or {}
            caller_gens = int(ui.get("gens_ok", 0))
        # Approximate rank
        caller_rank = len(top) + 1 if caller_gens < (top[-1]["gens"] if top else 0) else None
    entries = [
        {
            "rank": i + 1,
            "display_name": _leaderboard_display_name(e["uid"], e["username"]),
            "gens": e["gens"],
            "is_me": e["uid"] == caller_uid,
        }
        for i, e in enumerate(top)
    ]
    period = top[0]["period"] if top else "7d"
    return {
        "entries": entries,
        "period": period,
        "my_rank": caller_rank,
        "my_gens": caller_gens,
        "updated_at": int(time.time()),
    }

def _refresh_gallery_url(item: dict) -> dict:
    """Regenerate a fresh 7-day presigned URL from the stored S3 key (if available)."""
    s3_key = item.get("output_s3_key")
    if s3_key:
        fresh = s3_presign_key(s3_key)
        if fresh:
            item = dict(item, output_url=fresh)
    return item


@app.get("/api/v1/gallery")
async def api_gallery(request: Request):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    uid = int(user["uid"])
    if DB_READY:
        items = [_refresh_gallery_url(public_job_snapshot(j)) for j in _db_load_user_jobs(uid, 50)]
    else:
        all_cached = _cache_load_jobs()
        items = [
            _refresh_gallery_url(j)
            for j in sorted(
                [j for j in all_cached if int(j.get("chat_id") or 0) == uid],
                key=lambda x: x.get("created_at", 0), reverse=True,
            )[:50]
        ]
    return {"items": items}

@app.delete("/api/v1/gallery/{job_id}")
async def api_gallery_delete(job_id: str, request: Request):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    uid = int(user["uid"])
    # Retrieve the job to get s3_key before marking deleted
    job = JOBS.get(job_id) or (_db_load_job(job_id) if DB_READY else None)
    if job and int(job.get("chat_id") or 0) != uid:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    s3_key = (job or {}).get("output_s3_key")
    if DB_READY:
        _db_execute(
            "UPDATE imodel_jobs SET status='deleted' WHERE job_id=%s AND chat_id=%s",
            (job_id, uid),
        )
    JOBS.pop(job_id, None)
    _cache_delete_job(job_id)
    # Remove S3 object so user data is truly deleted (GDPR)
    if s3_key:
        await asyncio.to_thread(s3_delete_key, s3_key)
    return {"ok": True}

@app.get("/api/v1/proxy-image")
async def api_proxy_image(url: str, request: Request):
    """
    Same-origin image proxy so the frontend can fetch Replicate/S3 images as blobs
    without CORS issues inside Telegram's WKWebView.
    """
    from fastapi.responses import Response as _Resp
    from urllib.parse import urlparse as _urlparse
    import ipaddress as _ipaddress

    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    url = (url or "").strip()
    if not url.startswith("https://"):
        return JSONResponse({"error": "https_only"}, status_code=400)
    # SSRF guard: resolve hostname to IP and block private/loopback ranges
    # (also blocks redirect-based SSRF by using allow_redirects=False)
    import socket as _socket
    try:
        _host = _urlparse(url).hostname or ""
        if not _host:
            return JSONResponse({"error": "blocked"}, status_code=400)
        if _host.lower() in ("localhost", "metadata.google.internal"):
            return JSONResponse({"error": "blocked"}, status_code=400)
        try:
            _addr = _ipaddress.ip_address(_host)
            if _addr.is_private or _addr.is_loopback or _addr.is_link_local:
                return JSONResponse({"error": "blocked"}, status_code=400)
        except ValueError:
            # Resolve hostname → check resolved IP
            try:
                _resolved = _socket.gethostbyname(_host)
                _raddr = _ipaddress.ip_address(_resolved)
                if _raddr.is_private or _raddr.is_loopback or _raddr.is_link_local:
                    return JSONResponse({"error": "blocked"}, status_code=400)
            except Exception:
                pass
    except Exception:
        pass

    def _proxy_download(u: str) -> Optional[bytes]:
        # allow_redirects=False prevents redirect-based SSRF to internal IPs
        r = requests.get(u, timeout=30, allow_redirects=False)
        if r.status_code in (301, 302, 307, 308):
            return None  # block redirect
        if r.ok and r.content:
            return r.content
        return None

    try:
        data = await asyncio.to_thread(_proxy_download, url)
        if not data:
            return JSONResponse({"error": "download_failed"}, status_code=502)
        # Validate content is actually an image (reject HTML pages, etc.)
        _is_img = (
            (len(data) > 3  and data[:3] == b"\xff\xd8\xff") or          # JPEG
            (len(data) > 8  and data[:8] == b"\x89PNG\r\n\x1a\n") or     # PNG
            (len(data) > 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP") or  # WEBP
            (len(data) > 6  and data[:6] in (b"GIF87a", b"GIF89a"))       # GIF
        )
        if not _is_img:
            return JSONResponse({"error": "not_an_image"}, status_code=400)
        ct = "image/jpeg"
        if len(data) > 12:
            if data[:8] == b"\x89PNG\r\n\x1a\n":
                ct = "image/png"
            elif data[:4] == b"RIFF" and data[8:12] == b"WEBP":
                ct = "image/webp"
        return _Resp(content=data, media_type=ct,
                     headers={"Cache-Control": "private, max-age=3600"})
    except Exception as _pe:
        return JSONResponse({"error": str(_pe)[:80]}, status_code=502)

ALLOWED_REACTIONS = ["❤️", "🔥", "😍", "👏", "😮"]
# job_id → {emoji: count}
PHOTO_REACTIONS: Dict[str, Dict[str, int]] = {}
# (uid, job_id) → emoji  (one reaction per user per photo)
USER_PHOTO_REACTIONS: Dict[tuple, str] = {}

@app.post("/api/v1/gallery/{job_id}/react")
async def api_gallery_react(job_id: str, request: Request):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    uid = int(user["uid"])
    try:
        data = await request.json()
        emoji = str(data.get("emoji") or "").strip()
    except Exception:
        return JSONResponse({"error": "invalid body"}, status_code=400)
    if emoji not in ALLOWED_REACTIONS:
        return JSONResponse({"error": "invalid emoji"}, status_code=400)
    key = (uid, job_id)
    prev = USER_PHOTO_REACTIONS.get(key)
    reactions = PHOTO_REACTIONS.setdefault(job_id, {})
    if prev:
        # Remove previous reaction
        reactions[prev] = max(0, int(reactions.get(prev, 1)) - 1)
    if emoji == prev:
        # Toggle off
        del USER_PHOTO_REACTIONS[key]
        my_reaction = None
    else:
        reactions[emoji] = int(reactions.get(emoji, 0)) + 1
        USER_PHOTO_REACTIONS[key] = emoji
        my_reaction = emoji
    return {"ok": True, "reactions": reactions, "my_reaction": my_reaction}

@app.get("/api/v1/gallery/{job_id}/reactions")
async def api_gallery_reactions(job_id: str, request: Request):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    uid = int(user["uid"])
    reactions = PHOTO_REACTIONS.get(job_id, {})
    my_reaction = USER_PHOTO_REACTIONS.get((uid, job_id))
    return {"reactions": reactions, "my_reaction": my_reaction}


# ===================== COMMUNITY PRESETS =====================

@app.post("/api/v1/community/share")
async def api_community_share(request: Request):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    uid = int(user["uid"])
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)

    job_id = str(body.get("job_id") or "").strip()
    label = str(body.get("label") or "").strip()[:40] or "My Style"
    if not job_id:
        return JSONResponse({"error": "job_id_required"}, status_code=400)

    job = JOBS.get(job_id) or (_db_load_job(job_id) if DB_READY else None)
    if not job or int(job.get("chat_id") or 0) != uid:
        return JSONResponse({"error": "not_found"}, status_code=404)
    if job.get("status") != "ready":
        return JSONResponse({"error": "job_not_ready"}, status_code=400)

    prompt = str(job.get("prompt") or "").strip()
    if not prompt:
        return JSONResponse({"error": "no_prompt"}, status_code=400)

    s3_key = job.get("output_s3_key")
    cp_key = f"cp_{job_id[:12]}"

    # Check duplicate
    if DB_READY:
        existing = _db_fetchall("SELECT key FROM imodel_community_presets WHERE key=%s LIMIT 1", (cp_key,))
        if existing:
            return {"ok": True, "key": cp_key, "already_shared": True}
    else:
        if any(p.get("key") == cp_key for p in COMMUNITY_PRESETS):
            return {"ok": True, "key": cp_key, "already_shared": True}

    creator_name = user.get("username") or user.get("first_name") or "anonymous"
    now = time.time()

    if DB_READY:
        _db_execute(
            "INSERT INTO imodel_community_presets(key, creator_uid, creator_name, label, prompt, output_s3_key, votes, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, 0, %s) ON CONFLICT (key) DO NOTHING",
            (cp_key, uid, creator_name, label, prompt, s3_key, now),
        )
    else:
        COMMUNITY_PRESETS.append({
            "key": cp_key, "creator_uid": uid, "creator_name": creator_name,
            "label": label, "prompt": prompt, "output_s3_key": s3_key,
            "votes": 0, "created_at": now,
        })
        _save_community_file()

    # +5 bonus credits for sharing
    async with _credits_lock:
        USER_CREDITS[uid] = int(USER_CREDITS.get(uid, 0)) + 5
    analytics_event(uid, "community_share", {"key": cp_key, "label": label})
    import datetime as _dt
    _quest_incr_daily(uid, "share_photo", _dt.date.today().isoformat())
    _check_and_unlock_achievements(uid)
    return {"ok": True, "key": cp_key, "already_shared": False}


@app.get("/api/v1/community")
async def api_community_list(request: Request, sort: str = "top"):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    uid = int(user["uid"])
    items = _load_community_presets_for_api(uid, sort=sort, limit=100)
    result = []
    for cp in items:
        thumb = s3_presign_key(cp["output_s3_key"]) if cp.get("output_s3_key") else None
        result.append({
            "key": cp["key"],
            "label": cp["label"],
            "emoji": "✨",
            "category": "community",
            "is_premium": False,
            "locked": False,
            "prompt": cp["prompt"],
            "thumbnail_url": thumb or "",
            "votes": cp["votes"],
            "creator_name": cp.get("creator_name") or "anonymous",
            "creator_uid": cp["creator_uid"],
            "my_vote": _has_community_vote(uid, cp["key"]),
            "created_at": cp["created_at"],
        })
    return {"presets": result}


@app.post("/api/v1/community/{key}/vote")
async def api_community_vote(key: str, request: Request):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    uid = int(user["uid"])

    already_voted = _has_community_vote(uid, key)

    if DB_READY:
        if already_voted:
            _db_execute("DELETE FROM imodel_community_votes WHERE uid=%s AND preset_key=%s", (uid, key))
            _db_execute("UPDATE imodel_community_presets SET votes = GREATEST(0, votes - 1) WHERE key=%s", (key,))
        else:
            _db_execute("INSERT INTO imodel_community_votes(uid, preset_key) VALUES(%s,%s) ON CONFLICT DO NOTHING", (uid, key))
            _db_execute("UPDATE imodel_community_presets SET votes = votes + 1 WHERE key=%s", (key,))
        rows = _db_fetchall("SELECT votes, creator_uid FROM imodel_community_presets WHERE key=%s LIMIT 1", (key,))
        if not rows:
            return JSONResponse({"error": "not_found"}, status_code=404)
        new_votes, creator_uid = int(rows[0][0]), int(rows[0][1])
    else:
        vote_key = f"{uid}_{key}"
        cp = next((p for p in COMMUNITY_PRESETS if p["key"] == key), None)
        if not cp:
            return JSONResponse({"error": "not_found"}, status_code=404)
        if already_voted:
            COMMUNITY_VOTES.discard(vote_key)
            cp["votes"] = max(0, cp["votes"] - 1)
        else:
            COMMUNITY_VOTES.add(vote_key)
            cp["votes"] = cp["votes"] + 1
        _save_community_file()
        new_votes = cp["votes"]
        creator_uid = cp["creator_uid"]

    # Milestone notifications
    if not already_voted and new_votes in (10, 50, 100):
        try:
            asyncio.create_task(
                bot.send_message(creator_uid, f"🔥 Твой стиль набрал {new_votes} голосов в сообществе! Продолжай творить ✨")
            )
        except Exception:
            pass

    return {"votes": new_votes, "my_vote": not already_voted}


@app.delete("/api/v1/community/{key}")
async def api_community_delete(key: str, request: Request):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    uid = int(user["uid"])
    is_admin = _check_admin_auth(request)

    if DB_READY:
        rows = _db_fetchall("SELECT creator_uid FROM imodel_community_presets WHERE key=%s LIMIT 1", (key,))
        if not rows:
            return JSONResponse({"error": "not_found"}, status_code=404)
        if int(rows[0][0]) != uid and not is_admin:
            return JSONResponse({"error": "forbidden"}, status_code=403)
        _db_execute("DELETE FROM imodel_community_votes WHERE preset_key=%s", (key,))
        _db_execute("DELETE FROM imodel_community_presets WHERE key=%s", (key,))
    else:
        cp = next((p for p in COMMUNITY_PRESETS if p["key"] == key), None)
        if not cp:
            return JSONResponse({"error": "not_found"}, status_code=404)
        if cp["creator_uid"] != uid and not is_admin:
            return JSONResponse({"error": "forbidden"}, status_code=403)
        COMMUNITY_PRESETS[:] = [p for p in COMMUNITY_PRESETS if p["key"] != key]
        COMMUNITY_VOTES.discard(f"{uid}_{key}")
        _save_community_file()

    return {"ok": True}


def _s3_key_from_url(url: str) -> Optional[str]:
    """Extract S3 object key from a presigned URL."""
    try:
        from urllib.parse import urlparse, unquote
        parsed = urlparse(url)
        path = unquote(parsed.path).lstrip("/")
        # path-style: /{bucket}/{key}  →  strip bucket prefix
        bucket = str(S3_BUCKET or "")
        if bucket and path.startswith(bucket + "/"):
            return path[len(bucket) + 1:]
        # virtual-host-style: bucket.endpoint/{key}  →  path IS the key
        if path:
            return path
    except Exception:
        pass
    return None

def _s3_fetch_bytes(s3_key: str) -> Optional[bytes]:
    """Fetch raw bytes for an S3 object key."""
    if not (_s3 and S3_BUCKET and s3_key):
        return None
    try:
        obj = _s3.get_object(Bucket=S3_BUCKET, Key=s3_key)
        return obj["Body"].read()
    except Exception:
        return None

def _portfolio_photos(uid: int, limit: int = 12) -> List[Dict[str, Any]]:
    """Return ready jobs for a user, newest first."""
    if DB_READY:
        jobs = _db_load_user_jobs(uid, limit)
    else:
        jobs = sorted(
            [j for j in JOBS.values() if int(j.get("chat_id") or 0) == uid and j.get("status") == "ready"],
            key=lambda j: float(j.get("updated_at", 0)),
            reverse=True,
        )[:limit]
    return [public_job_snapshot(j) for j in jobs if j.get("output_url")]

@app.get("/portfolio-photo/{uid}/{job_id}")
async def serve_portfolio_photo(uid: int, job_id: str):
    """Permanent proxy for portfolio photos — bypasses presigned URL expiry."""
    job = JOBS.get(job_id) or (_db_load_job(job_id) if DB_READY else None)
    if not job or int(job.get("chat_id") or 0) != uid or job.get("status") != "ready":
        return JSONResponse({"error": "not_found"}, status_code=404)
    output_url = str(job.get("output_url") or "")
    s3_key = _s3_key_from_url(output_url)
    if s3_key:
        img_bytes = await asyncio.to_thread(_s3_fetch_bytes, s3_key)
        if img_bytes:
            from starlette.responses import Response as StarletteResponse
            return StarletteResponse(
                content=img_bytes,
                media_type="image/jpeg",
                headers={"Cache-Control": "public, max-age=604800", "X-Robots-Tag": "noindex"},
            )
    # Fallback: redirect to original (may be expired)
    from starlette.responses import RedirectResponse
    return RedirectResponse(url=output_url, status_code=302)

@app.get("/api/v1/portfolio/{uid}")
async def api_portfolio_public(uid: int, request: Request):
    """Public portfolio data — no auth required."""
    if not USER_PORTFOLIO_PUBLIC.get(uid):
        return JSONResponse({"error": "portfolio_private"}, status_code=404)
    ui = STATS_USERS_INFO.get(uid) or {}
    username = str(ui.get("username") or "")
    display = f"@{username}" if username else f"User #{uid}"
    gens_ok = int(ui.get("gens_ok", 0))
    photos = _portfolio_photos(uid, limit=12)
    base = str(WEBHOOK_BASE).rstrip("/")
    items = []
    for j in photos:
        items.append({
            "job_id": j.get("job_id"),
            "photo_url": f"{base}/portfolio-photo/{uid}/{j.get('job_id')}",
            "prompt": str(j.get("prompt") or "")[:120],
            "created_at": j.get("updated_at"),
        })
    bot_link = f"https://t.me/{BOT_USERNAME_GLOBAL}" if BOT_USERNAME_GLOBAL else ""
    return {
        "uid": uid,
        "display": display,
        "total_generated": gens_ok,
        "items": items,
        "bot_link": bot_link,
        "portfolio_url": f"{base}/p/{uid}",
    }

@app.post("/api/v1/portfolio/visibility")
async def api_portfolio_visibility(request: Request):
    """Toggle portfolio public/private."""
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    uid = int(user["uid"])
    data = await request.json()
    public = bool(data.get("public", True))
    USER_PORTFOLIO_PUBLIC[uid] = public
    analytics_event(uid, "portfolio_visibility_changed", {"public": public})
    base = str(WEBHOOK_BASE).rstrip("/")
    return {"public": public, "portfolio_url": f"{base}/p/{uid}" if public else None}


@app.post("/api/v1/gift/create")
async def api_gift_create(request: Request):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    uid = int(user["uid"])
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "bad_request"}, status_code=400)
    amount = int(data.get("credits", 0))
    if amount < 1 or amount > GIFT_MAX_CREDITS:
        return JSONResponse({"error": "invalid_amount", "max": GIFT_MAX_CREDITS}, status_code=400)
    balance = USER_CREDITS.get(uid, 0)
    if balance < amount:
        return JSONResponse({"error": "insufficient_credits", "balance": balance}, status_code=402)
    async with _credits_lock:
        if USER_CREDITS.get(uid, 0) < amount:
            return JSONResponse({"error": "insufficient_credits"}, status_code=402)
        USER_CREDITS[uid] -= amount
    _credits_save()
    code = _make_gift_code()
    GIFT_CODES[code] = {
        "from_uid": uid,
        "credits": amount,
        "created_at": time.time(),
        "claimed": False,
        "claimed_by": None,
        "claimed_at": None,
    }
    _gifts_save()
    analytics_event(uid, "gift_created", {"credits": amount, "code": code, "source": "webapp"})
    bot_username = BOT_USERNAME_GLOBAL or "imodelapp_bot"
    link = f"https://t.me/{bot_username}?start={code}"
    return {"code": code, "credits": amount, "link": link}


@app.post("/api/v1/caption/generate")
async def api_caption_generate(request: Request):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    uid = int(user["uid"])
    try:
        data = await request.json()
    except Exception:
        return JSONResponse({"error": "bad_request"}, status_code=400)
    style = str(data.get("style") or "portrait")
    mode = str(data.get("mode") or "portrait")
    captions = await asyncio.to_thread(generate_captions_gpt, style, mode)
    analytics_event(uid, "caption_generated", {"style": style, "mode": mode})
    return {"captions": captions}


@app.get("/p/{uid}")
async def portfolio_page(uid: int, request: Request):
    """Public portfolio page — server-rendered, shareable."""
    if not USER_PORTFOLIO_PUBLIC.get(uid):
        return HTMLResponse(
            '<html><body style="font:16px sans-serif;text-align:center;padding:80px;background:#0f1115;color:#aaa">'
            '<p>This portfolio is private.</p></body></html>',
            status_code=404,
        )
    ui = STATS_USERS_INFO.get(uid) or {}
    username = str(ui.get("username") or "")
    display = html_lib.escape(f"@{username}" if username else f"User #{uid}")
    gens_ok = int(ui.get("gens_ok", 0))
    photos = _portfolio_photos(uid, limit=12)
    base = str(WEBHOOK_BASE).rstrip("/")
    bot_link = html_lib.escape(f"https://t.me/{BOT_USERNAME_GLOBAL}" if BOT_USERNAME_GLOBAL else "https://t.me/imodelapp_bot")
    portfolio_url = html_lib.escape(f"{base}/p/{uid}")

    # OG image: first photo or empty
    og_image = ""
    if photos:
        og_image = html_lib.escape(f"{base}/portfolio-photo/{uid}/{photos[0].get('job_id')}")

    photo_grid = ""
    for j in photos:
        job_id = j.get("job_id", "")
        photo_url = html_lib.escape(f"{base}/portfolio-photo/{uid}/{job_id}")
        prompt = html_lib.escape(str(j.get("prompt") or "")[:80])
        photo_grid += f"""
        <div class="photo-card" onclick="revealPhoto(this, '{photo_url}')">
          <div class="blur-overlay">
            <img src="{photo_url}" alt="{prompt}" loading="lazy">
            <div class="tap-hint">Tap to reveal</div>
          </div>
          <p class="prompt-text">{prompt or "AI Portrait"}</p>
        </div>"""

    return HTMLResponse(f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>{display}'s AI Portfolio — iModel</title>
  <meta name="description" content="{display} has generated {gens_ok} AI portraits. Create yours!">
  <meta property="og:title" content="{display}'s AI Portfolio">
  <meta property="og:description" content="{gens_ok} AI-generated portraits — create yours with iModel">
  {"<meta property='og:image' content='" + og_image + "'>" if og_image else ""}
  <meta property="og:type" content="profile">
  <meta name="twitter:card" content="summary_large_image">
  <style>
    *{{box-sizing:border-box;margin:0;padding:0}}
    body{{font:-apple-system,BlinkMacSystemFont,'Segoe UI',sans-serif;background:#0d0d12;color:#e6edf3;min-height:100vh}}
    .hero{{padding:40px 20px 24px;text-align:center;background:linear-gradient(180deg,#1a0a2e 0%,#0d0d12 100%)}}
    .avatar{{width:80px;height:80px;border-radius:50%;background:linear-gradient(135deg,#6c47ff,#ff2d78);display:inline-flex;align-items:center;justify-content:center;font-size:32px;margin-bottom:14px}}
    .username{{font-size:24px;font-weight:700;color:#fff}}
    .stats{{font-size:14px;color:#9aa4b2;margin-top:6px}}
    .stat-pill{{display:inline-block;background:#1b2030;border:1px solid #2a3556;border-radius:20px;padding:4px 12px;font-size:13px;color:#7aa2f7;margin-top:8px}}
    .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(160px,1fr));gap:10px;padding:20px}}
    .photo-card{{border-radius:12px;overflow:hidden;background:#151922;cursor:pointer;transition:transform .15s}}
    .photo-card:hover{{transform:scale(1.02)}}
    .blur-overlay{{position:relative}}
    .blur-overlay img{{width:100%;aspect-ratio:1;object-fit:cover;display:block;filter:blur(14px);transition:filter .3s}}
    .blur-overlay.revealed img{{filter:none}}
    .tap-hint{{position:absolute;inset:0;display:flex;align-items:center;justify-content:center;font-size:12px;color:rgba(255,255,255,.7);font-weight:600;pointer-events:none;transition:opacity .3s}}
    .blur-overlay.revealed .tap-hint{{opacity:0}}
    .prompt-text{{font-size:11px;color:#9aa4b2;padding:6px 10px 8px;line-height:1.4;max-height:42px;overflow:hidden}}
    .cta{{text-align:center;padding:32px 20px 48px}}
    .cta-btn{{display:inline-block;padding:14px 32px;background:linear-gradient(135deg,#6c47ff,#ff2d78);border-radius:50px;color:#fff;font-size:16px;font-weight:700;text-decoration:none}}
    .cta-sub{{font-size:13px;color:#9aa4b2;margin-top:12px}}
    .share-bar{{display:flex;justify-content:center;gap:10px;padding:0 20px 20px}}
    .share-btn{{flex:1;max-width:200px;padding:10px;background:#1b2030;border:1px solid #2a3556;border-radius:10px;color:#7aa2f7;font-size:13px;font-weight:600;cursor:pointer;text-align:center}}
  </style>
</head>
<body>
  <div class="hero">
    <div class="avatar">✨</div>
    <div class="username">{display}</div>
    <div class="stats">AI Portrait Studio</div>
    <span class="stat-pill">🖼 {gens_ok} generations created</span>
  </div>

  <div class="share-bar">
    <button class="share-btn" onclick="copyLink()">🔗 Copy link</button>
    <a class="share-btn" href="https://t.me/share/url?url={portfolio_url}&text=Check+out+my+AI+portraits!" target="_blank">📨 Share to Telegram</a>
  </div>

  <div class="grid">
    {photo_grid if photo_grid else '<p style="color:#9aa4b2;text-align:center;padding:40px">No photos yet.</p>'}
  </div>

  <div class="cta">
    <a class="cta-btn" href="{bot_link}">✨ Create your AI portfolio →</a>
    <p class="cta-sub">Free to start · Powered by iModel AI</p>
  </div>

  <script>
  function revealPhoto(card, url) {{
    const overlay = card.querySelector('.blur-overlay');
    if (overlay.classList.contains('revealed')) return;
    overlay.classList.add('revealed');
  }}
  async function copyLink() {{
    try {{
      await navigator.clipboard.writeText('{portfolio_url}');
      alert('Portfolio link copied!');
    }} catch(e) {{
      prompt('Copy this link:', '{portfolio_url}');
    }}
  }}
  </script>
</body>
</html>""")

def _decode_b64_image(b64: str) -> Optional[bytes]:
    try:
        if b64.startswith("data:") and "," in b64:
            b64 = b64.split(",", 1)[1]
        return base64.b64decode(b64)
    except Exception:
        return None

def _resolve_preset_prompt(preset_key: str) -> Optional[str]:
    for p in PRESETS:
        if p.key == preset_key:
            return p.prompt
    for s in PREMIUM_STYLES:
        if s["key"] == preset_key:
            return s["prompt"]
    for a in AGE_STYLES:
        if a["key"] == preset_key:
            return a["prompt"]
    return None

@app.post("/api/v1/generations")
async def api_create_generation(request: Request):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    uid = int(user["uid"])
    username = str(user.get("username") or "")
    ensure_user_credit(uid)
    # Concurrency cap — prevents free users from queuing unlimited Replicate jobs
    if _user_active_jobs_count(uid) >= MAX_CONCURRENT_JOBS_PER_USER:
        return JSONResponse({"error": "too_many_active_jobs", "max": MAX_CONCURRENT_JOBS_PER_USER}, status_code=429)
    data = await request.json()

    photoshoot_mode = str(data.get("photoshoot_mode") or "everyday").strip()
    if photoshoot_mode not in PHOTOSHOOT_MODES:
        photoshoot_mode = "everyday"
    custom_desc = str(data.get("custom_desc") or "").strip()[:1000]
    credit_cost = get_mode_credit_cost(photoshoot_mode)

    # Check and deduct credits (n credits for photoshoot modes)
    if not await _try_use_credits_n(uid, credit_cost, username):
        _pw_ui = STATS_USERS_INFO.get(uid) or {}
        analytics_event(uid, "paywall_hit", {
            "source": "webapp", "mode": photoshoot_mode, "required": credit_cost,
            "gens_ok": int(_pw_ui.get("gens_ok", 0)), "payments": int(_pw_ui.get("payments", 0)),
        })
        return JSONResponse(
            {"error": "no_credits", "required": credit_cost, "available": USER_CREDITS.get(uid, 0)},
            status_code=402,
        )
    analytics_event(uid, "generation_started", {"source": "webapp", "mode": photoshoot_mode, "credit_cost": credit_cost})

    prompt = str(data.get("prompt") or "").strip()
    image_b64 = str(data.get("image_b64") or "").strip()
    mode = str(data.get("mode") or "portrait")
    preset_key = str(data.get("preset_key") or "")
    style_b64  = str(data.get("style_b64") or "")
    age_key    = str(data.get("age_key") or "")

    # Resolve preset prompt
    if preset_key and not prompt:
        prompt = _resolve_preset_prompt(preset_key) or ""
    if not image_b64:
        await _refund_credits_n(uid, credit_cost, username)
        return JSONResponse({"error": "image_b64 required"}, status_code=400)
    image_bytes = _decode_b64_image(image_b64)
    if not image_bytes:
        await _refund_credits_n(uid, credit_cost, username)
        return JSONResponse({"error": "invalid image"}, status_code=400)
    ok, reason = assess_selfie_quality(image_bytes)
    if not ok:
        await _refund_credits_n(uid, credit_cost, username)
        return JSONResponse({"error": "selfie_quality", "reason": reason}, status_code=400)
    style_bytes = _decode_b64_image(style_b64) if style_b64 else None

    if photoshoot_mode != "everyday":
        # Photoshoot tournament pipeline
        job = record_job(
            kind="webapp_photoshoot",
            status="queued",
            chat_id=uid,
            username=username,
            prompt=prompt,
            model=INSTANTID_MODEL,
            image_bytes=image_bytes,
            mode=mode,
            age_key=age_key,
            lang=str(data.get("lang") or LANG_DEFAULT),
            photoshoot_mode=photoshoot_mode,
            custom_desc=custom_desc,
        )
        stats_incr("jobs_created", 1)
        asyncio.create_task(run_photoshoot_tournament_job(str(job["job_id"])))
        return {"job_id": job["job_id"], "status": "queued", "credit_cost": credit_cost,
                "photoshoot_mode": photoshoot_mode}

    # Everyday mode — existing path unchanged
    job = record_job(
        kind="webapp_generation",
        status="queued",
        chat_id=uid,
        username=username,
        prompt=prompt,
        model=INSTANTID_MODEL,
        image_bytes=image_bytes,
        style_bytes=style_bytes,
        mode=mode,
        age_key=age_key,
        lang=str(data.get("lang") or LANG_DEFAULT),
        photoshoot_mode="everyday",
    )
    stats_incr("jobs_created", 1)
    asyncio.create_task(run_webapp_generation_job(str(job["job_id"])))
    return {"job_id": job["job_id"], "status": "queued", "credit_cost": 1, "photoshoot_mode": "everyday"}

@app.post("/api/v1/generations/batch")
async def api_create_batch(request: Request):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    uid = int(user["uid"])
    username = str(user.get("username") or "")
    BATCH_COST = 3
    async with _credits_lock:
        if not is_free_user(uid, username):
            available = USER_CREDITS.get(uid, FREE_QUOTA)
            if available < BATCH_COST:
                return JSONResponse({"error": "no_credits", "required": BATCH_COST, "available": available}, status_code=402)
            USER_CREDITS[uid] -= BATCH_COST
    _credits_save()
    data = await request.json()
    prompt = str(data.get("prompt") or "").strip()
    image_b64 = str(data.get("image_b64") or "").strip()
    preset_key = str(data.get("preset_key") or "")
    if preset_key and not prompt:
        prompt = _resolve_preset_prompt(preset_key) or ""
    image_bytes = _decode_b64_image(image_b64) if image_b64 else None
    if not image_bytes:
        async with _credits_lock:
            USER_CREDITS[uid] = USER_CREDITS.get(uid, 0) + BATCH_COST
        _credits_save()
        return JSONResponse({"error": "invalid image"}, status_code=400)
    ok, _ = assess_selfie_quality(image_bytes)
    if not ok:
        async with _credits_lock:
            USER_CREDITS[uid] = USER_CREDITS.get(uid, 0) + BATCH_COST
        _credits_save()
        return JSONResponse({"error": "selfie_quality"}, status_code=400)
    variations = [
        prompt,
        (prompt + ", slightly different angle, candid") if prompt else "natural light portrait",
        (prompt + ", soft bokeh, warm golden tone") if prompt else "soft bokeh portrait",
        (prompt + ", dramatic lighting, editorial mood") if prompt else "editorial portrait",
    ]
    job_ids = []
    lang = str(data.get("lang") or LANG_DEFAULT)
    for vp in variations:
        job = record_job(kind="webapp_batch", status="queued", chat_id=uid, username=username,
                         prompt=vp, model=INSTANTID_MODEL, image_bytes=image_bytes, lang=lang)
        job_ids.append(str(job["job_id"]))
        asyncio.create_task(run_webapp_generation_job(str(job["job_id"])))
        stats_incr("jobs_created", 1)
    return {"job_ids": job_ids, "status": "queued", "credit_cost": BATCH_COST}

@app.post("/api/v1/generations/{job_id}/hd")
async def api_hd_upscale(job_id: str, request: Request):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    uid = int(user["uid"])
    username = str(user.get("username") or "")
    job = JOBS.get(job_id) or (_db_load_job(job_id) if DB_READY else None)
    if not job:
        return JSONResponse({"error": "not_found"}, status_code=404)
    if int(job.get("chat_id") or 0) != uid:
        return JSONResponse({"error": "forbidden"}, status_code=403)
    if job.get("status") != "ready":
        return JSONResponse({"error": "job_not_ready"}, status_code=400)
    if job.get("hd_job_id"):
        hd = JOBS.get(job["hd_job_id"]) or (_db_load_job(job["hd_job_id"]) if DB_READY else None)
        if hd:
            return public_job_snapshot(hd)
    HD_COST = 2
    async with _credits_lock:
        if not is_free_user(uid, username):
            available = USER_CREDITS.get(uid, FREE_QUOTA)
            if available < HD_COST:
                return JSONResponse({"error": "no_credits", "required": HD_COST}, status_code=402)
            USER_CREDITS[uid] -= HD_COST
    _credits_save()
    hd_job = record_job(kind="webapp_hd", status="queued", chat_id=uid, username=username,
                        prompt=job.get("prompt", ""), model=CODEFORMER_MODEL, parent_job_id=job_id)
    hd_job_id = str(hd_job["job_id"])
    record_job(job_id, hd_job_id=hd_job_id)
    asyncio.create_task(_run_hd_upscale_job(hd_job_id, job_id))
    return {"job_id": hd_job_id, "status": "queued", "credit_cost": HD_COST}

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

@app.get("/api/v1/presets")
async def api_presets(request: Request):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    uid = int(user["uid"])
    unlocked = USER_STYLE_PACKS.get(uid, set())
    age_unlocked = USER_AGE_PACKS.get(uid, False)
    def _thumb_url(key: str) -> str:
        s3_k = PRESET_THUMB_KEYS.get(key)
        if s3_k and S3_BUCKET:
            fresh = s3_presign_key(s3_k)
            if fresh:
                return fresh
        return f"/preset-thumbs/{key}.webp"

    result = []
    for p in PRESETS:
        lang = USER_LANG.get(uid, LANG_DEFAULT)
        label = p.label_en
        if lang == "ru": label = p.label_ru
        elif lang == "ro": label = p.label_ro
        elif lang == "de": label = p.label_de
        result.append({"key": p.key, "label": label, "category": _preset_category(p.key),
                        "is_premium": False, "locked": False, "emoji": getattr(p, "emoji", "✦"),
                        "thumbnail_url": _thumb_url(p.key)})
    for s in PREMIUM_STYLES:
        result.append({"key": s["key"], "label": s["label_en"], "emoji": s.get("emoji","✦"),
                        "category": s["category"], "is_premium": True,
                        "pack_id": s["pack_id"], "locked": s["pack_id"] not in unlocked,
                        "thumbnail_url": _thumb_url(s["key"])})
    for a in AGE_STYLES:
        result.append({"key": a["key"], "label": a["label_en"], "emoji": a.get("emoji","✨"),
                        "category": "age", "is_premium": True,
                        "pack_id": "age_pack", "locked": not age_unlocked,
                        "thumbnail_url": _thumb_url(a["key"])})
    for pack_id, cfg in PRESET_PACKS.items():
        pack_unlocked = pack_id in unlocked
        lang = USER_LANG.get(uid, LANG_DEFAULT)
        for p in cfg["presets"]:
            label = p.get("label_ru", p["label_en"]) if lang == "ru" else p["label_en"]
            result.append({
                "key": p["key"], "label": label, "emoji": p.get("emoji", "✦"),
                "category": cfg["category"], "is_premium": True,
                "pack_id": pack_id, "locked": not pack_unlocked,
                "prompt": p["prompt"],
                "thumbnail_url": _thumb_url(p["key"]),
            })
    # Community presets (top 50 by votes)
    for cp in _load_community_presets_for_api(uid, sort="top", limit=50):
        thumb = s3_presign_key(cp["output_s3_key"]) if cp.get("output_s3_key") else ""
        result.append({
            "key": cp["key"],
            "label": cp["label"],
            "emoji": "✨",
            "category": "community",
            "is_premium": False,
            "locked": False,
            "prompt": cp["prompt"],
            "thumbnail_url": thumb,
            "votes": cp["votes"],
            "creator_name": cp.get("creator_name") or "anonymous",
            "creator_uid": cp["creator_uid"],
            "my_vote": _has_community_vote(uid, cp["key"]),
            "created_at": cp["created_at"],
        })

    trending_keys = [k.strip() for k in TRENDING_PRESETS_ENV.split(",") if k.strip()]
    return {"presets": result, "trending": trending_keys}

@app.get("/api/v1/photoshoot-modes")
async def api_photoshoot_modes(request: Request):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    uid = int(user["uid"])
    lang = USER_LANG.get(uid, LANG_DEFAULT)
    result = []
    for key, cfg in PHOTOSHOOT_MODES.items():
        result.append({
            "key": key,
            "label": cfg["label"].get(lang, cfg["label"].get("en", key)),
            "label_en": cfg["label"].get("en", key),
            "label_ru": cfg["label"].get("ru", key),
            "emoji": cfg.get("emoji", "✦"),
            "credits": cfg["credits"],
            "n_generations": cfg["n_generations"],
            "select_best": cfg["select_best"],
            "upscale": cfg["upscale"],
            "is_premium": cfg.get("is_premium", False),
            "requires_custom_prompt": cfg.get("requires_custom_prompt", False),
            "badge": cfg.get("badge"),
            "short_desc": cfg.get("short_desc", {}).get(lang, cfg.get("short_desc", {}).get("en", "")),
        })
    return {"modes": result}


def _check_admin_auth(request: Request) -> bool:
    """Accept either X-Admin-Secret header OR a TMA-authenticated admin user."""
    secret = request.headers.get("X-Admin-Secret") or request.query_params.get("secret")
    if ADMIN_PANEL_SECRET and secret == ADMIN_PANEL_SECRET:
        return True
    user = webapp_user_from_request(request)
    if user:
        uid = int(user["uid"])
        username = str(user.get("username") or "")
        if "admin.view" in grants_for_user(uid, username):
            return True
    return False


@app.get("/api/v1/admin/dashboard")
async def api_admin_dashboard(request: Request):
    if not _check_admin_auth(request):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    now = time.time()
    users_total = len(STATS_USERS_INFO)
    users_active_24h = sum(1 for u in STATS_USERS_INFO.values() if now - float(u.get("last_seen", 0)) <= 86400)
    users_active_7d  = sum(1 for u in STATS_USERS_INFO.values() if now - float(u.get("last_seen", 0)) <= 7*86400)
    users_online_5m  = sum(1 for u in STATS_USERS_INFO.values() if now - float(u.get("last_seen", 0)) <= 300)

    def sum_daily(keys: List[str], days: int) -> int:
        out = 0
        for d in range(days):
            dk = _date_key(now - d * 86400)
            dm = STATS_DAILY.get(dk) or {}
            for k in keys:
                out += int(dm.get(k, 0))
        return out

    def range_m(days: int) -> Dict[str, int]:
        return {
            "gens": sum_daily(["gens_ok", "gens_copy_ok"], days),
            "payments": sum_daily(["payments"], days),
            "new_users": sum_daily(["new_users"], days),
            "referrals": sum_daily(["referrals"], days),
        }

    day_m   = range_m(1)
    week_m  = range_m(7)
    month_m = range_m(30)

    top_gens = sorted(
        [
            {
                "uid": uid,
                "username": u.get("username") or "",
                "gens": int(u.get("gens_ok", 0)) + int(u.get("gens_copy_ok", 0)),
                "payments": int(u.get("payments", 0)),
                "last_seen": float(u.get("last_seen", 0)),
            }
            for uid, u in STATS_USERS_INFO.items()
        ],
        key=lambda x: x["gens"],
        reverse=True,
    )[:10]

    total_gens = int(STATS.get("gens_ok", 0)) + int(STATS.get("gens_copy_ok", 0))
    total_payments = sum(int(u.get("payments", 0)) for u in STATS_USERS_INFO.values())

    return {
        "users_total": users_total,
        "users_active_24h": users_active_24h,
        "users_active_7d": users_active_7d,
        "users_online_5m": users_online_5m,
        "total_gens": total_gens,
        "total_payments": total_payments,
        "today": day_m,
        "week": week_m,
        "month": month_m,
        "top_gens": top_gens,
        "broadcast_running": bool(_broadcast_running.get("status") == "running"),
        "broadcast_history": BROADCAST_HISTORY[:5],
    }


@app.get("/api/v1/admin/broadcast")
async def api_admin_broadcast_status(request: Request):
    if not _check_admin_auth(request):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    segments = {k: {"desc": v, "size": len(_broadcast_segment_uids(k))} for k, v in BROADCAST_SEGMENTS.items()}
    return {
        "running": _broadcast_running,
        "history": BROADCAST_HISTORY[:20],
        "segments": segments,
    }

@app.post("/api/v1/admin/broadcast")
async def api_admin_broadcast_send(request: Request):
    if not _check_admin_auth(request):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    if _broadcast_running.get("status") == "running":
        return JSONResponse({"error": "campaign_already_running"}, status_code=409)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    segment   = str(body.get("segment", "")).strip()
    message   = str(body.get("message", "")).strip()
    deep_link = str(body.get("deep_link", "")).strip()
    name      = str(body.get("name", segment)).strip()[:80]
    if segment not in BROADCAST_SEGMENTS:
        return JSONResponse({"error": "unknown_segment"}, status_code=400)
    if not message:
        return JSONResponse({"error": "empty_message"}, status_code=400)
    if len(message) > 4000:
        return JSONResponse({"error": "message_too_long"}, status_code=400)
    uids = _broadcast_segment_uids(segment)
    if not uids:
        return JSONResponse({"error": "empty_segment", "size": 0}, status_code=400)
    campaign_id = f"bc_{int(time.time())}_{segment}"
    # Record in history before spawning so it's immediately visible
    BROADCAST_HISTORY.insert(0, {
        "campaign_id": campaign_id,
        "name": name,
        "segment": segment,
        "total": len(uids),
        "sent": 0,
        "failed": 0,
        "blocked": 0,
        "status": "queued",
        "started_at": time.time(),
        "finished_at": None,
    })
    asyncio.create_task(run_broadcast_job(campaign_id, uids, message, deep_link))
    analytics_event(0, "broadcast_started", {"campaign_id": campaign_id, "segment": segment, "size": len(uids)})
    return {"campaign_id": campaign_id, "size": len(uids)}

@app.delete("/api/v1/admin/broadcast")
async def api_admin_broadcast_cancel(request: Request):
    if not _check_admin_auth(request):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    if _broadcast_running.get("status") == "running":
        _broadcast_running["status"] = "cancelled"
        return {"cancelled": True}
    return JSONResponse({"error": "no_active_campaign"}, status_code=404)


def _admin_resolve_user(q: str) -> Optional[int]:
    """Resolve a search query (UID or @username) to a uid, or None."""
    q = q.strip().lstrip("@")
    if q.isdigit():
        uid = int(q)
        return uid if uid in STATS_USERS_INFO or uid in USER_CREDITS else None
    # Search by username (case-insensitive)
    q_lower = q.lower()
    for uid, info in STATS_USERS_INFO.items():
        if (info.get("username") or "").lower() == q_lower:
            return uid
    return None


@app.get("/api/v1/admin/user")
async def api_admin_user_lookup(request: Request):
    if not _check_admin_auth(request):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    q = str(request.query_params.get("q") or "").strip()
    if not q:
        return JSONResponse({"error": "missing_q"}, status_code=400)
    uid = _admin_resolve_user(q)
    if uid is None:
        return JSONResponse({"error": "not_found"}, status_code=404)
    info = STATS_USERS_INFO.get(uid) or {}
    now = time.time()
    last_seen = float(info.get("last_seen", 0))
    first_seen = float(info.get("first_seen", 0))
    return {
        "uid": uid,
        "username": info.get("username") or "",
        "credits": USER_CREDITS.get(uid, 0),
        "plan": USER_SUBSCRIPTION.get(uid, {}).get("plan", "free"),
        "streak": USER_STREAK.get(uid, 0),
        "gens_ok": int(info.get("gens_ok", 0)),
        "payments": int(info.get("payments", 0)),
        "language": USER_LANG.get(uid, LANG_DEFAULT),
        "unlocked_packs": sorted(USER_STYLE_PACKS.get(uid, set())),
        "last_seen": last_seen,
        "last_seen_ago": f"{int((now - last_seen) // 3600)}h ago" if last_seen else "never",
        "first_seen": first_seen,
        "blocked": bool(NUDGE_INFO.get(uid, {}).get("blocked")),
        "is_free": is_free_user(uid),
    }


@app.post("/api/v1/admin/user/credits")
async def api_admin_user_credits(request: Request):
    if not _check_admin_auth(request):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    uid = int(body.get("uid", 0))
    delta = int(body.get("delta", 0))
    reason = str(body.get("reason", "admin_grant"))[:80]
    if not uid or delta == 0:
        return JSONResponse({"error": "bad_params"}, status_code=400)
    ensure_user_credit(uid)
    async with _credits_lock:
        before = USER_CREDITS.get(uid, 0)
        USER_CREDITS[uid] = max(0, before + delta)
        after = USER_CREDITS[uid]
    _credits_save()
    analytics_event(uid, "admin_credit_grant", {"delta": delta, "before": before, "after": after, "reason": reason})
    log_event("admin_credit_grant", uid=uid, delta=delta, reason=reason)
    return {"uid": uid, "before": before, "after": after, "delta": delta}


@app.post("/api/v1/admin/user/message")
async def api_admin_user_message(request: Request):
    if not _check_admin_auth(request):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    try:
        body = await request.json()
    except Exception:
        return JSONResponse({"error": "invalid_json"}, status_code=400)
    uid = int(body.get("uid", 0))
    text = str(body.get("text", "")).strip()[:1000]
    if not uid or not text:
        return JSONResponse({"error": "bad_params"}, status_code=400)
    try:
        await bot.send_message(uid, text)
        analytics_event(uid, "admin_message_sent", {"text_len": len(text)})
        return {"sent": True}
    except (TelegramForbiddenError, TelegramNotFound):
        return JSONResponse({"error": "user_blocked_bot"}, status_code=422)
    except Exception as e:
        return JSONResponse({"error": str(e)[:120]}, status_code=500)


@app.post("/api/v1/admin/generate-preset-thumbs")
async def api_admin_generate_preset_thumbs(request: Request):
    if not _check_admin_auth(request):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    try:
        body = await request.json()
    except Exception:
        body = {}
    reference_url = str(body.get("reference_url") or "").strip()
    if not reference_url:
        # Default: royalty-free Unsplash portrait (Creative Commons)
        reference_url = "https://images.unsplash.com/photo-1524504388940-b1c1722653e1?w=800&q=80"

    thumbs_dir = _PRESET_THUMBS_DIR  # persistent data dir, survives npm run build

    loop = asyncio.get_running_loop()

    try:
        ref_bytes = await loop.run_in_executor(
            None, lambda: requests.get(reference_url, timeout=30).content
        )
    except Exception as exc:
        return JSONResponse({"error": f"reference_download_failed: {exc}"}, status_code=400)

    if not ref_bytes or len(ref_bytes) < 1000:
        return JSONResponse({"error": "reference_photo_too_small"}, status_code=400)

    async def _gen_all_thumbs():
        _loop = asyncio.get_running_loop()
        for _p in PRESETS:
            _key = _p.key
            _prompt = _p.prompt
            try:
                result = await _loop.run_in_executor(
                    None,
                    lambda p=_prompt, rb=ref_bytes: generate_image_from_bytes(rb, p, lang="en")
                )
                if result:
                    path = os.path.join(thumbs_dir, f"{_key}.webp")
                    with open(path, "wb") as fh:
                        fh.write(result)
                    print(f"✅ thumb saved: {_key} ({len(result)} bytes)")
                    s3_key = f"preset-thumbs/{_key}.webp"
                    if s3_put_at_key(result, s3_key, content_type="image/webp"):
                        PRESET_THUMB_KEYS[_key] = s3_key
                        print(f"✅ thumb uploaded to S3: {s3_key}")
            except Exception as exc:
                print(f"⚠️ thumb failed: {_key}: {exc}")
        try:
            with open(_PRESET_THUMB_CONFIG, "w") as _f:
                json.dump(PRESET_THUMB_KEYS, _f, indent=2, sort_keys=True)
            print(f"✅ preset-thumbs.json updated ({len(PRESET_THUMB_KEYS)} entries)")
        except Exception as _e:
            print(f"preset-thumbs.json write error: {_e}")

    asyncio.create_task(_gen_all_thumbs())
    return {"queued": len(PRESETS), "keys": [p.key for p in PRESETS]}


@app.get("/api/v1/admin/preset-thumbs-status")
async def api_admin_preset_thumbs_status(request: Request):
    """Return the current in-memory PRESET_THUMB_KEYS mapping.
    Pipe the response body into preset-thumbs.json locally and commit."""
    if not _check_admin_auth(request):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    return JSONResponse(
        {"done": len(PRESET_THUMB_KEYS), "total": len(PRESETS), "keys": PRESET_THUMB_KEYS},
        status_code=200,
    )


@app.get("/api/v1/admin/debug-stats")
async def api_admin_debug_stats(request: Request):
    """Raw diagnostics: DB row counts + in-memory state. Use to verify data survived restarts."""
    if not _check_admin_auth(request):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    loop = asyncio.get_running_loop()
    def _query():
        db_totals = _db_load_stats_totals()
        db_users_count = len(_db_load_users())
        db_daily_days = len(_db_load_stats_daily())
        db_credits_count = len(_db_load_credits())
        return db_totals, db_users_count, db_daily_days, db_credits_count
    try:
        db_totals, db_users_count, db_daily_days, db_credits_count = await loop.run_in_executor(None, _query)
    except Exception as e:
        db_totals, db_users_count, db_daily_days, db_credits_count = {}, 0, 0, 0
    return {
        "db_ready": DB_READY,
        "db": {
            "users_rows": db_users_count,
            "stats_totals_rows": len(db_totals),
            "stats_daily_days": db_daily_days,
            "credits_rows": db_credits_count,
            "gens_ok": db_totals.get("gens_ok", 0),
            "gens_copy_ok": db_totals.get("gens_copy_ok", 0),
            "payments": db_totals.get("payments", 0),
        },
        "memory": {
            "users": len(STATS_USERS_INFO),
            "credits_loaded": len(USER_CREDITS),
            "stats_daily_days": len(STATS_DAILY),
            "gens_ok": STATS.get("gens_ok", 0),
            "gens_copy_ok": STATS.get("gens_copy_ok", 0),
            "payments": STATS.get("payments", 0),
            "top_users": sorted(
                [{"uid": uid, "username": u.get("username",""), "gens": int(u.get("gens_ok",0))+int(u.get("gens_copy_ok",0)), "payments": int(u.get("payments",0))}
                 for uid, u in STATS_USERS_INFO.items()],
                key=lambda x: x["gens"], reverse=True
            )[:20],
        },
        "s3_state": USE_S3_STATE,
    }


@app.get("/api/v1/admin/debug-gallery")
async def api_admin_debug_gallery(request: Request):
    """Gallery diagnostics: DB row counts + latest items without exposing presigned URLs."""
    if not _check_admin_auth(request):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    db_total = 0
    latest_rows: List[Dict[str, Any]] = []
    if DB_READY:
        rows = _db_fetchall(
            "SELECT job_id, chat_id, username, prompt, status, created_at, result_json "
            "FROM imodel_jobs WHERE status='ready' ORDER BY updated_at DESC LIMIT 20"
        )
        db_total_rows = _db_fetchall("SELECT COUNT(*) FROM imodel_jobs WHERE status='ready'")
        db_total = int(db_total_rows[0][0]) if db_total_rows else 0
        for row in rows:
            job_id, chat_id, username, prompt, status, created_at, result_json_str = row
            try:
                rj = json.loads(result_json_str or "{}")
            except Exception:
                rj = {}
            latest_rows.append({
                "job_id": str(job_id),
                "chat_id": int(chat_id) if chat_id else None,
                "username": str(username or ""),
                "prompt": str(prompt or "")[:80],
                "photoshoot_mode": rj.get("photoshoot_mode") or rj.get("mode") or "everyday",
                "has_s3_key": bool(rj.get("output_s3_key")),
                "s3_key": str(rj.get("output_s3_key") or ""),
                "created_at": float(created_at or 0),
            })
    cache_count = len([j for j in _cache_load_jobs() if j.get("status") == "ready"])
    return {
        "db_ready": DB_READY,
        "db_total_ready_jobs": db_total,
        "cache_ready_jobs": cache_count,
        "latest_20": latest_rows,
        "s3_state": USE_S3_STATE,
    }


@app.get("/api/v1/shop")
async def api_shop(request: Request):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    uid = int(user["uid"])
    sub = get_active_sub(uid)
    unlocked = sorted(USER_STYLE_PACKS.get(uid, set()))
    age_unlocked = USER_AGE_PACKS.get(uid, False)
    return {
        "packs": [
            {"id": "pack_10",  "credits": 10,  "stars": 199,  "label": "10 фото",  "badge": None},
            {"id": "pack_30",  "credits": 30,  "stars": 490,  "label": "30 фото",  "badge": "⭐ Popular"},
            {"id": "pack_100", "credits": 100, "stars": 1290, "label": "100 фото", "badge": "−35%"},
            {"id": "pack_300", "credits": 300, "stars": 2990, "label": "300 фото", "badge": "−50%"},
        ],
        "subscriptions": [
            {"id": "sub_weekly", "plan": "weekly", "stars": SUB_WEEKLY_STARS,
             "credits": SUB_WEEKLY_CREDITS, "period": "week",
             "active": bool(sub and sub.get("plan") == "weekly")},
            {"id": "sub_pro",   "plan": "pro",    "stars": SUB_PRO_STARS,
             "credits": SUB_PRO_CREDITS,   "period": "month",
             "active": bool(sub and sub.get("plan") == "pro")},
            {"id": "sub_creator", "plan": "creator", "stars": SUB_CREATOR_STARS,
             "credits": SUB_CREATOR_CREDITS, "period": "month",
             "active": bool(sub and sub.get("plan") == "creator")},
            {"id": "sub_elite", "plan": "elite",  "stars": SUB_ELITE_STARS,
             "credits": SUB_ELITE_CREDITS, "period": "month",
             "active": bool(sub and sub.get("plan") == "elite")},
        ],
        "style_packs": [
            {"id": "premium_pack_1", "label": "Premium Collection",
             "styles_count": 15, "stars": STYLE_PACK_STARS, "unlocked": "premium_pack_1" in unlocked},
            {"id": "age_pack", "label": "Age Magic",
             "styles_count": 4,  "stars": AGE_PACK_STARS,   "unlocked": age_unlocked},
        ],
        "preset_packs": [
            {
                "id": pack_id,
                "label": cfg["label_en"],
                "emoji": cfg["emoji"],
                "presets_count": len(cfg["presets"]),
                "stars": cfg["stars"],
                "unlocked": pack_id in unlocked,
            }
            for pack_id, cfg in PRESET_PACKS.items()
        ],
        "unlocked_packs": unlocked,
        "subscription": sub,
        "credits": USER_CREDITS.get(uid, 0),
        "banner": SHOP_BANNER or None,
        "subscription_features": {
            "free":    ["5 free gens/day", "All basic styles", "Standard quality"],
            "weekly":  [f"{SUB_WEEKLY_CREDITS} gens/week", "All basic styles", "Standard quality", "Priority queue"],
            "pro":     [f"{SUB_PRO_CREDITS} gens/month", "All styles unlocked", "HD upscale included", "Priority queue", "Batch ×4"],
            "creator": [f"{SUB_CREATOR_CREDITS} gens/month", "All styles + packs", "HD upscale included", "Priority queue", "Batch ×4", "Style packs included"],
            "elite":   [f"{SUB_ELITE_CREDITS} gens/month", "All styles + packs", "4K HD upscale", "Priority queue", "Batch ×4", "Early access"],
        },
    }

@app.post("/api/v1/shop/invoice")
async def api_shop_invoice(request: Request):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    data = await request.json()
    item_id = str(data.get("item_id") or "")
    ITEMS = {
        "pack_10":        ("iModel — 10 Generations", "10 AI portrait generations", 199, False),
        "pack_30":        ("iModel — 30 Generations", "30 AI portrait generations (Save 18%)", 490, False),
        "pack_100":       ("iModel — 100 Generations","100 AI portrait generations (Save 35%)", 1290, False),
        "pack_300":       ("iModel — 300 Generations","300 AI portrait generations (Save 50%)", 2990, False),
        "sub_weekly":     ("iModel Weekly Pro", f"{SUB_WEEKLY_CREDITS} gens/week, auto-renewal", SUB_WEEKLY_STARS, True),
        "sub_pro":        ("iModel Pro", f"{SUB_PRO_CREDITS} gens/month, auto-renewal", SUB_PRO_STARS, True),
        "sub_creator":    ("iModel Creator", f"{SUB_CREATOR_CREDITS} gens/month, auto-renewal", SUB_CREATOR_STARS, True),
        "sub_elite":      ("iModel Elite", f"{SUB_ELITE_CREDITS} gens/month, auto-renewal", SUB_ELITE_STARS, True),
        "premium_pack_1": ("iModel Premium Styles", "15 exclusive artistic style presets", STYLE_PACK_STARS, False),
        "age_pack":       ("iModel Age Magic", "4 age transformation styles", AGE_PACK_STARS, False),
        "viral_pack":     ("iModel Viral Social Pack", "6 trending social media aesthetic presets", VIRAL_PACK_STARS, False),
        "locations_pack": ("iModel World Locations Pack", "6 exotic travel location presets", LOCATIONS_PACK_STARS, False),
        "fantasy_pack":   ("iModel Fantasy & Sci-Fi Pack", "6 fantasy and sci-fi scene presets", FANTASY_PACK_STARS, False),
    }
    if item_id not in ITEMS:
        return JSONResponse({"error": "invalid_item"}, status_code=400)
    title, description, stars, is_sub = ITEMS[item_id]
    prices = [LabeledPrice(label=title, amount=stars)]
    kwargs: Dict[str, Any] = dict(
        title=title, description=description, payload=item_id,
        provider_token="", currency="XTR", prices=prices,
    )
    if is_sub:
        period = SUB_WEEKLY_PERIOD if item_id == "sub_weekly" else SUB_PERIOD
        kwargs["subscription_period"] = period
    try:
        invoice_url = await bot.create_invoice_link(**kwargs)
        return {"invoice_url": invoice_url}
    except Exception as e:
        print(f"[shop invoice] error: {e}")
        return JSONResponse({"error": "invoice_failed", "detail": str(e)[:200]}, status_code=500)

@app.post("/api/v1/style-packs/unlock")
async def api_unlock_style_pack(request: Request):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    data = await request.json()
    pack_id = str(data.get("pack_id") or "")
    uid = int(user["uid"])
    if pack_id == "premium_pack_1":
        USER_STYLE_PACKS.setdefault(uid, set()).add("premium_pack_1")
        _style_packs_save()
        return {"unlocked": pack_id, "all_packs": sorted(USER_STYLE_PACKS.get(uid, set()))}
    elif pack_id == "age_pack":
        USER_AGE_PACKS[uid] = True
        _style_packs_save()
        return {"unlocked": pack_id}
    return JSONResponse({"error": "invalid_pack"}, status_code=400)

@app.post("/api/v1/profile/daily")
async def api_claim_daily(request: Request):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    uid = int(user["uid"])
    if is_free_user(uid, str(user.get("username") or "")):
        return JSONResponse({"error": "free_user"}, status_code=400)
    async with _credits_lock:
        result = _claim_daily_bonus(uid)
    if result is None:
        last = USER_LAST_BONUS.get(uid, 0)
        next_at = int(last + DAILY_WINDOW)
        return JSONResponse({"error": "already_claimed", "next_at": next_at}, status_code=400)
    gens_added, streak, milestone_bonus = result
    return {"gens_added": gens_added, "streak": streak, "credits": USER_CREDITS.get(uid, 0), "milestone_bonus": milestone_bonus}

@app.get("/api/v1/profile/challenge")
async def api_daily_challenge(request: Request):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    import hashlib as _hl, datetime as _dt
    day_key = _dt.date.today().isoformat()
    idx = int(_hl.md5(day_key.encode()).hexdigest(), 16) % len(PRESETS)
    p = PRESETS[idx]
    uid = int(user["uid"])
    lang = USER_LANG.get(uid, LANG_DEFAULT)
    label = p.label_ru if lang == "ru" else p.label_en
    # Count how many unique users started the challenge preset today
    participants_today = sum(
        1 for _ui in STATS_USERS_INFO.values()
        if str(_ui.get("challenge_date", "")) == day_key
    )
    return {
        "preset_key": p.key,
        "label": label,
        "bonus_credits": CHALLENGE_BONUS_CREDITS,
        "date": day_key,
        "participants_today": max(participants_today, random.randint(40, 120)),  # floor for social proof
    }

@app.get("/api/v1/profile/stats")
async def api_profile_stats(request: Request):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    uid = int(user["uid"])
    info = STATS_USERS_INFO.get(uid, {})
    ref_stats = REF_STATS.get(uid, {"count": 0, "earned": 0})
    streak = USER_STREAK.get(uid, 0)
    last_bonus = USER_LAST_BONUS.get(uid, 0)
    can_claim = (time.time() - last_bonus) >= DAILY_WINDOW and not is_free_user(uid, str(user.get("username") or ""))
    next_at = int(last_bonus + DAILY_WINDOW) if not can_claim else None
    return {
        "total_photos": int(info.get("gens_ok", 0)),
        "streak": streak,
        "referrals": ref_stats.get("count", 0),
        "referrals_earned": ref_stats.get("earned", 0),
        "can_claim_daily": can_claim,
        "next_daily_at": next_at,
        "subscription": get_active_sub(uid),
        "credits": USER_CREDITS.get(uid, 0),
        "username": info.get("username", ""),
    }

@app.post("/api/v1/analytics/event")
async def api_analytics_event(request: Request):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    uid = int(user["uid"])
    try:
        data = await request.json()
        event = str(data.get("event") or "").strip()[:64]
        props = dict(data.get("props") or {})
        if not event:
            return JSONResponse({"error": "event required"}, status_code=400)
        props["source"] = "webapp"
        analytics_event(uid, event, props)
        _check_and_unlock_achievements(uid)
    except Exception:
        pass
    return {"ok": True}

@app.get("/api/v1/analytics/funnel")
async def api_analytics_funnel(request: Request):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    # Only admins
    uid = int(user["uid"])
    username = str(user.get("username") or "")
    if role_for_user(uid, username) not in ("admin", "superadmin"):
        return JSONResponse({"error": "forbidden"}, status_code=403)
    days = int(request.query_params.get("days", 7))
    days = max(1, min(days, 90))
    return _analytics_funnel_counts(days)

def _quest_progress_for_user(uid: int, today: str) -> List[Dict]:
    """Return quests with current progress for a user."""
    import datetime as _dt
    ui = STATS_USERS_INFO.get(uid) or {}
    streak = USER_STREAK.get(uid, 0)
    total_gens = int(ui.get("gens_ok", 0)) + int(ui.get("gens_copy_ok", 0))
    invites = int((STATS_USERS_INFO.get(uid) or {}).get("referrals_sent", 0))
    claimed = USER_QUEST_CLAIMED.get(uid, {})
    progress = USER_QUEST_PROGRESS.get(uid, {})
    result = []
    for q in QUESTS_CONFIG:
        qid = q["id"]
        qtype = q["type"]
        # For daily quests, progress resets each day
        if qtype == "daily":
            prog_key = f"{qid}:{today}"
            current = int(progress.get(prog_key, 0))
            claimed_today = claimed.get(qid) == today
        elif qtype == "milestone":
            # milestone: based on streak
            if qid == "streak_7":
                current = min(streak, q["target"])
            else:
                current = 0
            claimed_today = qid in claimed
        else:  # lifetime
            if qid == "gen_50":
                current = min(total_gens, q["target"])
            elif qid == "invite_1":
                current = min(invites, q["target"])
            else:
                current = 0
            claimed_today = qid in claimed
        result.append({
            "id": qid,
            "title": q["title"],
            "icon": q["icon"],
            "type": qtype,
            "target": q["target"],
            "progress": current,
            "reward": q["reward"],
            "claimable": current >= q["target"] and not claimed_today,
            "claimed": bool(claimed_today),
        })
    return result


@app.get("/api/v1/quests")
async def api_quests(request: Request):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    uid = int(user["uid"])
    import datetime as _dt
    today = _dt.date.today().isoformat()
    quests = _quest_progress_for_user(uid, today)
    claimable = sum(1 for q in quests if q["claimable"])
    return {"quests": quests, "claimable": claimable}


@app.post("/api/v1/quests/{quest_id}/claim")
async def api_quest_claim(quest_id: str, request: Request):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    uid = int(user["uid"])
    import datetime as _dt
    today = _dt.date.today().isoformat()
    # For home screen quest, grant progress server-side on claim (no JS hook needed)
    if quest_id == "add_to_home_screen":
        USER_QUEST_PROGRESS.setdefault(uid, {})["add_to_home_screen"] = 1
    async with _credits_lock:
        quests = _quest_progress_for_user(uid, today)
        quest = next((q for q in quests if q["id"] == quest_id), None)
        if not quest:
            return JSONResponse({"error": "quest_not_found"}, status_code=404)
        if not quest["claimable"]:
            return JSONResponse({"error": "not_claimable"}, status_code=400)
        # Mark claimed atomically before granting
        if uid not in USER_QUEST_CLAIMED:
            USER_QUEST_CLAIMED[uid] = {}
        USER_QUEST_CLAIMED[uid][quest_id] = today
        # Grant reward
        reward = quest["reward"]
        USER_CREDITS[uid] = int(USER_CREDITS.get(uid, 0)) + reward
    analytics_event(uid, "quest_claimed", {"quest_id": quest_id, "reward": reward})
    # Persist claimed state to DB so it survives restarts
    _db_save_quest(
        uid, quest_id, 0, today,
        json.dumps(USER_QUEST_PROGRESS.get(uid, {}), ensure_ascii=False)
    )
    # Check achievements after claiming
    _check_and_unlock_achievements(uid)
    return {"ok": True, "credits_added": reward, "new_balance": USER_CREDITS.get(uid, 0)}


def _check_and_unlock_achievements(uid: int) -> List[str]:
    """Check all achievements and unlock newly earned ones. Returns list of newly unlocked ids."""
    ui = STATS_USERS_INFO.get(uid) or {}
    streak = USER_STREAK.get(uid, 0)
    total_gens = int(ui.get("gens_ok", 0)) + int(ui.get("gens_copy_ok", 0))
    invites = int(ui.get("referrals_sent", 0))
    payments = int(ui.get("payments", 0))
    presets_used_count = len(ui.get("presets_used", []) if isinstance(ui.get("presets_used"), list) else [])
    unlocked = USER_ACHIEVEMENTS.setdefault(uid, {})
    newly = []
    checks = {
        "first_gen":   total_gens >= 1,
        "gen_10":      total_gens >= 10,
        "gen_50":      total_gens >= 50,
        "gen_100":     total_gens >= 100,
        "streak_7":    streak >= 7,
        "streak_30":   streak >= 30,
        "invited_1":   invites >= 1,
        "invited_5":   invites >= 5,
        "paid_user":   payments >= 1,
        "all_presets": presets_used_count >= 10,
    }
    for ach_id, earned in checks.items():
        if earned and ach_id not in unlocked:
            unlocked[ach_id] = time.time()
            newly.append(ach_id)
    return newly


@app.get("/api/v1/achievements")
async def api_achievements(request: Request):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    uid = int(user["uid"])
    unlocked = USER_ACHIEVEMENTS.get(uid, {})
    result = []
    for a in ACHIEVEMENTS_CONFIG:
        result.append({
            "id": a["id"],
            "title": a["title"],
            "icon": a["icon"],
            "desc": a["desc"],
            "unlocked": a["id"] in unlocked,
            "unlocked_at": unlocked.get(a["id"]),
        })
    newly_unlocked = _check_and_unlock_achievements(uid)
    return {"achievements": result, "newly_unlocked": newly_unlocked}


def _quest_incr_daily(uid: int, quest_id: str, today: str, n: int = 1):
    """Increment a daily quest counter for a user."""
    if uid not in USER_QUEST_PROGRESS:
        USER_QUEST_PROGRESS[uid] = {}
    key = f"{quest_id}:{today}"
    USER_QUEST_PROGRESS[uid][key] = int(USER_QUEST_PROGRESS[uid].get(key, 0)) + n


@app.get("/api/v1/referral")
async def api_referral(request: Request):
    user = webapp_user_from_request(request)
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=403)
    uid = int(user["uid"])
    if not BOT_USERNAME_GLOBAL:
        return JSONResponse({"error": "bot_not_ready"}, status_code=503)
    st = REF_STATS.get(uid, {"count": 0, "earned": 0})
    count = int(st.get("count", 0))
    earned = int(st.get("earned", 0))
    link = f"https://t.me/{BOT_USERNAME_GLOBAL}?start=ref_{uid}"
    # Next milestone
    next_ms = next((n for n in sorted(REFERRAL_MILESTONES) if n > count), None)
    milestones = [
        {"count": n, "bonus": b, "reached": count >= n}
        for n, b in sorted(REFERRAL_MILESTONES.items())
    ]
    return {
        "link": link,
        "invited_count": count,
        "credits_earned": earned,
        "bonus_per_invite": REF_BONUS_REF,
        "bonus_for_new": REF_BONUS_NEW,
        "next_milestone": next_ms,
        "next_milestone_bonus": REFERRAL_MILESTONES.get(next_ms, 0) if next_ms else 0,
        "milestones": milestones,
    }

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

def _admin_user_lookup_section() -> str:
    """User lookup & credit grant section for the admin panel."""
    return """
      <div class="section">
        <div class="card">
          <div class="muted" style="margin-bottom:10px">User Lookup &amp; Credit Grant</div>
          <div style="display:flex;gap:8px;margin-bottom:12px">
            <input id="ul_q" placeholder="UID or @username" style="flex:1;background:#1b2030;border:1px solid #2a3556;border-radius:6px;color:#e6edf3;padding:6px 10px;font-size:13px">
            <button onclick="ulLookup()" style="padding:6px 16px;background:var(--accent);border:none;border-radius:6px;color:#fff;cursor:pointer;font-size:13px">Search</button>
          </div>
          <div id="ul_result"></div>
        </div>
      </div>
      <script>
      async function ulLookup() {
        const q = document.getElementById('ul_q').value.trim();
        if (!q) return;
        const res = document.getElementById('ul_result');
        res.innerHTML = '<span class="muted">Searching…</span>';
        try {
          const r = await fetch('/api/v1/admin/user?q=' + encodeURIComponent(q) + '&secret=' + encodeURIComponent(ADMIN_SECRET));
          if (!r.ok) { res.innerHTML = '<span style="color:#e56565">Not found</span>'; return; }
          const u = await r.json();
          const plan_color = u.plan === 'free' ? '#9aa4b2' : '#ffd700';
          res.innerHTML = `
            <div style="background:#131a2b;border:1px solid #2a3556;border-radius:8px;padding:12px 14px;margin-bottom:10px">
              <div style="display:flex;align-items:center;gap:10px;margin-bottom:8px">
                <span style="font-size:16px;font-weight:700;color:#e6edf3">@${u.username || '—'}</span>
                <span class="muted">UID: ${u.uid}</span>
                <span style="color:${plan_color};font-size:11px;font-weight:600;background:${plan_color}22;padding:2px 7px;border-radius:10px">${u.plan.toUpperCase()}</span>
                ${u.blocked ? '<span style="color:#e56565;font-size:11px">🚫 blocked bot</span>' : ''}
              </div>
              <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-bottom:10px">
                <div style="background:#1b2030;border-radius:6px;padding:8px;text-align:center">
                  <div style="font-size:18px;font-weight:700;color:var(--accent)">${u.credits}</div>
                  <div class="muted" style="font-size:10px">Credits</div>
                </div>
                <div style="background:#1b2030;border-radius:6px;padding:8px;text-align:center">
                  <div style="font-size:18px;font-weight:700;color:#ffd700">${u.gens_ok}</div>
                  <div class="muted" style="font-size:10px">Gens</div>
                </div>
                <div style="background:#1b2030;border-radius:6px;padding:8px;text-align:center">
                  <div style="font-size:18px;font-weight:700;color:#24c38b">${u.payments}</div>
                  <div class="muted" style="font-size:10px">Payments</div>
                </div>
                <div style="background:#1b2030;border-radius:6px;padding:8px;text-align:center">
                  <div style="font-size:18px;font-weight:700;color:#ff9500">${u.streak}</div>
                  <div class="muted" style="font-size:10px">Streak</div>
                </div>
              </div>
              <div class="muted" style="font-size:11px;margin-bottom:10px">
                Lang: ${u.language} &nbsp;·&nbsp; Last seen: ${u.last_seen_ago}
                ${u.unlocked_packs.length ? ' &nbsp;·&nbsp; Packs: ' + u.unlocked_packs.join(', ') : ''}
              </div>
              <div style="display:flex;gap:6px;flex-wrap:wrap;margin-bottom:8px">
                ${[-10,-5,5,10,25,50].map(d =>
                  `<button onclick="ulCredits(${u.uid},${d})" style="padding:4px 10px;background:${d>0?'#24c38b22':'#e5656522'};border:1px solid ${d>0?'#24c38b55':'#e5656555'};border-radius:5px;color:${d>0?'#24c38b':'#e56565'};cursor:pointer;font-size:12px">${d>0?'+':''}${d}⚡</button>`
                ).join('')}
                <button onclick="ulCreditsCustom(${u.uid})" style="padding:4px 10px;background:#7aa2f722;border:1px solid #7aa2f755;border-radius:5px;color:#7aa2f7;cursor:pointer;font-size:12px">Custom</button>
              </div>
              <div style="display:flex;gap:6px">
                <input id="ul_msg_${u.uid}" placeholder="Send message to user…" style="flex:1;background:#1b2030;border:1px solid #2a3556;border-radius:5px;color:#e6edf3;padding:5px 8px;font-size:12px">
                <button onclick="ulMsg(${u.uid})" style="padding:4px 12px;background:#7aa2f722;border:1px solid #7aa2f755;border-radius:5px;color:#7aa2f7;cursor:pointer;font-size:12px">Send</button>
              </div>
              <div id="ul_action_${u.uid}" style="font-size:12px;margin-top:6px;min-height:16px"></div>
            </div>`;
        } catch(e) { res.innerHTML = '<span style="color:#e56565">Error: ' + e.message + '</span>'; }
      }
      document.getElementById('ul_q').addEventListener('keydown', e => { if(e.key==='Enter') ulLookup(); });

      async function ulCredits(uid, delta) {
        const reason = delta < 0 ? 'admin_deduct' : 'admin_grant';
        const r = await fetch('/api/v1/admin/user/credits?secret=' + encodeURIComponent(ADMIN_SECRET), {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({uid, delta, reason})
        });
        const d = await r.json();
        const el = document.getElementById('ul_action_' + uid);
        if (r.ok) el.innerHTML = `<span style="color:#24c38b">✓ Credits updated: ${d.before} → ${d.after}</span>`;
        else el.innerHTML = `<span style="color:#e56565">Error: ${d.error}</span>`;
      }
      async function ulCreditsCustom(uid) {
        const raw = prompt('Enter credit delta (e.g. +50 or -10):');
        if (!raw) return;
        const delta = parseInt(raw.replace(/^\\+/, ''), 10);
        if (isNaN(delta) || delta === 0) return alert('Invalid delta');
        await ulCredits(uid, delta);
      }
      async function ulMsg(uid) {
        const text = document.getElementById('ul_msg_' + uid).value.trim();
        if (!text) return;
        const r = await fetch('/api/v1/admin/user/message?secret=' + encodeURIComponent(ADMIN_SECRET), {
          method:'POST', headers:{'Content-Type':'application/json'},
          body: JSON.stringify({uid, text})
        });
        const d = await r.json();
        const el = document.getElementById('ul_action_' + uid);
        if (r.ok) el.innerHTML = '<span style="color:#24c38b">✓ Message sent</span>';
        else el.innerHTML = `<span style="color:#e56565">Error: ${d.error}</span>`;
      }
      </script>"""


def _admin_broadcast_section() -> str:
    """Broadcast campaign launcher + history table."""
    now = time.time()
    running = _broadcast_running
    status_block = ""
    if running.get("status") == "running":
        pct = int(100 * running.get("sent", 0) / max(running.get("total", 1), 1))
        status_block = (
            f'<div style="background:#1a2a1a;border:1px solid #2a4a2a;border-radius:8px;padding:10px 14px;margin-bottom:12px;">'
            f'<b style="color:#24c38b">▶ Running:</b> {html_lib.escape(running.get("campaign_id",""))} &nbsp;'
            f'Sent {running.get("sent",0)}/{running.get("total",0)} ({pct}%) · '
            f'Failed {running.get("failed",0)} · Blocked {running.get("blocked",0)}'
            f'&nbsp;<button onclick="cancelCampaign()" style="margin-left:12px;padding:2px 10px;background:#e56565;border:none;border-radius:4px;color:#fff;cursor:pointer">Cancel</button>'
            f'</div>'
        )

    history_rows = ""
    for c in BROADCAST_HISTORY[:10]:
        started = c.get("started_at", 0)
        age = int(now - started) if started else 0
        age_str = f"{age//3600}h {(age%3600)//60}m ago" if age > 3600 else f"{age//60}m ago"
        st = c.get("status", "")
        st_color = "#24c38b" if st == "done" else ("#7aa2f7" if st == "running" else "#9aa4b2")
        history_rows += (
            f'<tr>'
            f'<td>{html_lib.escape(c.get("name") or c.get("campaign_id",""))}</td>'
            f'<td>{html_lib.escape(c.get("segment",""))}</td>'
            f'<td style="color:{st_color}">{html_lib.escape(st)}</td>'
            f'<td>{c.get("sent",0)}/{c.get("total",0)}</td>'
            f'<td>{c.get("failed",0)}</td>'
            f'<td>{c.get("blocked",0)}</td>'
            f'<td>{age_str}</td>'
            f'</tr>'
        )

    seg_opts = "".join(
        f'<option value="{k}">{html_lib.escape(v)}</option>'
        for k, v in BROADCAST_SEGMENTS.items()
    )
    seg_sizes = {k: len(_broadcast_segment_uids(k)) for k in BROADCAST_SEGMENTS}
    seg_size_json = json.dumps(seg_sizes)

    return f"""
<div class="section">
  <div class="card">
    <div class="muted" style="font-weight:600;font-size:13px;margin-bottom:10px">📣 Broadcast Campaigns</div>
    {status_block}
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px;">
      <div>
        <div class="muted" style="margin-bottom:8px">Send Campaign</div>
        <label style="display:block;margin-bottom:6px;font-size:13px">Segment
          <select id="bc_seg" onchange="updateSegSize()" style="width:100%;margin-top:4px;background:#1b2030;border:1px solid #2a3556;border-radius:6px;color:#e6edf3;padding:6px 8px;">
            {seg_opts}
          </select>
        </label>
        <div id="bc_seg_size" style="font-size:12px;color:#7aa2f7;margin-bottom:8px;">— users</div>
        <label style="display:block;margin-bottom:6px;font-size:13px">Campaign name (optional)
          <input id="bc_name" style="width:100%;margin-top:4px;background:#1b2030;border:1px solid #2a3556;border-radius:6px;color:#e6edf3;padding:6px 8px;" placeholder="e.g. June win-back">
        </label>
        <label style="display:block;margin-bottom:6px;font-size:13px">Deep link (optional — appended to message)
          <input id="bc_link" style="width:100%;margin-top:4px;background:#1b2030;border:1px solid #2a3556;border-radius:6px;color:#e6edf3;padding:6px 8px;" placeholder="https://t.me/your_bot?start=...">
        </label>
      </div>
      <div>
        <label style="display:block;margin-bottom:6px;font-size:13px">Message
          <textarea id="bc_msg" rows="7" style="width:100%;margin-top:4px;background:#1b2030;border:1px solid #2a3556;border-radius:6px;color:#e6edf3;padding:6px 8px;resize:vertical;" placeholder="Hey! Your AI photos are waiting... 📸"></textarea>
        </label>
        <button onclick="sendCampaign()" style="width:100%;padding:8px;background:#6c47ff;border:none;border-radius:8px;color:#fff;font-weight:600;cursor:pointer;font-size:14px;">Send Campaign</button>
        <div id="bc_result" style="font-size:12px;margin-top:8px;color:#9aa4b2;"></div>
      </div>
    </div>
    {'<table style="margin-top:16px"><tr><th>Name</th><th>Segment</th><th>Status</th><th>Sent</th><th>Failed</th><th>Blocked</th><th>When</th></tr>' + history_rows + '</table>' if history_rows else ''}
  </div>
</div>
<script>
const SEG_SIZES = {seg_size_json};
const ADMIN_SECRET = new URLSearchParams(location.search).get('secret') || '';
function updateSegSize() {{
  const seg = document.getElementById('bc_seg').value;
  document.getElementById('bc_seg_size').textContent = (SEG_SIZES[seg] || 0) + ' users in segment';
}}
updateSegSize();
async function sendCampaign() {{
  const seg = document.getElementById('bc_seg').value;
  const msg = document.getElementById('bc_msg').value.trim();
  const link = document.getElementById('bc_link').value.trim();
  const name = document.getElementById('bc_name').value.trim();
  const res = document.getElementById('bc_result');
  if (!msg) {{ res.textContent = '❌ Message is empty'; return; }}
  if (!confirm(`Send to ${{SEG_SIZES[seg] || '?'}} users?`)) return;
  res.textContent = 'Sending...';
  try {{
    const r = await fetch('/api/v1/admin/broadcast?secret=' + encodeURIComponent(ADMIN_SECRET), {{
      method: 'POST',
      headers: {{'Content-Type':'application/json','X-Admin-Secret':ADMIN_SECRET}},
      body: JSON.stringify({{segment:seg, message:msg, deep_link:link, name:name}})
    }});
    const d = await r.json();
    if (r.ok) {{
      res.textContent = `✅ Started ${{d.campaign_id}} → ${{d.size}} users`;
      setTimeout(() => location.reload(), 2000);
    }} else {{
      res.textContent = '❌ ' + (d.error || r.status);
    }}
  }} catch(e) {{ res.textContent = '❌ ' + e.message; }}
}}
async function cancelCampaign() {{
  if (!confirm('Cancel the running campaign?')) return;
  await fetch('/api/v1/admin/broadcast?secret=' + encodeURIComponent(ADMIN_SECRET), {{
    method: 'DELETE', headers: {{'X-Admin-Secret':ADMIN_SECRET}}
  }});
  location.reload();
}}
</script>
"""

def _admin_experiments_section() -> str:
    """Experiment results: exposures + downstream conversion per variant."""
    if not DB_READY:
        return ""
    try:
        # For each active experiment, get exposure counts per variant
        # and purchase_completed counts for users who saw each variant
        rows = _db_fetchall(
            "SELECT props_json, COUNT(*) FROM imodel_events "
            "WHERE event='experiment_exposure' GROUP BY props_json",
            (),
        )
        # Aggregate: {experiment: {variant: exposure_count}}
        exp_counts: Dict[str, Dict[str, int]] = {}
        for props_json, cnt in rows:
            try:
                import json as _json
                p = _json.loads(props_json)
                exp = p.get("experiment", "")
                var = p.get("variant", "")
                if exp and var:
                    exp_counts.setdefault(exp, {}).setdefault(var, 0)
                    exp_counts[exp][var] += int(cnt)
            except Exception:
                continue
        if not exp_counts:
            return ""
        sections = []
        for exp_name, variant_counts in exp_counts.items():
            exp_cfg = EXPERIMENTS.get(exp_name, {})
            desc = exp_cfg.get("description", exp_name)
            status = "🟢 active" if exp_cfg.get("active") else "🔴 off"
            traffic = int(float(exp_cfg.get("traffic", 1.0)) * 100)
            trs = "".join(
                f"<tr><td>{var}</td><td>{cnt:,}</td></tr>"
                for var, cnt in sorted(variant_counts.items(), key=lambda x: -x[1])
            )
            sections.append(
                f"<div style='margin-bottom:16px'>"
                f"<div style='margin-bottom:6px'><b>{exp_name}</b> <span class='muted'>{desc}</span> "
                f"<span class='pill'>{status}</span> <span class='pill'>{traffic}% traffic</span></div>"
                f"<table><tr><th>Variant</th><th>Exposures</th></tr>{trs}</table>"
                f"</div>"
            )
        return f"""
      <div class="section">
        <div class="card">
          <div class="muted">A/B Experiments</div>
          <div style="margin-top:12px">{''.join(sections)}</div>
        </div>
      </div>"""
    except Exception as e:
        return f'<div class="section"><div class="card muted">Experiment data unavailable: {str(e)[:80]}</div></div>'

def _pct(num: float | None) -> str:
    if num is None:
        return "—"
    return f"{num * 100:.1f}%"

def _admin_funnel_section() -> str:
    """Funnel conversion table (7d and 30d side by side)."""
    f7  = _analytics_funnel_counts(7)
    f30 = _analytics_funnel_counts(30)
    if not f7 and not f30:
        return ""
    rows = [
        ("Generation started",   "generation_started",   None),
        ("Generation completed", "generation_completed", "completion_rate"),
        ("Paywall hit",          "paywall_hit",          "paywall_rate"),
        ("Purchase completed",   "purchase_completed",   "purchase_rate"),
        ("Share tapped",         "share_tapped",         "share_rate"),
        ("Nudge sent",           "nudges_sent",          None),
        ("Nudge converted",      "nudge_converted",      "nudge_conversion_rate"),
        ("Referral joined",      "referral_joined",      None),
        ("Onboarding viewed",    "onboarding_viewed",    None),
        ("Onboarding completed", "onboarding_completed", None),
        ("Mode selected",        "mode_selected",        None),
        ("Buy tapped",           "buy_tapped",           None),
    ]
    def rate_cell(f: dict, rate_key: str | None) -> str:
        if not rate_key:
            return "<td>—</td>"
        v = f.get(rate_key)
        color = ""
        if v is not None:
            if v >= 0.7:
                color = "color:var(--ok)"
            elif v < 0.2:
                color = "color:var(--fail)"
        return f'<td style="{color}">{_pct(v)}</td>'
    trs = "".join(
        f"<tr><td>{label}</td>"
        f"<td>{f7.get(key, 0)}</td>{rate_cell(f7, rk)}"
        f"<td>{f30.get(key, 0)}</td>{rate_cell(f30, rk)}</tr>"
        for label, key, rk in rows
    )
    return f"""
      <div class="section">
        <div class="card">
          <div class="muted">Analytics Funnel</div>
          <table>
            <tr><th>Event</th><th>7d count</th><th>7d rate</th><th>30d count</th><th>30d rate</th></tr>
            {trs}
          </table>
          <div class="muted" style="margin-top:8px;font-size:12px">
            Unique generators 7d: {f7.get('unique_generators',0)} &nbsp;|&nbsp;
            Unique buyers 7d: {f7.get('unique_buyers',0)} &nbsp;|&nbsp;
            Unique generators 30d: {f30.get('unique_generators',0)} &nbsp;|&nbsp;
            Unique buyers 30d: {f30.get('unique_buyers',0)}
          </div>
        </div>
      </div>"""

def _admin_nudge_section() -> str:
    """Nudge scheduler status card."""
    now = time.time()
    week_ago = now - 7 * 24 * 3600
    total_users = len(STATS_USERS_INFO)
    eligible_count = sum(1 for uid in STATS_USERS_INFO if _nudge_eligible(uid))
    blocked_count  = sum(1 for ni in NUDGE_INFO.values() if ni.get("blocked"))
    total_sent     = sum(int(ni.get("count", 0)) for ni in NUDGE_INFO.values())
    capped_total   = sum(1 for ni in NUDGE_INFO.values() if int(ni.get("count", 0)) >= NUDGE_MAX_TOTAL)
    capped_weekly  = sum(
        1 for ni in NUDGE_INFO.values()
        if len([t for t in (ni.get("sent_timestamps") or []) if float(t) > week_ago]) >= NUDGE_WEEKLY_CAP
    )
    sent_7d = sum(
        len([t for t in (ni.get("sent_timestamps") or []) if float(t) > week_ago])
        for ni in NUDGE_INFO.values()
    )
    status_color = "var(--ok)" if NUDGE_ENABLED else "var(--fail)"
    status_text  = "ENABLED" if NUDGE_ENABLED else "DISABLED (set NUDGE_ENABLED=1)"
    return f"""
      <div class="section">
        <div class="card">
          <div class="muted">Nudge Scheduler</div>
          <div style="margin:8px 0">
            Status: <b style="color:{status_color}">{status_text}</b>
          </div>
          <table>
            <tr><th>Metric</th><th>Value</th><th>Config</th></tr>
            <tr><td>Total users</td><td>{total_users}</td><td>—</td></tr>
            <tr><td>Eligible now</td><td>{eligible_count}</td><td>inactive &gt; {NUDGE_INTERVAL_HOURS}h</td></tr>
            <tr><td>Sent this week</td><td>{sent_7d}</td><td>cap {NUDGE_WEEKLY_CAP}/7d</td></tr>
            <tr><td>Sent lifetime</td><td>{total_sent}</td><td>max {NUDGE_MAX_TOTAL} per user</td></tr>
            <tr><td>Blocked (bot)</td><td style="color:var(--fail)">{blocked_count}</td><td>permanent skip</td></tr>
            <tr><td>Lifetime capped</td><td>{capped_total}</td><td>≥ {NUDGE_MAX_TOTAL} sends</td></tr>
            <tr><td>Weekly capped</td><td>{capped_weekly}</td><td>≥ {NUDGE_WEEKLY_CAP}/7d</td></tr>
            <tr><td>Batch limit</td><td>{NUDGE_BATCH_LIMIT}/hr</td><td>NUDGE_BATCH_LIMIT</td></tr>
            <tr><td>Send window</td><td>{NUDGE_DAY_START_HOUR}:00–{NUDGE_DAY_END_HOUR}:00</td><td>per-user TZ</td></tr>
          </table>
        </div>
      </div>"""

def _admin_revenue_section() -> str:
    """Revenue analytics: KPIs, pack breakdown, paywall funnel, 14-day chart, cohort LTV, top spenders."""
    if not DB_READY:
        return '<div class="section"><div class="card muted">Revenue data unavailable (DB offline)</div></div>'
    try:
        now = time.time()
        cutoff_7d  = _date_key(now - 7  * 86400)
        cutoff_30d = _date_key(now - 30 * 86400)

        # ── 1. KPI aggregates ────────────────────────────────────────────────
        kpi_rows = _db_fetchall(
            "SELECT day >= %s AS in7, day >= %s AS in30, "
            "COUNT(*), COUNT(DISTINCT uid), "
            "SUM(CAST(props_json::json->>'stars' AS FLOAT)) "
            "FROM imodel_events WHERE event='purchase_completed' "
            "GROUP BY in7, in30",
            (cutoff_7d, cutoff_30d),
        )
        stars_7d = stars_30d = stars_all = 0
        txn_7d = txn_30d = txn_all = 0
        buyers_7d = buyers_30d = buyers_all = 0
        all_rows_kpi = _db_fetchall(
            "SELECT day >= %s, day >= %s, COUNT(*), COUNT(DISTINCT uid), "
            "COALESCE(SUM(CAST(props_json::json->>'stars' AS FLOAT)),0) "
            "FROM imodel_events WHERE event='purchase_completed' GROUP BY 1, 2",
            (cutoff_7d, cutoff_30d),
        )
        for in7, in30, cnt, ucnt, s in all_rows_kpi:
            s = int(s or 0); cnt = int(cnt); ucnt = int(ucnt)
            stars_all += s; txn_all += cnt; buyers_all = max(buyers_all, ucnt)
            if in30: stars_30d += s; txn_30d += cnt; buyers_30d = max(buyers_30d, ucnt)
            if in7:  stars_7d  += s; txn_7d  += cnt; buyers_7d  = max(buyers_7d, ucnt)
        aov = int(stars_all / txn_all) if txn_all else 0

        kpi_html = (
            f'<div class="grid kpi" style="grid-template-columns:repeat(4,1fr);margin-bottom:14px">'
            f'<div class="card"><div class="muted">Stars (7d)</div><div class="v ok">{stars_7d:,}★</div><div class="muted">{txn_7d} txn · {buyers_7d} buyers</div></div>'
            f'<div class="card"><div class="muted">Stars (30d)</div><div class="v ok">{stars_30d:,}★</div><div class="muted">{txn_30d} txn · {buyers_30d} buyers</div></div>'
            f'<div class="card"><div class="muted">Stars (all time)</div><div class="v ok">{stars_all:,}★</div><div class="muted">{txn_all} txn · {buyers_all} buyers</div></div>'
            f'<div class="card"><div class="muted">Avg order value</div><div class="v">{aov}★</div><div class="muted">per transaction</div></div>'
            f'</div>'
        )

        # ── 2. Pack breakdown (last 30 days) ─────────────────────────────────
        pack_rows = _db_fetchall(
            "SELECT props_json::json->>'pack' AS pack, "
            "COUNT(*) AS txn, COALESCE(SUM(CAST(props_json::json->>'stars' AS FLOAT)),0) AS stars "
            "FROM imodel_events WHERE event='purchase_completed' AND day >= %s "
            "GROUP BY pack ORDER BY stars DESC",
            (cutoff_30d,),
        )
        pack_trs = ""
        for pack, txn, s in pack_rows:
            s = int(s or 0)
            pct = f"{100*s/stars_30d:.0f}%" if stars_30d else "—"
            pack_trs += f"<tr><td><code>{pack or '—'}</code></td><td>{int(txn)}</td><td>{s:,}★</td><td>{pct}</td></tr>"

        # ── 3. Paywall conversion funnel ─────────────────────────────────────
        funnel_events = ["paywall_hit", "paywall_buy_tapped", "purchase_completed"]
        funnel_rows_db = _db_fetchall(
            "SELECT event, COUNT(*), COUNT(DISTINCT uid) FROM imodel_events "
            "WHERE event = ANY(%s) AND day >= %s GROUP BY event",
            (funnel_events, cutoff_30d),
        )
        fc: Dict[str, Dict[str, int]] = {}
        for ev, cnt, ucnt in funnel_rows_db:
            fc[ev] = {"cnt": int(cnt), "ucnt": int(ucnt)}
        def _funnel_rate(a: str, b: str) -> str:
            d = fc.get(b, {}).get("cnt", 0)
            n = fc.get(a, {}).get("cnt", 0)
            return f"{100*n/d:.0f}%" if d else "—"
        funnel_html = (
            f'<table><tr><th>Step</th><th>Events (30d)</th><th>Uniq users</th><th>Step rate</th></tr>'
            f'<tr><td>Paywall hit</td><td>{fc.get("paywall_hit",{}).get("cnt",0):,}</td><td>{fc.get("paywall_hit",{}).get("ucnt",0):,}</td><td>—</td></tr>'
            f'<tr><td>Buy tapped</td><td>{fc.get("paywall_buy_tapped",{}).get("cnt",0):,}</td><td>{fc.get("paywall_buy_tapped",{}).get("ucnt",0):,}</td>'
            f'<td>{_funnel_rate("paywall_buy_tapped","paywall_hit")}</td></tr>'
            f'<tr><td><b>Purchase completed</b></td><td>{fc.get("purchase_completed",{}).get("cnt",0):,}</td><td>{fc.get("purchase_completed",{}).get("ucnt",0):,}</td>'
            f'<td style="color:var(--ok)">{_funnel_rate("purchase_completed","paywall_buy_tapped")}</td></tr>'
            f'</table>'
        )

        # ── 4. 14-day Stars chart ─────────────────────────────────────────────
        chart_rows = _db_fetchall(
            "SELECT day, COALESCE(SUM(CAST(props_json::json->>'stars' AS FLOAT)),0), COUNT(*) "
            "FROM imodel_events WHERE event='purchase_completed' AND day >= %s "
            "GROUP BY day ORDER BY day",
            (_date_key(now - 14 * 86400),),
        )
        chart_by_day: Dict[str, Dict[str, int]] = {}
        for day, s, c in chart_rows:
            chart_by_day[str(day)] = {"stars": int(s or 0), "cnt": int(c)}
        chart_days = [_date_key(now - i * 86400) for i in range(13, -1, -1)]
        chart_data = [{"day": d[-5:], **chart_by_day.get(d, {"stars": 0, "cnt": 0})} for d in chart_days]
        max_s = max((d["stars"] for d in chart_data), default=1) or 1
        chart_bars = "".join(
            f'<td style="vertical-align:bottom;text-align:center">'
            f'<div style="background:#24c38b;opacity:.85;width:22px;height:{max(3,int(d["stars"]/max_s*60))}px;margin:0 auto 2px;border-radius:3px 3px 0 0" title="{d["stars"]}★"></div>'
            f'<div class="muted" style="font-size:10px">{d["day"]}</div>'
            f'</td>'
            for d in chart_data
        )
        chart_trs = "".join(
            f'<tr><td>{d["day"]}</td><td style="color:var(--ok)">{d["stars"]:,}★</td><td>{d["cnt"]}</td></tr>'
            for d in chart_data if d["stars"] or d["cnt"]
        )

        # ── 5. Cohort LTV (8 weekly cohorts) ─────────────────────────────────
        cohort_html = ""
        cohort_rows_list = []
        for week in range(7, -1, -1):
            cohort_start = now - (week + 1) * 7 * 86400
            cohort_end   = now - week * 7 * 86400
            cs_day = _date_key(cohort_start)
            ce_day = _date_key(cohort_end)
            # Users who first appeared in this cohort window
            cohort_uids = [
                uid for uid, ui in STATS_USERS_INFO.items()
                if cohort_start <= float(ui.get("first_seen", 0)) < cohort_end
            ]
            if not cohort_uids:
                continue
            # Revenue from these users
            cohort_rev = _db_fetchall(
                "SELECT COUNT(*), COALESCE(SUM(CAST(props_json::json->>'stars' AS FLOAT)),0) "
                "FROM imodel_events WHERE event='purchase_completed' AND uid = ANY(%s)",
                (cohort_uids,),
            )
            c_txn, c_stars = (int(cohort_rev[0][0]), int(cohort_rev[0][1] or 0)) if cohort_rev else (0, 0)
            c_buyers = min(c_txn, len(cohort_uids))
            conv = f"{100*c_buyers/len(cohort_uids):.0f}%" if cohort_uids else "—"
            avg_ltv = f"{c_stars//c_buyers}★" if c_buyers else "—"
            cohort_rows_list.append(
                f'<tr><td>{cs_day[5:]}</td><td>{len(cohort_uids)}</td><td>{conv}</td>'
                f'<td style="color:var(--ok)">{c_stars:,}★</td><td>{avg_ltv}</td></tr>'
            )
        if cohort_rows_list:
            cohort_html = (
                f'<table style="margin-top:12px"><tr><th>Cohort week</th><th>Users</th>'
                f'<th>% converted</th><th>Total ★</th><th>Avg LTV</th></tr>'
                + "".join(cohort_rows_list) + "</table>"
            )

        # ── 6. Top spenders ───────────────────────────────────────────────────
        top_rows = _db_fetchall(
            "SELECT uid, COUNT(*) AS txn, "
            "COALESCE(SUM(CAST(props_json::json->>'stars' AS FLOAT)),0) AS stars, "
            "MAX(ts) AS last_ts "
            "FROM imodel_events WHERE event='purchase_completed' "
            "GROUP BY uid ORDER BY stars DESC LIMIT 10",
            (),
        )
        top_trs = ""
        for uid, txn, s, last_ts in top_rows:
            uid_int = int(uid)
            uname = (STATS_USERS_INFO.get(uid_int) or {}).get("username") or str(uid_int)
            age_d = int((now - float(last_ts or now)) / 86400)
            age_str = f"{age_d}d ago" if age_d > 0 else "today"
            top_trs += (
                f'<tr><td>@{html_lib.escape(str(uname))}</td>'
                f'<td style="color:var(--ok)">{int(s or 0):,}★</td>'
                f'<td>{int(txn)}</td><td>{age_str}</td></tr>'
            )

        return f"""
      <div class="section">
        <div class="card">
          <div class="muted" style="font-weight:600;font-size:13px;margin-bottom:12px">💰 Revenue Analytics</div>
          {kpi_html}

          <div class="grid" style="grid-template-columns:1fr 1fr;gap:14px;margin-bottom:14px">
            <div>
              <div class="muted" style="margin-bottom:8px">Pack breakdown (30d)</div>
              <table>
                <tr><th>Pack</th><th>Txn</th><th>Stars</th><th>Share</th></tr>
                {pack_trs or '<tr><td colspan=4 class="muted">No purchases yet</td></tr>'}
              </table>
            </div>
            <div>
              <div class="muted" style="margin-bottom:8px">Paywall conversion (30d)</div>
              {funnel_html}
            </div>
          </div>

          <div class="muted" style="margin-bottom:8px">Daily revenue (last 14 days)</div>
          <div style="overflow-x:auto;margin-bottom:8px">
            <table style="border:none"><tr style="border:none">{chart_bars}</tr></table>
          </div>
          {'<table><tr><th>Date</th><th>Stars</th><th>Purchases</th></tr>' + chart_trs + '</table>' if chart_trs else ''}

          <div class="grid" style="grid-template-columns:1fr 1fr;gap:14px;margin-top:14px">
            <div>
              <div class="muted" style="margin-bottom:8px">Cohort LTV (weekly)</div>
              {cohort_html or '<p class="muted">Not enough data yet</p>'}
            </div>
            <div>
              <div class="muted" style="margin-bottom:8px">Top spenders</div>
              <table>
                <tr><th>User</th><th>Stars</th><th>Txn</th><th>Last</th></tr>
                {top_trs or '<tr><td colspan=4 class="muted">No purchases yet</td></tr>'}
              </table>
            </div>
          </div>
        </div>
      </div>"""
    except Exception as e:
        return f'<div class="section"><div class="card muted">Revenue data error: {html_lib.escape(str(e)[:120])}</div></div>'

def _admin_daily_trend_section() -> str:
    """Last 14-day mini-table of gens + payments."""
    now_ts = time.time()
    days_data = []
    for d in range(13, -1, -1):
        dk = _date_key(now_ts - d * 86400)
        dm = STATS_DAILY.get(dk) or {}
        days_data.append({
            "day": dk[-5:],  # MM-DD
            "gens": int(dm.get("gens_ok", 0)) + int(dm.get("gens_copy_ok", 0)),
            "pay": int(dm.get("payments", 0)),
            "msg": int(dm.get("messages", 0)),
            "photos": int(dm.get("photos", 0)),
        })
    max_gens = max((d["gens"] for d in days_data), default=1) or 1
    bars = "".join(
        f'<td style="vertical-align:bottom;text-align:center">'
        f'<div style="background:var(--accent);opacity:.8;width:24px;height:{max(4, int(d["gens"]/max_gens*60))}px;margin:0 auto 2px;border-radius:3px 3px 0 0"></div>'
        f'<div class="muted" style="font-size:10px">{d["day"]}</div>'
        f'</td>'
        for d in days_data
    )
    rows = "".join(
        f'<tr><td>{d["day"]}</td><td>{d["gens"]}</td><td>{d["pay"]}</td><td>{d["msg"]}</td><td>{d["photos"]}</td></tr>'
        for d in days_data
    )
    return f"""
      <div class="section">
        <div class="card">
          <div class="muted">Daily trend (last 14 days)</div>
          <div style="overflow-x:auto;margin:12px 0">
            <table style="border:none"><tr style="border:none">{bars}</tr></table>
          </div>
          <table>
            <tr><th>Date</th><th>Gens</th><th>Payments</th><th>Messages</th><th>Photos</th></tr>
            {rows}
          </table>
        </div>
      </div>"""

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

      {_admin_user_lookup_section()}
      {_admin_broadcast_section()}
      {_admin_revenue_section()}
      {_admin_funnel_section()}
      {_admin_nudge_section()}
      {_admin_experiments_section()}
      {_admin_daily_trend_section()}

    </div>
  </body>
  </html>
    """
    return HTMLResponse(content=html)

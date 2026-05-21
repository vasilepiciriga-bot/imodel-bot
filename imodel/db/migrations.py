"""Additive Postgres migrations — no DROP TABLE."""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List

from imodel.config.settings import get_settings
from imodel.db import connection as db


MIGRATION_SQL = [
    """
    CREATE TABLE IF NOT EXISTS imodel_styles (
        style_key TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        category TEXT NOT NULL,
        config_json TEXT NOT NULL DEFAULT '{}',
        price_credits INTEGER NOT NULL DEFAULT 1,
        is_premium BOOLEAN NOT NULL DEFAULT TRUE,
        is_trending BOOLEAN NOT NULL DEFAULT FALSE,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        sort_order INTEGER NOT NULL DEFAULT 100,
        quality_grade TEXT NOT NULL DEFAULT 'A',
        created_at DOUBLE PRECISION NOT NULL,
        updated_at DOUBLE PRECISION NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS imodel_packs (
        pack_key TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        config_json TEXT NOT NULL DEFAULT '{}',
        price_stars INTEGER NOT NULL,
        credits INTEGER NOT NULL,
        is_active BOOLEAN NOT NULL DEFAULT TRUE,
        sort_order INTEGER NOT NULL DEFAULT 100,
        created_at DOUBLE PRECISION NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS imodel_payments (
        id BIGSERIAL PRIMARY KEY,
        telegram_payment_charge_id TEXT UNIQUE,
        uid BIGINT NOT NULL,
        payload TEXT NOT NULL,
        stars INTEGER NOT NULL DEFAULT 0,
        credits_added INTEGER NOT NULL DEFAULT 0,
        created_at DOUBLE PRECISION NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS imodel_credit_transactions (
        id BIGSERIAL PRIMARY KEY,
        uid BIGINT NOT NULL,
        delta INTEGER NOT NULL,
        reason TEXT NOT NULL,
        ref_id TEXT,
        balance_after INTEGER,
        created_at DOUBLE PRECISION NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS imodel_generation_results (
        result_id TEXT PRIMARY KEY,
        uid BIGINT NOT NULL,
        job_id TEXT,
        style_key TEXT,
        s3_key TEXT,
        output_url TEXT,
        thumb_key TEXT,
        deleted_at DOUBLE PRECISION,
        created_at DOUBLE PRECISION NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS imodel_style_events (
        id BIGSERIAL PRIMARY KEY,
        uid BIGINT,
        style_key TEXT NOT NULL,
        event TEXT NOT NULL,
        meta_json TEXT NOT NULL DEFAULT '{}',
        created_at DOUBLE PRECISION NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS imodel_referrals (
        invited_uid BIGINT PRIMARY KEY,
        referrer_uid BIGINT NOT NULL,
        created_at DOUBLE PRECISION NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_imodel_generation_results_uid ON imodel_generation_results(uid, created_at DESC)",
    "CREATE INDEX IF NOT EXISTS idx_imodel_style_events_style ON imodel_style_events(style_key, event)",
    "CREATE INDEX IF NOT EXISTS idx_imodel_payments_uid ON imodel_payments(uid, created_at DESC)",
]


def run_migrations() -> bool:
    if not db.is_ready():
        conn = db.connect()
        if conn is None:
            return False
        try:
            with conn.cursor() as cur:
                for sql in MIGRATION_SQL:
                    cur.execute(sql.strip())
            return True
        except Exception as e:
            print("[imodel.db] migration error:", str(e)[:240])
            return False
        finally:
            try:
                conn.close()
            except Exception:
                pass
    for sql in MIGRATION_SQL:
        db.execute(sql.strip())
    return True


def seed_styles_if_empty() -> int:
    rows = db.fetchall("SELECT COUNT(*) FROM imodel_styles")
    count = int(rows[0][0]) if rows else 0
    if count > 0:
        return 0
    path = Path(get_settings().styles_seed_path)
    if not path.is_file():
        return 0
    with open(path, "r", encoding="utf-8") as f:
        styles: List[Dict[str, Any]] = json.load(f)
    now = time.time()
    n = 0
    for s in styles:
        key = s.get("key")
        if not key:
            continue
        db.execute(
            "INSERT INTO imodel_styles(style_key, name, category, config_json, price_credits, "
            "is_premium, is_trending, is_active, sort_order, quality_grade, created_at, updated_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (style_key) DO NOTHING",
            (
                key,
                s.get("name", key),
                s.get("category", "General"),
                json.dumps(s, ensure_ascii=False),
                int(s.get("price_credits", 1)),
                bool(s.get("is_premium", True)),
                bool(s.get("is_trending", False)),
                bool(s.get("is_active", True)),
                int(s.get("sort_order", 100)),
                str(s.get("quality_grade", "A")),
                now,
                now,
            ),
        )
        n += 1
    return n


def seed_packs_if_empty() -> int:
    from imodel.config.packages import list_packages

    rows = db.fetchall("SELECT COUNT(*) FROM imodel_packs")
    count = int(rows[0][0]) if rows else 0
    if count > 0:
        return 0
    now = time.time()
    n = 0
    for i, p in enumerate(list_packages(include_premium=True)):
        db.execute(
            "INSERT INTO imodel_packs(pack_key, name, config_json, price_stars, credits, is_active, sort_order, created_at) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (pack_key) DO NOTHING",
            (
                p["payload"],
                p.get("title", p["payload"]),
                json.dumps(p, ensure_ascii=False),
                int(p["stars"]),
                int(p["credits"]),
                True,
                i,
                now,
            ),
        )
        n += 1
    return n

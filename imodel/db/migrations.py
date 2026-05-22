"""Additive Postgres migrations — safe to call on every startup."""

from __future__ import annotations

from typing import Callable, Optional


def run_migrations(execute: Callable[[str, tuple], bool]) -> None:
    """execute(sql, params) -> success bool (e.g. app._db_execute)."""
    statements = [
        """
        CREATE TABLE IF NOT EXISTS imodel_payments (
            id BIGSERIAL PRIMARY KEY,
            uid BIGINT NOT NULL,
            package_key TEXT NOT NULL,
            stars_amount INTEGER NOT NULL DEFAULT 0,
            credits_added INTEGER NOT NULL DEFAULT 0,
            telegram_charge_id TEXT UNIQUE,
            status TEXT NOT NULL DEFAULT 'completed',
            created_at DOUBLE PRECISION NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS imodel_credit_transactions (
            id BIGSERIAL PRIMARY KEY,
            uid BIGINT NOT NULL,
            type TEXT NOT NULL,
            amount INTEGER NOT NULL,
            reason TEXT,
            job_id TEXT,
            payment_id BIGINT,
            created_at DOUBLE PRECISION NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS imodel_styles (
            key TEXT PRIMARY KEY,
            category TEXT NOT NULL,
            name TEXT NOT NULL,
            description TEXT,
            prompt_template TEXT,
            negative_prompt TEXT,
            prompt_version TEXT NOT NULL DEFAULT 'v1.0',
            price_credits INTEGER NOT NULL DEFAULT 4,
            trend_level TEXT,
            is_premium BOOLEAN NOT NULL DEFAULT TRUE,
            is_trending BOOLEAN NOT NULL DEFAULT FALSE,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            sort_order INTEGER NOT NULL DEFAULT 100,
            created_at DOUBLE PRECISION NOT NULL,
            updated_at DOUBLE PRECISION NOT NULL
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS imodel_generation_results (
            id BIGSERIAL PRIMARY KEY,
            job_id TEXT,
            uid BIGINT NOT NULL,
            style_key TEXT,
            prompt_version TEXT,
            image_url TEXT,
            s3_key TEXT,
            is_upscaled BOOLEAN NOT NULL DEFAULT FALSE,
            created_at DOUBLE PRECISION NOT NULL,
            deleted_at DOUBLE PRECISION
        )
        """,
        """
        CREATE TABLE IF NOT EXISTS imodel_style_events (
            id BIGSERIAL PRIMARY KEY,
            uid BIGINT,
            style_key TEXT NOT NULL,
            event TEXT NOT NULL,
            job_id TEXT,
            created_at DOUBLE PRECISION NOT NULL
        )
        """,
        "CREATE INDEX IF NOT EXISTS idx_imodel_gen_results_uid ON imodel_generation_results(uid, created_at DESC)",
        "CREATE INDEX IF NOT EXISTS idx_imodel_style_events_key ON imodel_style_events(style_key, event)",
    ]
    for sql in statements:
        execute(sql.strip(), ())

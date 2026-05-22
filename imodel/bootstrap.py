"""Wire iModel Studio modules into app.py with minimal surface area."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Callable, Optional

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

from imodel.config.packages import LEGACY_PACKAGES, PREMIUM_PACKAGES, credits_for_payload, get_package
from imodel.config.settings import feature_enabled
from imodel.db import run_migrations
from imodel.db import gallery as gallery_db
from imodel.db import ledger as ledger_db
from imodel.webapp_api import deps
from imodel.webapp_api.router import create_studio_router


def extend_db_init(db_execute: Callable[[str, tuple], bool]) -> None:
    if not db_execute:
        return
    try:
        run_migrations(db_execute)
    except Exception as e:
        print("[imodel] migration warning:", str(e)[:160])


def bind_app_context(ctx: dict) -> None:
    deps.CTX.clear()
    deps.CTX.update(ctx)
    weekly = Path(__file__).resolve().parent / "trends" / "weekly_trends.md"
    deps.CTX["weekly_trends_path"] = str(weekly)


def register_studio_routes(app: FastAPI) -> None:
    app.include_router(create_studio_router())


def mount_webapp(app: FastAPI, legacy_html_handler: Callable) -> None:
    dist = Path(__file__).resolve().parent.parent / "webapp" / "dist"
    index = dist / "index.html"
    if feature_enabled("WEBAPP_V2_STATIC") and index.is_file():
        assets = dist / "assets"
        if assets.is_dir():
            app.mount("/webapp/assets", StaticFiles(directory=str(assets)), name="webapp_assets")

        @app.get("/webapp")
        async def webapp_v2():
            return FileResponse(str(index))

        @app.get("/webapp/{path:path}")
        async def webapp_v2_spa(path: str):
            if path.startswith("assets/"):
                return FileResponse(str(dist / path))
            return FileResponse(str(index))
    else:
        app.get("/webapp")(legacy_html_handler)


def process_payment(
    *,
    uid: int,
    payload: str,
    stars_amount: int,
    telegram_charge_id: Optional[str],
    legacy_add_map: dict,
    db_ready: bool,
    db_execute: Callable,
    db_fetchall: Callable,
) -> int:
    """Return credits to add; 0 if duplicate payment when ledger enabled."""
    add = credits_for_payload(payload)
    if not add:
        if payload == "pack_10":
            add = 10
        elif payload == "pack_30":
            add = 30
        elif payload == "pack_100":
            add = 100
        else:
            add = int(legacy_add_map.get(payload, 0))

    if not feature_enabled("PAYMENT_LEDGER_V2") or not db_ready:
        return add

    if telegram_charge_id and ledger_db.payment_exists(db_fetchall, telegram_charge_id):
        return 0

    pkg = get_package(payload)
    ledger_db.record_payment(
        db_execute,
        uid=uid,
        package_key=payload,
        stars_amount=stars_amount or (pkg or {}).get("stars", 0),
        credits_added=add,
        telegram_charge_id=telegram_charge_id,
    )
    ledger_db.record_credit_tx(
        db_execute,
        uid=uid,
        tx_type="purchase",
        amount=add,
        reason=f"stars:{payload}",
    )
    return add


def save_gallery_result(
    *,
    uid: int,
    job_id: str,
    style_key: Optional[str],
    prompt_version: Optional[str],
    image_url: Optional[str],
    db_ready: bool,
    db_execute: Callable,
) -> None:
    if not feature_enabled("PERSISTENT_GALLERY") or not db_ready:
        return
    gallery_db.save_result(
        db_execute,
        uid=uid,
        job_id=job_id,
        style_key=style_key,
        prompt_version=prompt_version,
        image_url=image_url,
    )


def premium_buy_keyboard_rows(lang: dict) -> list:
    if not feature_enabled("NEW_STAR_PACKAGES"):
        return []
    rows = []
    for key in ("starter_249", "creator_599", "pro_999", "max_1999"):
        pkg = PREMIUM_PACKAGES[key]
        rows.append([{
            "text": f"{pkg['title']} — {pkg['stars']}★",
            "callback_data": pkg["callback"],
        }])
    return rows


def resolve_invoice_from_callback(callback: str) -> Optional[tuple]:
    """callback_data -> (payload, stars, title, description)"""
    for pool in (LEGACY_PACKAGES, PREMIUM_PACKAGES):
        for pkg in pool.values():
            if pkg.get("callback") == callback:
                return (
                    pkg["key"],
                    int(pkg["stars"]),
                    pkg["title"],
                    pkg.get("description", ""),
                )
    return None

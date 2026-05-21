from __future__ import annotations

import time
from typing import Any, Dict, Optional

from imodel.config.packages import credits_for_payload
from imodel.db import connection as db


def record_payment(
    uid: int,
    payload: str,
    stars: int,
    credits_added: int,
    charge_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Insert payment; returns {'ok': bool, 'duplicate': bool}."""
    if not db.is_ready():
        return {"ok": True, "duplicate": False, "ledger": False}
    charge_id = charge_id or f"legacy_{uid}_{payload}_{int(time.time())}"
    existing = db.fetchall(
        "SELECT id FROM imodel_payments WHERE telegram_payment_charge_id = %s LIMIT 1",
        (charge_id,),
    )
    if existing:
        return {"ok": True, "duplicate": True, "ledger": True}
    db.execute(
        "INSERT INTO imodel_payments(telegram_payment_charge_id, uid, payload, stars, credits_added, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (charge_id, uid, payload, stars, credits_added, time.time()),
    )
    return {"ok": True, "duplicate": False, "ledger": True}


def record_credit_transaction(uid: int, delta: int, reason: str, ref_id: Optional[str] = None, balance_after: Optional[int] = None) -> None:
    if not db.is_ready():
        return
    db.execute(
        "INSERT INTO imodel_credit_transactions(uid, delta, reason, ref_id, balance_after, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s)",
        (uid, delta, reason, ref_id, balance_after, time.time()),
    )


def process_payment_idempotent(
    uid: int,
    payload: str,
    stars: int,
    charge_id: Optional[str] = None,
) -> Dict[str, Any]:
    credits = credits_for_payload(payload)
    if credits <= 0:
        return {"ok": False, "credits": 0, "duplicate": False}
    rec = record_payment(uid, payload, stars, credits, charge_id=charge_id)
    if rec.get("duplicate"):
        return {"ok": True, "credits": 0, "duplicate": True}
    return {"ok": True, "credits": credits, "duplicate": False}


def revenue_summary() -> Dict[str, Any]:
    if not db.is_ready():
        return {"total_payments": 0, "total_stars": 0}
    rows = db.fetchall("SELECT COUNT(*), COALESCE(SUM(stars),0) FROM imodel_payments")
    if rows:
        return {"total_payments": int(rows[0][0]), "total_stars": int(rows[0][1])}
    return {"total_payments": 0, "total_stars": 0}

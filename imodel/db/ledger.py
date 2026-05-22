"""Payment and credit ledger (Phase 6+, safe no-op when DB unavailable)."""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, Optional


def payment_exists(execute_fetch: Callable, charge_id: str) -> bool:
    if not charge_id:
        return False
    rows = execute_fetch(
        "SELECT id FROM imodel_payments WHERE telegram_charge_id = %s LIMIT 1",
        (charge_id,),
    )
    return bool(rows)


def record_payment(
    execute: Callable[[str, tuple], bool],
    *,
    uid: int,
    package_key: str,
    stars_amount: int,
    credits_added: int,
    telegram_charge_id: Optional[str],
) -> bool:
    return execute(
        "INSERT INTO imodel_payments(uid, package_key, stars_amount, credits_added, telegram_charge_id, status, created_at) "
        "VALUES (%s, %s, %s, %s, %s, 'completed', %s) ON CONFLICT (telegram_charge_id) DO NOTHING",
        (uid, package_key, stars_amount, credits_added, telegram_charge_id, time.time()),
    )


def record_credit_tx(
    execute: Callable[[str, tuple], bool],
    *,
    uid: int,
    tx_type: str,
    amount: int,
    reason: str = "",
    job_id: Optional[str] = None,
    payment_id: Optional[int] = None,
) -> bool:
    return execute(
        "INSERT INTO imodel_credit_transactions(uid, type, amount, reason, job_id, payment_id, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (uid, tx_type, amount, reason[:500], job_id, payment_id, time.time()),
    )


def resolve_package_credits(payload: str, fallback_map: Dict[str, int]) -> int:
    from imodel.config.packages import credits_for_payload

    c = credits_for_payload(payload)
    if c:
        return c
    return int(fallback_map.get(payload, 0))

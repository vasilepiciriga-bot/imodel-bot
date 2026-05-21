from __future__ import annotations

import time
from typing import Optional

from imodel.db import connection as db


def save_referral(invited_uid: int, referrer_uid: int) -> bool:
    if not db.is_ready() or invited_uid == referrer_uid:
        return False
    existing = db.fetchall("SELECT invited_uid FROM imodel_referrals WHERE invited_uid = %s", (invited_uid,))
    if existing:
        return False
    db.execute(
        "INSERT INTO imodel_referrals(invited_uid, referrer_uid, created_at) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
        (invited_uid, referrer_uid, time.time()),
    )
    return True


def get_referrer(invited_uid: int) -> Optional[int]:
    if not db.is_ready():
        return None
    rows = db.fetchall("SELECT referrer_uid FROM imodel_referrals WHERE invited_uid = %s", (invited_uid,))
    return int(rows[0][0]) if rows else None

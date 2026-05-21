from __future__ import annotations

import time
import uuid
from typing import Any, Dict, List, Optional

from imodel.config.settings import get_settings
from imodel.db import connection as db


def save_result(
    uid: int,
    job_id: Optional[str],
    style_key: Optional[str],
    s3_key: Optional[str],
    output_url: Optional[str],
) -> Optional[str]:
    if not db.is_ready() or not get_settings().persistent_gallery:
        return None
    result_id = uuid.uuid4().hex
    db.execute(
        "INSERT INTO imodel_generation_results(result_id, uid, job_id, style_key, s3_key, output_url, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (result_id, uid, job_id, style_key, s3_key, output_url, time.time()),
    )
    _trim_user_gallery(uid)
    return result_id


def _trim_user_gallery(uid: int) -> None:
    limit = get_settings().gallery_limit
    rows = db.fetchall(
        "SELECT result_id FROM imodel_generation_results WHERE uid = %s AND deleted_at IS NULL "
        "ORDER BY created_at DESC",
        (uid,),
    )
    if len(rows) <= limit:
        return
    for (rid,) in rows[limit:]:
        db.execute(
            "UPDATE imodel_generation_results SET deleted_at = %s WHERE result_id = %s",
            (time.time(), rid),
        )


def list_for_user(uid: int, limit: int = 50) -> List[Dict[str, Any]]:
    if db.is_ready() and get_settings().persistent_gallery:
        rows = db.fetchall(
            "SELECT result_id, job_id, style_key, s3_key, output_url, created_at "
            "FROM imodel_generation_results WHERE uid = %s AND deleted_at IS NULL "
            "ORDER BY created_at DESC LIMIT %s",
            (uid, limit),
        )
        return [
            {
                "result_id": r[0],
                "job_id": r[1],
                "style_key": r[2],
                "s3_key": r[3],
                "output_url": r[4],
                "created_at": r[5],
            }
            for r in rows
        ]
    return []


def soft_delete(uid: int, result_id: str) -> bool:
    if not db.is_ready():
        return False
    db.execute(
        "UPDATE imodel_generation_results SET deleted_at = %s WHERE result_id = %s AND uid = %s",
        (time.time(), result_id, uid),
    )
    return True


def record_style_event(uid: int, style_key: str, event: str, meta: Optional[Dict[str, Any]] = None) -> None:
    if not db.is_ready():
        return
    import json
    db.execute(
        "INSERT INTO imodel_style_events(uid, style_key, event, meta_json, created_at) VALUES (%s, %s, %s, %s, %s)",
        (uid, style_key, event, json.dumps(meta or {}, ensure_ascii=False), time.time()),
    )

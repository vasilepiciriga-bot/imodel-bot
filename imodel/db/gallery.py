"""Persistent gallery storage."""

from __future__ import annotations

import time
from typing import Any, Callable, Dict, List, Optional


def save_result(
    execute: Callable[[str, tuple], bool],
    *,
    uid: int,
    job_id: str,
    style_key: Optional[str],
    prompt_version: Optional[str],
    image_url: Optional[str],
    s3_key: Optional[str] = None,
) -> bool:
    return execute(
        "INSERT INTO imodel_generation_results(job_id, uid, style_key, prompt_version, image_url, s3_key, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s)",
        (job_id, uid, style_key, prompt_version, image_url, s3_key, time.time()),
    )


def list_results(fetchall: Callable, uid: int, limit: int = 50) -> List[Dict[str, Any]]:
    rows = fetchall(
        "SELECT id, job_id, style_key, prompt_version, image_url, s3_key, is_upscaled, created_at "
        "FROM imodel_generation_results WHERE uid = %s AND deleted_at IS NULL "
        "ORDER BY created_at DESC LIMIT %s",
        (uid, limit),
    )
    out = []
    for row in rows or []:
        out.append({
            "id": row[0],
            "job_id": row[1],
            "style_key": row[2],
            "prompt_version": row[3],
            "image_url": row[4],
            "s3_key": row[5],
            "is_upscaled": bool(row[6]),
            "created_at": row[7],
        })
    return out


def soft_delete(execute: Callable[[str, tuple], bool], result_id: int, uid: int) -> bool:
    return execute(
        "UPDATE imodel_generation_results SET deleted_at = %s WHERE id = %s AND uid = %s",
        (time.time(), result_id, uid),
    )

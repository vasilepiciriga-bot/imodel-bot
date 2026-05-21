"""Database connection helpers — delegates to app when integrated."""

from __future__ import annotations

import os
from typing import Any, Callable, List, Optional, Tuple

try:
    import psycopg
except Exception:
    psycopg = None  # type: ignore

DATABASE_URL = os.getenv("DATABASE_URL") or os.getenv("POSTGRES_URL") or ""

# Set by app.py on startup
_db_execute: Optional[Callable[[str, tuple], bool]] = None
_db_fetchall: Optional[Callable[[str, tuple], List[tuple]]] = None
_db_ready: bool = False


def configure(execute_fn: Callable, fetchall_fn: Callable, ready: bool) -> None:
    global _db_execute, _db_fetchall, _db_ready
    _db_execute = execute_fn
    _db_fetchall = fetchall_fn
    _db_ready = ready


def is_ready() -> bool:
    return _db_ready and _db_execute is not None


def execute(sql: str, params: tuple = ()) -> bool:
    if _db_execute is None:
        return False
    return _db_execute(sql, params)


def fetchall(sql: str, params: tuple = ()) -> List[tuple]:
    if _db_fetchall is None:
        return []
    return _db_fetchall(sql, params)


def connect():
    if not DATABASE_URL or psycopg is None:
        return None
    return psycopg.connect(DATABASE_URL, autocommit=True)

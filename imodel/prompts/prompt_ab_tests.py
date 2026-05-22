"""A/B test group placeholders (traffic split applied in Phase 7+)."""

from __future__ import annotations

import hashlib


def ab_group_for_user(style_key: str, user_id: int | None, groups: tuple[str, ...] = ("a", "b")) -> str:
    if not groups:
        return "a"
    if user_id is None:
        return groups[0]
    raw = f"{style_key}:{user_id}".encode("utf-8")
    bucket = int(hashlib.sha256(raw).hexdigest()[:8], 16) % len(groups)
    return groups[bucket]


def resolve_ab_test_group(style_key: str, declared_group: str | None, user_id: int | None = None) -> str:
    if declared_group:
        return declared_group
    return ab_group_for_user(style_key, user_id)

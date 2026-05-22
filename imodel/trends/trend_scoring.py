"""Placeholder trend scoring for weekly ops (Phase 9 analytics)."""

from __future__ import annotations


def trend_score(
    *,
    clicks: int = 0,
    conversions: int = 0,
    failures: int = 0,
) -> float:
    if clicks <= 0:
        return 0.0
    conversion_rate = conversions / clicks
    failure_penalty = min(0.5, failures / max(clicks, 1))
    return round(conversion_rate * 100 * (1 - failure_penalty), 2)

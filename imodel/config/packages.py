"""Telegram Stars credit packages — legacy + premium."""

from __future__ import annotations

from typing import Any, Dict, List

# Legacy payloads — must remain forever
LEGACY_PACKAGES: List[Dict[str, Any]] = [
    {"payload": "pack_10", "title": "iModel — 10 photos", "credits": 10, "stars": 200, "legacy": True},
    {"payload": "pack_30", "title": "iModel — 30 photos", "credits": 30, "stars": 500, "legacy": True},
    {"payload": "pack_100", "title": "iModel — 100 photos", "credits": 100, "stars": 1200, "legacy": True},
]

PREMIUM_PACKAGES: List[Dict[str, Any]] = [
    {
        "payload": "pack_starter",
        "title": "Starter",
        "description": "6 premium photos — best first test",
        "credits": 6,
        "stars": 249,
        "hd_upgrades": 0,
        "badge": None,
    },
    {
        "payload": "pack_creator",
        "title": "Creator",
        "description": "18 premium photos — most popular",
        "credits": 18,
        "stars": 599,
        "hd_upgrades": 0,
        "badge": "popular",
    },
    {
        "payload": "pack_pro",
        "title": "Pro",
        "description": "35 photos + 5 HD upgrades",
        "credits": 35,
        "stars": 999,
        "hd_upgrades": 5,
        "badge": None,
    },
    {
        "payload": "pack_max",
        "title": "iModel Max",
        "description": "80 photos + 15 HD — all premium looks",
        "credits": 80,
        "stars": 1999,
        "hd_upgrades": 15,
        "badge": "best",
    },
]

PACK_CREDITS: Dict[str, int] = {}
PACK_STARS: Dict[str, int] = {}
for p in LEGACY_PACKAGES + PREMIUM_PACKAGES:
    PACK_CREDITS[p["payload"]] = int(p["credits"])
    PACK_STARS[p["payload"]] = int(p["stars"])


def list_packages(include_premium: bool = True) -> List[Dict[str, Any]]:
    out = list(LEGACY_PACKAGES)
    if include_premium:
        out.extend(PREMIUM_PACKAGES)
    return out


def credits_for_payload(payload: str) -> int:
    return int(PACK_CREDITS.get(payload, 0))

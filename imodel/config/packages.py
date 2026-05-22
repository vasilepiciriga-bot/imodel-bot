"""Telegram Stars packages — legacy MVP + premium studio packs."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

LEGACY_PACKAGES: Dict[str, Dict[str, Any]] = {
    "pack_10": {
        "key": "pack_10",
        "title": "iModel — 10 premium photos",
        "description": "Starter pack",
        "stars": 200,
        "credits": 10,
        "hd_upgrades": 0,
        "callback": "buy_stars_10",
    },
    "pack_30": {
        "key": "pack_30",
        "title": "iModel — 30 premium photos",
        "description": "Creator pack",
        "stars": 500,
        "credits": 30,
        "hd_upgrades": 0,
        "callback": "buy_stars_30",
    },
    "pack_100": {
        "key": "pack_100",
        "title": "iModel — 100 premium photos",
        "description": "Pro pack",
        "stars": 1200,
        "credits": 100,
        "hd_upgrades": 0,
        "callback": "buy_stars_100",
    },
}

PREMIUM_PACKAGES: Dict[str, Dict[str, Any]] = {
    "starter_249": {
        "key": "starter_249",
        "title": "iModel Studio Starter",
        "description": "6 premium photos — best for first test",
        "stars": 249,
        "credits": 6,
        "hd_upgrades": 0,
        "callback": "buy_stars_starter_249",
        "popular": False,
    },
    "creator_599": {
        "key": "creator_599",
        "title": "iModel Studio Creator",
        "description": "18 premium photos — most popular",
        "stars": 599,
        "credits": 18,
        "hd_upgrades": 0,
        "callback": "buy_stars_creator_599",
        "popular": True,
    },
    "pro_999": {
        "key": "pro_999",
        "title": "iModel Studio Pro",
        "description": "35 premium photos + 5 HD upgrades",
        "stars": 999,
        "credits": 35,
        "hd_upgrades": 5,
        "callback": "buy_stars_pro_999",
        "priority_queue": True,
    },
    "max_1999": {
        "key": "max_1999",
        "title": "iModel Max",
        "description": "80 premium photos + 15 HD upgrades",
        "stars": 1999,
        "credits": 80,
        "hd_upgrades": 15,
        "callback": "buy_stars_max_1999",
        "priority_queue": True,
        "all_premium_looks": True,
    },
}

ALL_PACKAGES: Dict[str, Dict[str, Any]] = {**LEGACY_PACKAGES, **PREMIUM_PACKAGES}


def get_package(payload_or_key: str) -> Optional[Dict[str, Any]]:
    return ALL_PACKAGES.get(payload_or_key)


def list_all_packages(*, premium_only: bool = False, legacy_only: bool = False) -> List[Dict[str, Any]]:
    if legacy_only:
        return list(LEGACY_PACKAGES.values())
    if premium_only:
        return list(PREMIUM_PACKAGES.values())
    return list(ALL_PACKAGES.values())


def credits_for_payload(payload: str) -> int:
    pkg = get_package(payload)
    return int(pkg["credits"]) if pkg else 0

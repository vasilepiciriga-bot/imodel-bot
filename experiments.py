"""
Lightweight server-side A/B experiment system.

Assignment is deterministic: same uid always gets the same variant
(hash-based, no DB or session state required).

Add experiments to EXPERIMENTS dict. Set active=False to kill-switch.
traffic controls what fraction of users are enrolled (rest get "control").
"""
import hashlib
from typing import Dict, Optional

EXPERIMENTS: Dict[str, Dict] = {
    # Paywall modal copy — tests social proof vs urgency headline
    "paywall_copy": {
        "variants": ["control", "urgency", "social_proof"],
        "traffic": 1.0,
        "active": True,
        "description": "Paywall headline copy variant",
        "primary_metric": "purchase_completed",
        "exposure_event": "paywall_hit",
    },
    # Nudge message minimum gap — tests 24h vs 48h re-engagement timing
    "nudge_interval": {
        "variants": ["24h", "48h"],
        "traffic": 0.5,
        "active": True,
        "description": "Minimum hours between nudges",
        "primary_metric": "nudge_converted",
        "exposure_event": "nudge_sent",
    },
    # Onboarding CTA button text
    "onboarding_cta": {
        "variants": ["try_free", "see_examples"],
        "traffic": 1.0,
        "active": True,
        "description": "Welcome screen CTA button label",
        "primary_metric": "generation_started",
        "exposure_event": "onboarding_viewed",
    },
    # Premium mode upgrade sheet — inline two-button sheet vs direct paywall
    "upgrade_sheet": {
        "variants": ["inline", "paywall"],
        "traffic": 1.0,
        "active": True,
        "description": "Premium mode gate: inline upgrade sheet vs direct paywall redirect",
        "primary_metric": "premium_mode_use_credits",
        "exposure_event": "premium_mode_upgrade_shown",
    },
    # Bundle offer position in Shop packs tab
    "bundle_position": {
        "variants": ["top", "control"],
        "traffic": 0.8,
        "active": True,
        "description": "Show bundle card at top of packs tab vs standard position",
        "primary_metric": "purchase_completed",
        "exposure_event": "shop_opened",
    },
}


def get_variant(uid: int, experiment: str) -> str:
    """Return deterministic variant for a user. Returns 'control' when inactive or out of traffic."""
    exp = EXPERIMENTS.get(experiment)
    if not exp or not exp.get("active", False):
        return "control"
    variants = exp.get("variants", ["control"])
    if not variants:
        return "control"
    # Deterministic hash: uid + experiment name → stable bucket
    h = int(hashlib.md5(f"{uid}:{experiment}".encode()).hexdigest(), 16)
    # Traffic gate: skip if user falls outside enrolled slice
    traffic = float(exp.get("traffic", 1.0))
    if traffic < 1.0 and (h % 10000) / 10000.0 >= traffic:
        return "control"
    return variants[h % len(variants)]


def all_variants(uid: int) -> Dict[str, str]:
    """Return all active experiment assignments for a user."""
    return {name: get_variant(uid, name) for name in EXPERIMENTS if EXPERIMENTS[name].get("active")}


def nudge_interval_hours(uid: int) -> int:
    """Return the nudge minimum gap for a user based on their experiment variant."""
    v = get_variant(uid, "nudge_interval")
    return 48 if v == "48h" else 24

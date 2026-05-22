"""Feature flags and runtime settings (defaults keep MVP behavior)."""

from __future__ import annotations

import os
from functools import lru_cache
from typing import Dict


def _flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in ("1", "true", "yes", "on")


@lru_cache(maxsize=1)
def load_settings() -> Dict[str, bool]:
    return {
        "USE_PROMPT_BUILDER": _flag("USE_PROMPT_BUILDER", "0"),
        "WEBAPP_V2_STATIC": _flag("WEBAPP_V2_STATIC", "0"),
        "NEW_STAR_PACKAGES": _flag("NEW_STAR_PACKAGES", "0"),
        "PERSISTENT_GALLERY": _flag("PERSISTENT_GALLERY", "0"),
        "STYLE_CATALOG_V2": _flag("STYLE_CATALOG_V2", "0"),
        "PAYMENT_LEDGER_V2": _flag("PAYMENT_LEDGER_V2", "0"),
        "COPY_MODE_V2": _flag("COPY_MODE_V2", "0"),
        "TREND_LAB_V2": _flag("TREND_LAB_V2", "0"),
        "ADMIN_ANALYTICS_V2": _flag("ADMIN_ANALYTICS_V2", "0"),
        "GROWTH_LOOPS_V2": _flag("GROWTH_LOOPS_V2", "0"),
    }


def feature_enabled(key: str) -> bool:
    return load_settings().get(key, False)

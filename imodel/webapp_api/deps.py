"""Runtime dependencies injected from app.py at startup."""

from __future__ import annotations

from typing import Any, Callable, Dict, Optional

# Populated by imodel.bootstrap.bind_app_context()
CTX: Dict[str, Any] = {}


def get(name: str, default: Any = None) -> Any:
    return CTX.get(name, default)

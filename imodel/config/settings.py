import os
from dataclasses import dataclass, field
from functools import lru_cache


def _flag(name: str, default: str = "0") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


@dataclass
class Settings:
    use_prompt_builder: bool = field(default_factory=lambda: _flag("USE_PROMPT_BUILDER"))
    webapp_v2_static: bool = field(default_factory=lambda: _flag("WEBAPP_V2_STATIC"))
    new_star_packages: bool = field(default_factory=lambda: _flag("NEW_STAR_PACKAGES"))
    persistent_gallery: bool = field(default_factory=lambda: _flag("PERSISTENT_GALLERY"))
    style_catalog_v2: bool = field(default_factory=lambda: _flag("STYLE_CATALOG_V2"))
    payment_ledger_v2: bool = field(default_factory=lambda: _flag("PAYMENT_LEDGER_V2"))
    copy_mode_v2: bool = field(default_factory=lambda: _flag("COPY_MODE_V2"))
    notify_chat_on_webapp_job: bool = field(default_factory=lambda: _flag("NOTIFY_CHAT_ON_WEBAPP_JOB", "1"))
    gallery_limit: int = field(default_factory=lambda: int(os.getenv("GALLERY_LIMIT", "50")))
    data_dir: str = field(default_factory=lambda: os.getenv("DATA_DIR", "data"))
    styles_seed_path: str = field(default_factory=lambda: os.getenv(
        "STYLES_SEED_PATH",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "styles_seed.json"),
    ))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()

from pydantic import BaseSettings, Field
from functools import lru_cache
import os


class Settings(BaseSettings):
    TELEGRAM_TOKEN: str = Field(..., env="TELEGRAM_TOKEN")
    REPLICATE_API_TOKEN: str = Field(..., env="REPLICATE_API_TOKEN")

    IMG_MODEL: str = Field("black-forest-labs/FLUX.1-dev", env="IMG_MODEL")
    UPSCALE_MODEL: str = Field("xinntao/real-esrgan", env="UPSCALE_MODEL")
    INPAINT_MODEL: str = Field("jiahui/laminpaint", env="INPAINT_MODEL")

    GRID_ROWS: int = Field(6, env="GRID_ROWS")
    GRID_COLS: int = Field(6, env="GRID_COLS")

    SMALL_OBJ_MAX_RATIO: float = Field(0.03, env="SMALL_OBJ_MAX_RATIO")

    class Config:
        env_file = os.getenv("ENV_FILE", ".env")
        env_file_encoding = "utf-8"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()  # type: ignore


settings = get_settings()


from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/app/core/config.py -> project root is three levels up
_PROJECT_ROOT_ENV = Path(__file__).resolve().parents[3] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=_PROJECT_ROOT_ENV, env_file_encoding="utf-8", extra="ignore"
    )

    app_name: str = "IQO Strategy Lab"
    app_version: str = "0.1.0"
    app_env: str = "development"
    app_debug: bool = True

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    database_url: str = "postgresql+psycopg://iqolab:iqolab@localhost:5432/iqolab"

    frontend_url: str = "http://localhost:5173"

    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()

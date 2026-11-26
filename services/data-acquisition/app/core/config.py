"""Settings of the data-acquisition service: environment variables, then a local `.env`."""

from pathlib import Path

from pydantic_settings import SettingsConfigDict
from platform_kit.settings import ServiceSettings

_SERVICE_DIR = Path(__file__).resolve().parents[2]


class Settings(ServiceSettings):
    # Resolve this service's .env independently of the shell's working directory. This
    # keeps local token verification aligned with the identity service's service-local key.
    model_config = SettingsConfigDict(env_file=str(_SERVICE_DIR / ".env"), extra="ignore")

    SERVICE_NAME: str = "data-acquisition"
    DB_SCHEMA: str = "data_acquisition"
    # The central access document (config/access-control.json in the repository). The image sets
    # ACCESS_CONFIG_PATH=/app/config/access-control.json; mount a ConfigMap over it to change access.
    ACCESS_CONFIG_PATH: str = str(_SERVICE_DIR.parent.parent / "config" / "access-control.json")

    # --- Rate limiting: memory:// counts per process; use redis://... to share counters across replicas ---
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_STORAGE_URI: str = "memory://"

    # --- Business configuration ---


config = Settings()

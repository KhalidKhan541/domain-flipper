from pathlib import Path
from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    database_path: Path = Path("data/domains.db")
    log_level: str = "INFO"

    # Budget
    max_bid: int = 100
    preferred_min: int = 10
    preferred_max: int = 50
    exceptional_max: int = 300

    # Notifications
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    discord_webhook_url: Optional[str] = None
    smtp_host: Optional[str] = None
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_pass: Optional[str] = None
    email_from: Optional[str] = None
    email_to: Optional[str] = None

    # API keys
    catchdoms_api_key: Optional[str] = None
    crawly_api_key: Optional[str] = None
    ahrefs_api_key: Optional[str] = None
    moz_api_key: Optional[str] = None
    google_safe_browsing_key: Optional[str] = None

    # Offline mode — skip external HTTP calls, use heuristics/optimistic defaults
    offline_mode: bool = False

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()

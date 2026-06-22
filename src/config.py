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

    # n8n
    n8n_url: Optional[str] = None

    # Notifications
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    discord_webhook_url: Optional[str] = None
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_pass: str = ""
    email_from: Optional[str] = None
    email_to: Optional[str] = None

    # API keys (all optional — zero-budget mode uses no paid APIs)
    catchdoms_api_key: Optional[str] = None
    crawly_api_key: Optional[str] = None
    ahrefs_api_key: Optional[str] = None
    moz_api_key: Optional[str] = None
    google_safe_browsing_key: Optional[str] = None
    apollo_api_key: Optional[str] = None
    tomba_api_key: Optional[str] = None
    twitter_bearer_token: Optional[str] = None

    # Outbound outreach
    max_outbound_per_run: int = 20

    # Offline mode — skip external HTTP calls, use heuristics/optimistic defaults
    offline_mode: bool = False

    # Trading — Wallet & Escrow
    wallet_type: str = "coinbase"  # "coinbase" | "phantom" | "metamask"
    wallet_chain: str = "base"  # "base" | "ethereum" | "solana"
    escrow_chain: str = "base"  # chain for escrow contracts
    escrow_timeout_hours: int = 72  # auto-refund after this many hours

    # Trading — Cashout
    cashout_method: str = "binance_p2p"  # "binance_p2p" | "paxful" | "manual"
    cashout_currency: str = "USD"  # fiat currency for cashout
    cashout_payment_method: str = "bank_transfer"  # "bank_transfer" | "upi" | "paypal"

    # Trading — Domain Transfer
    preferred_registrar: str = "porkbun"  # where to receive domains
    transfer_timeout_days: int = 10  # cancel transfer if not completed

    # Trading — Verification
    min_ownership_confidence: float = 0.7  # minimum confidence to proceed
    require_dns_check: bool = True

    model_config = SettingsConfigDict(env_file=".env")


settings = Settings()

"""App settings, read from environment variables or the repo-root .env file."""
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_ENV = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ROOT_ENV, extra="ignore")

    database_url: str = "postgresql+psycopg://payledger:payledger@localhost:5432/payledger"
    # Shared secret Razorpay uses to sign webhooks. Set the same value in the Razorpay dashboard.
    razorpay_webhook_secret: str = "dev_webhook_secret"
    # AI reconciliation (optional). Without a key, matching still works; explanations are skipped.
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-3.5-flash"  # pinned: aliases like *-latest change under you


settings = Settings()

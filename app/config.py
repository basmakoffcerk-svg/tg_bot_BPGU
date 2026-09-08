"""
Application Configuration and Environment Settings.
Uses pydantic-settings v2 to load configuration from environment and .env files.
"""

from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Core settings for АРМ Старосты system."""

    # Telegram Bot
    BOT_TOKEN: str = "1234567890:ABCdefGHIjklMNOpqrsTUVwxyz_12345678"
    STAROSTA_TELEGRAM_ID: Optional[int] = 123456789
    GROUP_CHAT_ID: Optional[int] = -1001234567890

    # Server & Runtime
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    APP_ENV: str = "development"
    TIMEZONE: str = "Europe/Moscow"

    # Webhook
    WEBHOOK_URL: Optional[str] = "https://api.yourdomain.com/webhook"
    WEBHOOK_SECRET: Optional[str] = "your_super_secret_webhook_token"

    # Frontend Mini App URL
    FRONTEND_URL: Optional[str] = "https://app.yourdomain.com"

    # Database & Storage
    DATABASE_URL: str = "sqlite+aiosqlite:///data/database.sqlite"
    BACKUP_DIR: str = "data/backups"

    # Geolocation & Checkin Rules
    MAX_ALLOWED_DISTANCE_METERS: float = 150.0
    MAX_GPS_ACCURACY_METERS: float = 50.0
    CHECKIN_WINDOW_BEFORE_MINUTES: int = 5
    CHECKIN_WINDOW_AFTER_MINUTES: int = 15
    MAX_CLOCK_DRIFT_SECONDS: float = 30.0
    INIT_DATA_MAX_AGE_SECONDS: int = 86400

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()

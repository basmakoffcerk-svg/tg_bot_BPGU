"""
Конфигурация приложения АРМ Старосты (Pydantic Settings).
"""
import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Telegram
    BOT_TOKEN: str = "123456789:TEST_BOT_TOKEN_ABCDEFGHIJKLMN"
    STAROSTA_TELEGRAM_ID: int = 987654321
    GROUP_CHAT_ID: int = -1001234567890

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    APP_ENV: str = "development"
    TIMEZONE: str = "Europe/Moscow"
    WEBHOOK_URL: str = ""
    WEBHOOK_SECRET: str = "secret_webhook_token"
    FRONTEND_URL: str = "http://localhost:8000"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///data/database.sqlite"
    BACKUP_DIR: str = "data/backups"

    # Geocheckin Parameters
    MAX_ALLOWED_DISTANCE_METERS: float = 150.0
    MAX_GPS_ACCURACY_METERS: float = 50.0
    CHECKIN_WINDOW_BEFORE_MINUTES: int = 5
    CHECKIN_WINDOW_AFTER_MINUTES: int = 15


settings = Settings()

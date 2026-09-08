import os
from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


def get_default_database_url() -> str:
    # 1. External Postgres / Neon
    env_db = os.environ.get("POSTGRES_URL") or os.environ.get("POSTGRES_PRISMA_URL") or os.environ.get("DATABASE_URL")
    if env_db:
        return env_db
    # 2. Vercel / Serverless -> /tmp (writable)
    if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return "sqlite+aiosqlite:////tmp/database.sqlite"
    # 3. Local development
    return "sqlite+aiosqlite:///data/database.sqlite"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Telegram
    BOT_TOKEN: str = "8713079092:AAG6B-YEpmQ4hl7-xuQtOc2XlrSDG0gSvcw"
    STAROSTA_TELEGRAM_ID: int = 1131010316
    GROUP_CHAT_ID: int = -1001234567890

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    APP_ENV: str = "production"
    TIMEZONE: str = "Europe/Minsk"
    WEBHOOK_URL: str = ""
    WEBHOOK_SECRET: str = ""
    FRONTEND_URL: str = "https://tg-bot-bpgu240326.vercel.app"

    # Database
    DATABASE_URL: str = get_default_database_url()
    BACKUP_DIR: str = "/tmp/backups" if os.environ.get("VERCEL") else "data/backups"

    # Geocheckin Parameters
    MAX_ALLOWED_DISTANCE_METERS: float = 150.0
    MAX_GPS_ACCURACY_METERS: float = 50.0
    CHECKIN_WINDOW_BEFORE_MINUTES: int = 5
    CHECKIN_WINDOW_AFTER_MINUTES: int = 15


settings = Settings()


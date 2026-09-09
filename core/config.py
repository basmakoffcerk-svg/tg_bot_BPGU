from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Telegram
    BOT_TOKEN: str = "123456789:AAHfdjsdhfkjsdfhkjsdfhksjdfhksjdfh"
    STAROSTA_TELEGRAM_ID: int = 123456789
    GROUP_CHAT_ID: int = -1001234567890

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    APP_ENV: str = "development"
    TIMEZONE: str = "Europe/Minsk"
    WEBHOOK_URL: str = ""
    WEBHOOK_SECRET: str = ""
    FRONTEND_URL: str = "*"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///data/database.sqlite"
    BACKUP_DIR: str = "data/backups"

    # Geocheckin parameters
    MAX_ALLOWED_DISTANCE_METERS: float = 150.0
    MAX_GPS_ACCURACY_METERS: float = 50.0
    CHECKIN_WINDOW_BEFORE_MINUTES: int = 5
    CHECKIN_WINDOW_AFTER_MINUTES: int = 15


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()

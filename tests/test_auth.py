import time

from core.config import settings
from core.security import generate_test_init_data, validate_telegram_init_data


def test_valid_init_data_verification():
    bot_token = settings.BOT_TOKEN
    init_data = generate_test_init_data(123456, bot_token, "Test", "User")

    result = validate_telegram_init_data(init_data, bot_token)
    assert result is not None
    assert "user" in result
    assert result.get("auth_date") is not None


def test_corrupted_hash_verification():
    bot_token = settings.BOT_TOKEN
    init_data = generate_test_init_data(123456, bot_token, "Test", "User")
    # Tamper with hash
    corrupted_data = init_data[:-4] + "ffff"

    result = validate_telegram_init_data(corrupted_data, bot_token)
    assert result is None


def test_expired_auth_date_verification():
    bot_token = settings.BOT_TOKEN
    # Auth date 2 days ago
    expired_date = int(time.time()) - (86400 * 2)
    init_data = generate_test_init_data(123456, bot_token, "Test", "User", auth_date=expired_date)

    result = validate_telegram_init_data(init_data, bot_token, max_age_seconds=86400)
    assert result is None


def test_empty_or_malformed_init_data():
    bot_token = settings.BOT_TOKEN
    assert validate_telegram_init_data("", bot_token) is None
    assert validate_telegram_init_data("not_a_valid_string", bot_token) is None
    assert validate_telegram_init_data("key=value", bot_token) is None

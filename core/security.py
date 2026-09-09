import hashlib
import hmac
import json
import time
from urllib.parse import parse_qsl

# Fast in-memory cache for validated tokens (hash -> (parsed_data, timestamp))
_VALIDATION_CACHE: dict[str, tuple[dict, float]] = {}
_CACHE_TTL_SECONDS = 60.0


def clean_validation_cache() -> None:
    now = time.time()
    expired = [k for k, v in _VALIDATION_CACHE.items() if now - v[1] > _CACHE_TTL_SECONDS]
    for k in expired:
        _VALIDATION_CACHE.pop(k, None)


def validate_telegram_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> dict | None:
    """
    Validates Telegram WebApp initData string according to Telegram specification:
    1. Parse query string
    2. Extract hash
    3. Construct data_check_string from sorted key=value pairs (excluding hash)
    4. secret_key = HMAC_SHA256("WebAppData", bot_token)
    5. calculated_hash = HMAC_SHA256(secret_key, data_check_string).hexdigest()
    6. Verify HMAC match and auth_date freshness (<= max_age_seconds)
    """
    if not init_data:
        return None

    # Check fast cache
    now = time.time()
    if init_data in _VALIDATION_CACHE:
        cached_data, cached_ts = _VALIDATION_CACHE[init_data]
        if now - cached_ts <= _CACHE_TTL_SECONDS:
            return cached_data
        else:
            _VALIDATION_CACHE.pop(init_data, None)

    try:
        # Step 1: Parse query string
        parsed_items = parse_qsl(init_data, keep_blank_values=True)
        parsed = dict(parsed_items)

        received_hash = parsed.pop("hash", None)
        if not received_hash:
            return None

        # Step 2: Check auth_date
        auth_date_str = parsed.get("auth_date")
        if not auth_date_str or not auth_date_str.isdigit():
            return None

        auth_date = int(auth_date_str)
        if max_age_seconds > 0 and (now - auth_date > max_age_seconds):
            return None

        # Step 3: Construct data_check_string
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items(), key=lambda item: item[0]))

        # Step 4: Calculate secret_key and check hash
        secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
        calculated_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

        if hmac.compare_digest(calculated_hash, received_hash):
            # Parse 'user' if present
            if "user" in parsed and isinstance(parsed["user"], str):
                try:
                    parsed["user_obj"] = json.loads(parsed["user"])
                except Exception:
                    pass
            # Cache result
            _VALIDATION_CACHE[init_data] = (parsed, now)
            if len(_VALIDATION_CACHE) > 5000:
                clean_validation_cache()
            return parsed

        return None
    except Exception:
        return None


def generate_test_init_data(
    user_id: int,
    bot_token: str,
    first_name: str = "Test",
    last_name: str = "User",
    username: str = "testuser",
    auth_date: int | None = None,
) -> str:
    """Helper for generating cryptographically valid initData in tests."""
    if auth_date is None:
        auth_date = int(time.time())

    user_dict = {
        "id": user_id,
        "first_name": first_name,
        "last_name": last_name,
        "username": username,
        "language_code": "ru",
    }
    user_json = json.dumps(user_dict, separators=(",", ":"))

    params = {"auth_date": str(auth_date), "query_id": "AAHd_test", "user": user_json}

    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(params.items(), key=lambda item: item[0]))

    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    hash_val = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()

    from urllib.parse import urlencode

    params_with_hash = dict(params)
    params_with_hash["hash"] = hash_val
    return urlencode(params_with_hash)

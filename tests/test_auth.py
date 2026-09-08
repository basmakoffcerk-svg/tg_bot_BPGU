"""
Tier 1 & Tier 2 Tests: Authentication, HMAC-SHA256 Cryptography & 3-Tier RBAC Engine.
Requirements: ORIGINAL_REQUEST §2, API §2, ARCHITECTURE §3, SRS §2.
"""
import json
import time
import urllib.parse
import pytest
from httpx import AsyncClient

from tests.mock_backend import (
    BOT_TOKEN_DEFAULT,
    ROLE_STAROSTA,
    ROLE_STUDENT,
    ROLE_ZAM,
    calculate_init_data_hash,
    mock_init_data,
    validate_telegram_init_data,
)


# ---------------------------------------------------------------------------
# Cryptographic Validation Unit Tests (Tier 1 & Tier 2)
# ---------------------------------------------------------------------------
def test_hmac_sha256_valid_signature_generation(bot_token: str):
    """Generates authentic HMAC-SHA256 signature matching Telegram specification."""
    user = {"id": 123456, "first_name": "Test", "username": "testuser"}
    init_data = mock_init_data(user, bot_token=bot_token)
    parsed = validate_telegram_init_data(init_data, bot_token=bot_token)
    assert parsed is not None
    assert "user" in parsed
    parsed_user = json.loads(parsed["user"])
    assert parsed_user["id"] == 123456


def test_hmac_sha256_different_token_fails(bot_token: str):
    """Data signed with token A must fail validation when tested against token B."""
    user = {"id": 123456, "first_name": "Test"}
    init_data = mock_init_data(user, bot_token=bot_token)
    wrong_token = "999999999:WRONG_BOT_TOKEN_ZZZZZZZZZZZZ"
    parsed = validate_telegram_init_data(init_data, bot_token=wrong_token)
    assert parsed is None


def test_hmac_sha256_tampered_payload_fails(bot_token: str):
    """Tampering with user ID without recalculating hash must be rejected."""
    user = {"id": 123456, "first_name": "Test"}
    init_data = mock_init_data(user, bot_token=bot_token)
    tampered_data = init_data.replace("123456", "999999")
    parsed = validate_telegram_init_data(tampered_data, bot_token=bot_token)
    assert parsed is None


def test_hmac_sha256_missing_hash_fails(bot_token: str):
    """Payload with missing hash parameter must be rejected."""
    user = {"id": 123456, "first_name": "Test"}
    init_data = mock_init_data(user, bot_token=bot_token)
    pairs = [p for p in init_data.split("&") if not p.startswith("hash=")]
    data_without_hash = "&".join(pairs)
    assert validate_telegram_init_data(data_without_hash, bot_token=bot_token) is None


def test_hmac_sha256_empty_string_fails(bot_token: str):
    """Empty initData string must return None."""
    assert validate_telegram_init_data("", bot_token=bot_token) is None


def test_hmac_sha256_expired_auth_date_boundary_86401(bot_token: str):
    """auth_date older than 86400 seconds (24h + 1s) must be rejected."""
    now = int(time.time())
    user = {"id": 123456, "first_name": "Test"}
    init_data = mock_init_data(user, bot_token=bot_token, auth_date=now - 86401)
    assert validate_telegram_init_data(init_data, bot_token=bot_token) is None


def test_hmac_sha256_valid_auth_date_boundary_86390(bot_token: str):
    """auth_date within 24h (e.g. 23h 59m 50s ago) must be accepted."""
    now = int(time.time())
    user = {"id": 123456, "first_name": "Test"}
    init_data = mock_init_data(user, bot_token=bot_token, auth_date=now - 86390)
    assert validate_telegram_init_data(init_data, bot_token=bot_token) is not None


def test_hmac_sha256_future_auth_date_rejected(bot_token: str):
    """auth_date abnormally in the future (>300 seconds) must be rejected."""
    future_time = int(time.time()) + 400
    user = {"id": 123456, "first_name": "Test"}
    init_data = mock_init_data(user, bot_token=bot_token, auth_date=future_time)
    assert validate_telegram_init_data(init_data, bot_token=bot_token) is None


def test_hmac_sha256_non_numeric_auth_date_fails(bot_token: str):
    """auth_date with non-numeric value must fail gracefully."""
    params = {
        "auth_date": "not_a_timestamp",
        "user": json.dumps({"id": 123456}),
    }
    h = calculate_init_data_hash(params, bot_token)
    params["hash"] = h
    qs = urllib.parse.urlencode(params)
    assert validate_telegram_init_data(qs, bot_token=bot_token) is None


def test_hmac_sha256_arbitrary_param_order_supported(bot_token: str):
    """Verification must sort parameters alphabetically regardless of wire order."""
    now = int(time.time())
    user_json = json.dumps({"id": 123456}, separators=(",", ":"))
    params = {
        "z_param": "last",
        "auth_date": str(now),
        "a_param": "first",
        "user": user_json,
    }
    h = calculate_init_data_hash(params, bot_token)
    # Wire string in reverse sorted order
    wire_qs = f"z_param=last&user={urllib.parse.quote(user_json)}&hash={h}&auth_date={now}&a_param=first"
    parsed = validate_telegram_init_data(wire_qs, bot_token=bot_token)
    assert parsed is not None
    assert parsed.get("a_param") == "first"
    assert parsed.get("z_param") == "last"


def test_hmac_sha256_special_characters_escaping(bot_token: str):
    """Cyrillic characters, emoji, quotes, and slashes must be preserved and verified."""
    user = {
        "id": 123456,
        "first_name": "Пётр-Иван & Co. 🚀",
        "last_name": "O'Connor/Смирнов",
    }
    init_data = mock_init_data(user, bot_token=bot_token)
    parsed = validate_telegram_init_data(init_data, bot_token=bot_token)
    assert parsed is not None
    parsed_user = json.loads(parsed["user"])
    assert parsed_user["first_name"] == "Пётр-Иван & Co. 🚀"
    assert parsed_user["last_name"] == "O'Connor/Смирнов"


# ---------------------------------------------------------------------------
# HTTP REST API Auth & RBAC Endpoint Tests (Tier 1 & Tier 2)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_auth_telegram_success_for_starosta(
    async_client: AsyncClient,
    starosta_auth_header: dict,
):
    """Starosta authentication returns full admin permissions."""
    res = await async_client.post("/api/v1/auth/telegram", headers=starosta_auth_header)
    assert res.status_code == 200
    data = res.json()

    assert data["user"]["role"] == ROLE_STAROSTA
    assert data["user"]["status"] == "ACTIVE"
    assert data["user"]["full_name"] == "Иванов Иван Иванович"

    perms = data["permissions"]
    assert perms["can_view_grid"] is True
    assert perms["can_override_status"] is True
    assert perms["can_lock_pairs"] is True
    assert perms["can_broadcast_critical"] is True
    assert perms["can_export_reports"] is True


@pytest.mark.asyncio
async def test_auth_telegram_success_for_zam(
    async_client: AsyncClient,
    zam_auth_header: dict,
):
    """Deputy (Zam) authentication returns admin permissions excluding lock and critical broadcast."""
    res = await async_client.post("/api/v1/auth/telegram", headers=zam_auth_header)
    assert res.status_code == 200
    data = res.json()

    assert data["user"]["role"] == ROLE_ZAM
    assert data["user"]["status"] == "ACTIVE"
    assert data["user"]["full_name"] == "Константинов Константин Константинович"

    perms = data["permissions"]
    assert perms["can_view_grid"] is True
    assert perms["can_override_status"] is True
    assert perms["can_lock_pairs"] is False
    assert perms["can_broadcast_critical"] is False
    assert perms["can_export_reports"] is True


@pytest.mark.asyncio
async def test_auth_telegram_success_for_student(
    async_client: AsyncClient,
    student_auth_header: dict,
):
    """Regular student authentication returns restricted permissions."""
    res = await async_client.post("/api/v1/auth/telegram", headers=student_auth_header)
    assert res.status_code == 200
    data = res.json()

    assert data["user"]["role"] == ROLE_STUDENT
    assert data["user"]["status"] == "ACTIVE"
    assert data["user"]["subgroup"] == 1

    perms = data["permissions"]
    assert perms["can_view_grid"] is False
    assert perms["can_override_status"] is False
    assert perms["can_lock_pairs"] is False
    assert perms["can_broadcast_critical"] is False
    assert perms["can_export_reports"] is False


@pytest.mark.asyncio
async def test_auth_telegram_returns_current_week_info(
    async_client: AsyncClient,
    student_auth_header: dict,
):
    """Auth endpoint returns academic week information."""
    res = await async_client.post("/api/v1/auth/telegram", headers=student_auth_header)
    assert res.status_code == 200
    data = res.json()
    week = data.get("current_week")
    assert week is not None
    assert "week_number" in week
    assert week.get("week_type") in ("ODD", "EVEN")


@pytest.mark.asyncio
async def test_auth_missing_header_returns_422_or_401(async_client: AsyncClient):
    """Request missing X-Telegram-Init-Data header returns 422 or 401."""
    res = await async_client.post("/api/v1/auth/telegram", headers={})
    assert res.status_code in (401, 422)


@pytest.mark.asyncio
async def test_auth_invalid_signature_returns_401(
    async_client: AsyncClient,
    invalid_hash_auth_header: dict,
):
    """Forged or corrupted hash returns 401 Unauthorized."""
    res = await async_client.post("/api/v1/auth/telegram", headers=invalid_hash_auth_header)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_auth_expired_signature_returns_401(
    async_client: AsyncClient,
    expired_auth_header: dict,
):
    """auth_date older than 24h returns 401 Unauthorized."""
    res = await async_client.post("/api/v1/auth/telegram", headers=expired_auth_header)
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_auth_unknown_telegram_user_returns_401(
    async_client: AsyncClient,
    bot_token: str,
):
    """Telegram ID that is validly signed but not in whitelist database returns 401."""
    unknown_user = {"id": 888888888, "first_name": "Stranger"}
    init_data = mock_init_data(unknown_user, bot_token=bot_token)
    res = await async_client.post(
        "/api/v1/auth/telegram",
        headers={"X-Telegram-Init-Data": init_data},
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_auth_pending_approval_user_returns_403(
    async_client: AsyncClient,
    bot_token: str,
    db_session,
):
    """User in PENDING state receives 403 Forbidden until starosta approves."""
    from tests.mock_backend import Student
    from sqlalchemy import select

    # Look up the pending student
    st = (await db_session.execute(select(Student).where(Student.status == "PENDING"))).scalar_one_or_none()
    if st:
        st.telegram_id = 777777777
        await db_session.commit()

        pending_user = {"id": 777777777, "first_name": "Pending"}
        init_data = mock_init_data(pending_user, bot_token=bot_token)
        res = await async_client.post(
            "/api/v1/auth/telegram",
            headers={"X-Telegram-Init-Data": init_data},
        )
        assert res.status_code == 403


@pytest.mark.asyncio
async def test_rbac_student_forbidden_to_access_grid(
    async_client: AsyncClient,
    student_auth_header: dict,
):
    """Student role is strictly forbidden (403) from accessing starosta attendance grid."""
    res = await async_client.get("/api/v1/attendance/grid/1", headers=student_auth_header)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_rbac_student_forbidden_to_override_attendance(
    async_client: AsyncClient,
    student_auth_header: dict,
):
    """Student role is strictly forbidden (403) from overriding attendance."""
    payload = {"pair_id": 1, "student_id": 1, "new_status": "MANUAL_CONFIRM"}
    res = await async_client.patch("/api/v1/attendance/override", json=payload, headers=student_auth_header)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_rbac_student_forbidden_to_lock_pair(
    async_client: AsyncClient,
    student_auth_header: dict,
):
    """Student role is strictly forbidden (403) from locking a pair."""
    res = await async_client.post("/api/v1/attendance/lock/1", headers=student_auth_header)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_rbac_zam_forbidden_to_lock_pair(
    async_client: AsyncClient,
    zam_auth_header: dict,
):
    """Deputy (Zam) is forbidden (403) from locking a pair (Starosta-only privilege)."""
    res = await async_client.post("/api/v1/attendance/lock/1", headers=zam_auth_header)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_rbac_zam_forbidden_to_broadcast_critical(
    async_client: AsyncClient,
    zam_auth_header: dict,
):
    """Deputy (Zam) is forbidden (403) from sending CRITICAL alerts (Starosta-only)."""
    payload = {"type": "CRITICAL", "title": "Fire drill", "body": "Evacuate building!"}
    res = await async_client.post("/api/v1/alerts/broadcast", json=payload, headers=zam_auth_header)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_rbac_zam_allowed_to_access_grid(
    async_client: AsyncClient,
    zam_auth_header: dict,
):
    """Deputy (Zam) has permission (200) to view attendance grid."""
    res = await async_client.get("/api/v1/attendance/grid/1", headers=zam_auth_header)
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_rbac_zam_allowed_to_override_status(
    async_client: AsyncClient,
    zam_auth_header: dict,
):
    """Deputy (Zam) has permission (200) to override student attendance status."""
    payload = {
        "pair_id": 1,
        "student_id": 1,
        "new_status": "MANUAL_CONFIRM",
        "excuse_reason": "Low battery",
    }
    res = await async_client.patch("/api/v1/attendance/override", json=payload, headers=zam_auth_header)
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_rbac_starosta_allowed_all_admin_actions(
    async_client: AsyncClient,
    starosta_auth_header: dict,
):
    """Starosta can access grid, override status, and lock pair."""
    res_grid = await async_client.get("/api/v1/attendance/grid/1", headers=starosta_auth_header)
    assert res_grid.status_code == 200

    res_override = await async_client.patch(
        "/api/v1/attendance/override",
        json={"pair_id": 1, "student_id": 2, "new_status": "ABSENT_EXCUSED", "excuse_reason": "Doctor note"},
        headers=starosta_auth_header,
    )
    assert res_override.status_code == 200

    res_lock = await async_client.post("/api/v1/attendance/lock/1", headers=starosta_auth_header)
    assert res_lock.status_code == 200


@pytest.mark.asyncio
async def test_auth_replay_attack_prevention_on_stale_token(
    async_client: AsyncClient,
    student1_user_dict: dict,
    bot_token: str,
):
    """Replay of captured initData after 24h period fails."""
    stale_ts = int(time.time()) - 86500
    stale_init_data = mock_init_data(student1_user_dict, bot_token=bot_token, auth_date=stale_ts)
    res = await async_client.post(
        "/api/v1/auth/telegram",
        headers={"X-Telegram-Init-Data": stale_init_data},
    )
    assert res.status_code == 401

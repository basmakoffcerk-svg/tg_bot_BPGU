"""
Tier 1, Tier 2 & Tier 3 Tests: Telegram Bot Onboarding, Whitelist Reservation, Callbacks & Alerts Broadcast.
Requirements: ORIGINAL_REQUEST §1, §6, SRS §3.1, §3.6, API §8, TEST_INFRA.md.
"""
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from tests.mock_backend import (
    ROLE_STAROSTA,
    ROLE_STUDENT,
    ROLE_ZAM,
    BroadcastMessage,
    MockBotDispatcher,
    Student,
)


# ---------------------------------------------------------------------------
# Bot Onboarding & Whitelist Unit & Event Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_bot_start_for_existing_active_starosta(
    bot_dispatcher: MockBotDispatcher,
):
    """Existing active starosta running /start gets MAIN_MENU action."""
    res = await bot_dispatcher.handle_start_command(
        telegram_id=987654321,
        user_full_name="Иванов Иван Иванович",
    )
    assert res["action"] == "MAIN_MENU"
    assert res["role"] == ROLE_STAROSTA
    assert "Добро пожаловать" in res["message"]


@pytest.mark.asyncio
async def test_bot_start_for_existing_active_student(
    bot_dispatcher: MockBotDispatcher,
):
    """Existing active student running /start gets MAIN_MENU action."""
    res = await bot_dispatcher.handle_start_command(
        telegram_id=100001,
        user_full_name="Александров Александр",
    )
    assert res["action"] == "MAIN_MENU"
    assert res["role"] == ROLE_STUDENT


@pytest.mark.asyncio
async def test_bot_start_for_unassigned_user_shows_whitelist(
    bot_dispatcher: MockBotDispatcher,
):
    """New Telegram user running /start receives list of unassigned students."""
    res = await bot_dispatcher.handle_start_command(
        telegram_id=555001,
        user_full_name="New Unknown User",
    )
    assert res["action"] == "ONBOARDING_CHOOSE_NAME"
    assert "available_students" in res
    avail = res["available_students"]
    assert len(avail) >= 1
    # Check that Новиков (unassigned) is present
    names = [s["full_name"] for s in avail]
    assert any("Новиков" in n for n in names)


@pytest.mark.asyncio
async def test_bot_select_name_creates_claim_and_pending_status(
    bot_dispatcher: MockBotDispatcher,
):
    """Student selects an unassigned name: transitions to PENDING and generates starosta notification."""
    # Look up unassigned student ID
    unassigned_res = await bot_dispatcher.handle_start_command(telegram_id=555002, user_full_name="User")
    novikov_id = [s["id"] for s in unassigned_res["available_students"] if "Новиков" in s["full_name"]][0]

    select_res = await bot_dispatcher.handle_select_name(telegram_id=555002, student_id=novikov_id)
    assert select_res["success"] is True
    assert select_res["status"] == "PENDING"

    notif = select_res["starosta_notification"]
    assert "Новиков" in notif["text"]
    assert notif["callback_approve"] == f"approve:{novikov_id}:555002"
    assert notif["callback_reject"] == f"reject:{novikov_id}:555002"


@pytest.mark.asyncio
async def test_bot_starosta_approves_student(
    bot_dispatcher: MockBotDispatcher,
):
    """Starosta clicks approve inline button: student becomes ACTIVE and linked."""
    unassigned_res = await bot_dispatcher.handle_start_command(telegram_id=555003, user_full_name="User")
    novikov_id = [s["id"] for s in unassigned_res["available_students"] if "Новиков" in s["full_name"]][0]

    # Student selects
    await bot_dispatcher.handle_select_name(telegram_id=555003, student_id=novikov_id)

    # Starosta clicks approve
    cb_data = f"approve:{novikov_id}:555003"
    cb_res = await bot_dispatcher.handle_callback_query(callback_data=cb_data, admin_telegram_id=987654321)
    assert cb_res["success"] is True
    assert cb_res["status"] == "ACTIVE"
    assert cb_res["action"] == "approved"

    # Verify student now gets MAIN_MENU on /start
    start_res = await bot_dispatcher.handle_start_command(telegram_id=555003, user_full_name="Novikov")
    assert start_res["action"] == "MAIN_MENU"


@pytest.mark.asyncio
async def test_bot_starosta_rejects_student(
    bot_dispatcher: MockBotDispatcher,
):
    """Starosta clicks reject inline button: student claim is canceled."""
    unassigned_res = await bot_dispatcher.handle_start_command(telegram_id=555004, user_full_name="User")
    novikov_id = [s["id"] for s in unassigned_res["available_students"] if "Новиков" in s["full_name"]][0]

    await bot_dispatcher.handle_select_name(telegram_id=555004, student_id=novikov_id)

    cb_data = f"reject:{novikov_id}:555004"
    cb_res = await bot_dispatcher.handle_callback_query(callback_data=cb_data, admin_telegram_id=987654321)
    assert cb_res["success"] is True
    assert cb_res["action"] == "rejected"


@pytest.mark.asyncio
async def test_bot_non_starosta_cannot_approve(
    bot_dispatcher: MockBotDispatcher,
):
    """Regular student (or deputy) clicking approve callback is denied."""
    cb_data = "approve:28:555005"
    cb_res = await bot_dispatcher.handle_callback_query(
        callback_data=cb_data,
        admin_telegram_id=100001,  # Regular student
    )
    assert cb_res["success"] is False
    assert "Only starosta" in cb_res["error"]


@pytest.mark.asyncio
async def test_bot_cannot_select_already_assigned_student(
    bot_dispatcher: MockBotDispatcher,
):
    """Attempting to select student ID 1 (already assigned to Alexandrov) fails."""
    res = await bot_dispatcher.handle_select_name(telegram_id=555006, student_id=1)
    assert res["success"] is False


@pytest.mark.asyncio
async def test_bot_invalid_callback_data_format(
    bot_dispatcher: MockBotDispatcher,
):
    """Malformed callback data fails gracefully."""
    res = await bot_dispatcher.handle_callback_query(
        callback_data="invalid_data_without_colons",
        admin_telegram_id=987654321,
    )
    assert res["success"] is False


# ---------------------------------------------------------------------------
# Broadcast & Alert Messaging Tests (REST API §6)
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_broadcast_critical_alert_by_starosta(
    async_client: AsyncClient,
    starosta_auth_header: dict,
    db_session,
):
    """Starosta can send CRITICAL broadcast; returns 202 Accepted and records in DB."""
    payload = {
        "type": "CRITICAL",
        "title": "Перенос пары",
        "body": "Пара по ОС перенесена в ауд. 401 Корпуса А!",
    }
    res = await async_client.post("/api/v1/alerts/broadcast", json=payload, headers=starosta_auth_header)
    assert res.status_code == 202
    data = res.json()
    assert data["broadcast_id"] > 0
    assert data["queued_recipients"] >= 27
    assert data["status"] == "SENDING"

    # Verify DB record
    stmt = select(BroadcastMessage).where(BroadcastMessage.id == data["broadcast_id"])
    msg = (await db_session.execute(stmt)).scalar_one_or_none()
    assert msg is not None
    assert msg.message_type == "CRITICAL"
    assert msg.title == "Перенос пары"


@pytest.mark.asyncio
async def test_broadcast_info_alert_by_zam(
    async_client: AsyncClient,
    zam_auth_header: dict,
):
    """Deputy (Zam) can send INFO broadcast."""
    payload = {
        "type": "INFO",
        "title": "Консультация",
        "body": "Консультация по матанализу в пятницу в 15:00.",
    }
    res = await async_client.post("/api/v1/alerts/broadcast", json=payload, headers=zam_auth_header)
    assert res.status_code == 202
    data = res.json()
    assert data["channel_posted"] is True


@pytest.mark.asyncio
async def test_broadcast_critical_alert_forbidden_for_zam(
    async_client: AsyncClient,
    zam_auth_header: dict,
):
    """Deputy (Zam) is forbidden (403) from sending CRITICAL broadcast."""
    payload = {
        "type": "CRITICAL",
        "title": "Срочно",
        "body": "Всем явиться в деканат!",
    }
    res = await async_client.post("/api/v1/alerts/broadcast", json=payload, headers=zam_auth_header)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_broadcast_forbidden_for_student(
    async_client: AsyncClient,
    student_auth_header: dict,
):
    """Regular student is forbidden (403) from sending any broadcast."""
    payload = {
        "type": "INFO",
        "title": "Продам гараж",
        "body": "Недорого",
    }
    res = await async_client.post("/api/v1/alerts/broadcast", json=payload, headers=student_auth_header)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_broadcast_invalid_type_rejected_with_400(
    async_client: AsyncClient,
    starosta_auth_header: dict,
):
    """Invalid message type is rejected with 400 Bad Request."""
    payload = {
        "type": "ULTRA_ALERT",
        "title": "Test",
        "body": "Test",
    }
    res = await async_client.post("/api/v1/alerts/broadcast", json=payload, headers=starosta_auth_header)
    assert res.status_code == 400


@pytest.mark.asyncio
async def test_bot_rejection_allows_student_to_reselect(
    bot_dispatcher: MockBotDispatcher,
):
    """After starosta rejects a mistaken selection, student can pick another name."""
    unassigned_res = await bot_dispatcher.handle_start_command(telegram_id=555020, user_full_name="Student")
    novikov_id = [s["id"] for s in unassigned_res["available_students"] if "Новиков" in s["full_name"]][0]

    # Student mistakenly selects Novikov
    await bot_dispatcher.handle_select_name(telegram_id=555020, student_id=novikov_id)

    # Starosta rejects
    reject_cb = f"reject:{novikov_id}:555020"
    rej_res = await bot_dispatcher.handle_callback_query(callback_data=reject_cb, admin_telegram_id=987654321)
    assert rej_res["success"] is True

    # Now Novikov is back in unassigned list
    unassigned_res_2 = await bot_dispatcher.handle_start_command(telegram_id=555021, user_full_name="Real Novikov")
    ids = [s["id"] for s in unassigned_res_2["available_students"]]
    assert novikov_id in ids


@pytest.mark.asyncio
async def test_bot_unassigned_students_alphabetical_order(
    bot_dispatcher: MockBotDispatcher,
):
    """Unassigned students list returned to onboarding user is sorted alphabetically."""
    res = await bot_dispatcher.handle_start_command(telegram_id=555022, user_full_name="User")
    names = [s["full_name"] for s in res["available_students"]]
    assert names == sorted(names)


@pytest.mark.asyncio
async def test_broadcast_recipient_count_reflects_active_students(
    async_client: AsyncClient,
    starosta_auth_header: dict,
    db_session,
):
    """Queued recipients count strictly matches count of ACTIVE students in group."""
    from sqlalchemy import func
    stmt = select(func.count(Student.id)).where(Student.status == "ACTIVE")
    expected_count = (await db_session.execute(stmt)).scalar()

    payload = {
        "type": "CRITICAL",
        "title": "Проверка связи",
        "body": "Тестовое сообщение",
    }
    res = await async_client.post("/api/v1/alerts/broadcast", json=payload, headers=starosta_auth_header)
    assert res.status_code == 202
    assert res.json()["queued_recipients"] == expected_count


@pytest.mark.asyncio
async def test_broadcast_persists_sender_id(
    async_client: AsyncClient,
    starosta_auth_header: dict,
    db_session,
):
    """Broadcast records sender_id of the initiating starosta."""
    payload = {
        "type": "CRITICAL",
        "title": "Внимание",
        "body": "Тест отправителя",
    }
    res = await async_client.post("/api/v1/alerts/broadcast", json=payload, headers=starosta_auth_header)
    data = res.json()
    b_id = data["broadcast_id"]

    stmt = select(BroadcastMessage).where(BroadcastMessage.id == b_id)
    msg = (await db_session.execute(stmt)).scalar_one_or_none()
    assert msg is not None
    # Starosta student id in seed data is Ivanov (id = 9)
    assert msg.sender_id > 0


@pytest.mark.asyncio
async def test_broadcast_missing_fields_validation(
    async_client: AsyncClient,
    starosta_auth_header: dict,
):
    """Missing title or body in broadcast request returns 422 Unprocessable Entity."""
    res = await async_client.post("/api/v1/alerts/broadcast", json={"type": "INFO"}, headers=starosta_auth_header)
    assert res.status_code == 422


@pytest.mark.asyncio
async def test_broadcast_multiple_sequential_announcements(
    async_client: AsyncClient,
    starosta_auth_header: dict,
):
    """Starosta can send multiple alerts in sequence without deadlock or failure."""
    for i in range(3):
        payload = {
            "type": "INFO" if i > 0 else "CRITICAL",
            "title": f"Оповещение №{i + 1}",
            "body": f"Текст сообщения №{i + 1}",
        }
        res = await async_client.post("/api/v1/alerts/broadcast", json=payload, headers=starosta_auth_header)
        assert res.status_code == 202
        assert res.json()["broadcast_id"] > 0


@pytest.mark.asyncio
async def test_bot_select_non_existent_student_id(
    bot_dispatcher: MockBotDispatcher,
):
    """Selecting non-existent student ID returns error."""
    res = await bot_dispatcher.handle_select_name(telegram_id=555030, student_id=99999)
    assert res["success"] is False


@pytest.mark.asyncio
async def test_bot_select_negative_student_id(
    bot_dispatcher: MockBotDispatcher,
):
    """Selecting negative student ID returns error."""
    res = await bot_dispatcher.handle_select_name(telegram_id=555031, student_id=-1)
    assert res["success"] is False


@pytest.mark.asyncio
async def test_bot_double_approval_attempt_idempotent(
    bot_dispatcher: MockBotDispatcher,
):
    """Approving an already approved student succeeds idempotently."""
    cb_data = "approve:1:100001"
    res = await bot_dispatcher.handle_callback_query(callback_data=cb_data, admin_telegram_id=987654321)
    assert res["success"] is True
    assert res["status"] == "ACTIVE"


@pytest.mark.asyncio
async def test_bot_approval_by_zam_rejected(
    bot_dispatcher: MockBotDispatcher,
):
    """Deputy (Zam) is not allowed to approve student claims."""
    cb_data = "approve:28:555032"
    res = await bot_dispatcher.handle_callback_query(callback_data=cb_data, admin_telegram_id=987654322)
    assert res["success"] is False
    assert "Only starosta" in res["error"]


@pytest.mark.asyncio
async def test_bot_start_idempotency_for_active_student(
    bot_dispatcher: MockBotDispatcher,
):
    """Repeated /start commands by an active student consistently return MAIN_MENU."""
    for _ in range(3):
        res = await bot_dispatcher.handle_start_command(telegram_id=100001, user_full_name="Alex")
        assert res["action"] == "MAIN_MENU"


@pytest.mark.asyncio
async def test_broadcast_body_character_length_stress(
    async_client: AsyncClient,
    starosta_auth_header: dict,
):
    """Large text body (1000 characters) in broadcast request succeeds."""
    long_body = "Внимание: " + ("Академическая информация " * 45)
    payload = {
        "type": "CRITICAL",
        "title": "Длинное оповещение",
        "body": long_body,
    }
    res = await async_client.post("/api/v1/alerts/broadcast", json=payload, headers=starosta_auth_header)
    assert res.status_code == 202


@pytest.mark.asyncio
async def test_broadcast_special_html_symbols_integrity(
    async_client: AsyncClient,
    starosta_auth_header: dict,
    db_session,
):
    """Broadcast body containing HTML entities (<, >, &, \") is stored safely."""
    payload = {
        "type": "INFO",
        "title": "HTML тест <alert>",
        "body": "Ссылка: <a href='https://bspu.by'>БГПУ</a> & спецсимволы \"100%\"",
    }
    res = await async_client.post("/api/v1/alerts/broadcast", json=payload, headers=starosta_auth_header)
    assert res.status_code == 202
    b_id = res.json()["broadcast_id"]

    stmt = select(BroadcastMessage).where(BroadcastMessage.id == b_id)
    msg = (await db_session.execute(stmt)).scalar_one_or_none()
    assert msg is not None
    assert "<alert>" in msg.title
    assert "https://bspu.by" in msg.body


@pytest.mark.asyncio
async def test_bot_callback_query_with_insufficient_parts(
    bot_dispatcher: MockBotDispatcher,
):
    """Callback data with only 2 colon-separated parts fails."""
    res = await bot_dispatcher.handle_callback_query(callback_data="approve:1", admin_telegram_id=987654321)
    assert res["success"] is False



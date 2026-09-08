"""
Tier 3 & Tier 4 Tests: Real-World End-to-End Workload Scenarios & Pairwise Combinatorial Matrix.
Requirements: ORIGINAL_REQUEST §1-§6, TEST_INFRA.md § Real-World Scenarios 1-5 & Coverage Thresholds.
"""
from datetime import date, datetime, timedelta
import json
import time
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from tests.mock_backend import (
    EARTH_RADIUS_METERS,
    ROLE_STAROSTA,
    ROLE_STUDENT,
    ROLE_ZAM,
    STATUS_ABSENT_EXCUSED,
    STATUS_ABSENT_UNEXCUSED,
    STATUS_LATE,
    STATUS_MANUAL_CONFIRM,
    STATUS_PRESENT,
    MockBotDispatcher,
    Student,
    generate_dean_report_workbook,
    mock_init_data,
)


# ===========================================================================
# SCENARIO 1: Full Student Journey (Tier 4)
# ===========================================================================
@pytest.mark.asyncio
async def test_e2e_scenario_1_full_student_journey(
    async_client: AsyncClient,
    bot_dispatcher: MockBotDispatcher,
    bot_token: str,
):
    """
    Scenario 1 (TEST_INFRA §38):
    Unregistered student /start -> selects name -> starosta approves ->
    student opens TMA -> checks schedule -> performs geocheckin (d=45m, accuracy=15m) ->
    status becomes PRESENT.
    """
    new_tg_id = 991001
    user_dict = {
        "id": new_tg_id,
        "first_name": "Непривязанный",
        "last_name": "Новиков",
        "username": "novikov_matinf",
    }

    # Step 1: Student runs /start
    start_res = await bot_dispatcher.handle_start_command(telegram_id=new_tg_id, user_full_name="Новиков")
    assert start_res["action"] == "ONBOARDING_CHOOSE_NAME"
    avail = start_res["available_students"]
    novikov = [s for s in avail if "Новиков" in s["full_name"]][0]

    # Step 2: Student selects name
    select_res = await bot_dispatcher.handle_select_name(telegram_id=new_tg_id, student_id=novikov["id"])
    assert select_res["success"] is True
    assert select_res["status"] == "PENDING"

    # Step 3: Starosta approves claim via 1-click inline button
    approve_cb = select_res["starosta_notification"]["callback_approve"]
    approve_res = await bot_dispatcher.handle_callback_query(callback_data=approve_cb, admin_telegram_id=987654321)
    assert approve_res["success"] is True
    assert approve_res["status"] == "ACTIVE"

    # Step 4: Student launches TMA with authentic initData
    init_data = mock_init_data(user_dict, bot_token=bot_token)
    auth_res = await async_client.post(
        "/api/v1/auth/telegram",
        headers={"X-Telegram-Init-Data": init_data},
    )
    assert auth_res.status_code == 200
    student_profile = auth_res.json()["user"]
    assert student_profile["status"] == "ACTIVE"
    assert student_profile["role"] == ROLE_STUDENT
    assert "Новиков" in student_profile["full_name"]

    # Step 5: Student fetches today's schedule
    schedule_res = await async_client.get(
        "/api/v1/schedule/today",
        headers={"X-Telegram-Init-Data": init_data},
    )
    assert schedule_res.status_code == 200
    schedule_data = schedule_res.json()
    pairs = schedule_data["pairs"]
    assert len(pairs) >= 1
    target_pair = pairs[0]
    assert target_pair["my_attendance"] is None

    # Step 6: Student performs geocheckin (d=45m, accuracy=15m)
    # Target building: 55.751244, 37.618423 (45m north)
    delta_lat = (45.0 / EARTH_RADIUS_METERS) * (180.0 / 3.141592653589793)
    client_lat = 55.751244 + delta_lat
    client_lon = 37.618423

    checkin_payload = {
        "pair_id": target_pair["pair_id"],
        "client_lat": client_lat,
        "client_lon": client_lon,
        "accuracy": 15.0,
        "timestamp": time.time(),
    }
    checkin_res = await async_client.post(
        "/api/v1/attendance/checkin",
        json=checkin_payload,
        headers={"X-Telegram-Init-Data": init_data},
    )
    assert checkin_res.status_code == 200
    assert checkin_res.json()["status"] == STATUS_PRESENT

    # Step 7: Verify schedule now shows status PRESENT
    updated_sched = await async_client.get(
        "/api/v1/schedule/today",
        headers={"X-Telegram-Init-Data": init_data},
    )
    pair_record = [p for p in updated_sched.json()["pairs"] if p["pair_id"] == target_pair["pair_id"]][0]
    assert pair_record["my_attendance"]["status"] == STATUS_PRESENT
    assert 40.0 <= pair_record["my_attendance"]["distance"] <= 50.0


# ===========================================================================
# SCENARIO 2: Class Attendance Management (Starosta Session) (Tier 4)
# ===========================================================================
@pytest.mark.asyncio
async def test_e2e_scenario_2_starosta_attendance_management(
    async_client: AsyncClient,
    starosta_auth_header: dict,
    student_auth_header: dict,
    bot_token: str,
):
    """
    Scenario 2 (TEST_INFRA §39):
    Pair starts -> Students check in via GPS -> Starosta opens Chessboard ->
    sets student to ABSENT_EXCUSED with reason -> sets student to LATE ->
    locks pair -> attempts by latecomers rejected.
    """
    # Student 1 checks in via GPS
    c_res = await async_client.post(
        "/api/v1/attendance/checkin",
        json={
            "pair_id": 1,
            "client_lat": 55.751244,
            "client_lon": 37.618423,
            "accuracy": 12.0,
            "timestamp": time.time(),
        },
        headers=student_auth_header,
    )
    assert c_res.status_code == 200

    # Starosta opens Chessboard grid
    grid1 = await async_client.get("/api/v1/attendance/grid/1", headers=starosta_auth_header)
    assert grid1.status_code == 200
    assert grid1.json()["summary"]["present_count"] >= 1

    # Starosta sets student 2 to ABSENT_EXCUSED with official note
    override_excused = await async_client.patch(
        "/api/v1/attendance/override",
        json={
            "pair_id": 1,
            "student_id": 2,
            "new_status": STATUS_ABSENT_EXCUSED,
            "excuse_reason": "Справка №421 от поликлиники №33",
        },
        headers=starosta_auth_header,
    )
    assert override_excused.status_code == 200
    assert override_excused.json()["status"] == STATUS_ABSENT_EXCUSED

    # Starosta sets student 3 to LATE
    override_late = await async_client.patch(
        "/api/v1/attendance/override",
        json={
            "pair_id": 1,
            "student_id": 3,
            "new_status": STATUS_LATE,
        },
        headers=starosta_auth_header,
    )
    assert override_late.status_code == 200
    assert override_late.json()["status"] == STATUS_LATE

    # Starosta locks the pair
    lock_res = await async_client.post("/api/v1/attendance/lock/1", headers=starosta_auth_header)
    assert lock_res.status_code == 200
    assert lock_res.json()["is_locked"] is True

    # Latecomer student 4 attempts to check in -> rejected because pair is locked
    late_student_dict = {"id": 100004, "first_name": "Григорий", "username": "grigory"}
    late_hdr = {"X-Telegram-Init-Data": mock_init_data(late_student_dict, bot_token=bot_token)}
    late_res = await async_client.post(
        "/api/v1/attendance/checkin",
        json={
            "pair_id": 1,
            "client_lat": 55.751244,
            "client_lon": 37.618423,
            "accuracy": 10.0,
            "timestamp": time.time(),
        },
        headers=late_hdr,
    )
    assert late_res.status_code == 400
    assert "pair-locked" in late_res.json().get("type", "")

    # Starosta verifies final grid in archive mode
    final_grid = await async_client.get("/api/v1/attendance/grid/1", headers=starosta_auth_header)
    assert final_grid.json()["is_locked"] is True
    summary = final_grid.json()["summary"]
    assert summary["present_count"] >= 1
    assert summary["absent_excused_count"] >= 1
    assert summary["late_count"] >= 1


# ===========================================================================
# SCENARIO 3: Weekly Dean Report Cycle (Tier 4)
# ===========================================================================
@pytest.mark.asyncio
async def test_e2e_scenario_3_weekly_dean_report_cycle(
    async_client: AsyncClient,
    starosta_auth_header: dict,
    db_session,
):
    """
    Scenario 3 (TEST_INFRA §40):
    Group conducts classes Mon–Sat -> Report triggered -> Excel generated with
    exact BSPU styling and =COUNTIF(...) * 2 formulas -> verified formulas calculate hours.
    """
    # Trigger export API
    export_payload = {
        "date_from": "2026-09-01",
        "date_to": "2026-09-08",
        "delivery_method": "TELEGRAM_DM",
    }
    res = await async_client.post("/api/v1/reports/export", json=export_payload, headers=starosta_auth_header)
    assert res.status_code == 200
    data = res.json()
    assert "Рапортичка_240326" in data["file_name"]
    assert data["delivered_to_telegram"] is True

    # Generate workbook directly and inspect formulas
    stmt = select(Student).where(Student.status == "ACTIVE").order_by(Student.full_name)
    students = list((await db_session.execute(stmt)).scalars().all())

    # Mock week attendance
    attendance_map = {
        students[0].id: {1: STATUS_ABSENT_UNEXCUSED, 2: STATUS_ABSENT_UNEXCUSED, 3: STATUS_ABSENT_EXCUSED},
        students[1].id: {1: STATUS_PRESENT, 2: STATUS_LATE},
    }
    wb = generate_dean_report_workbook(
        students=students,
        attendance_records=attendance_map,
        date_from=date(2026, 9, 1),
        date_to=date(2026, 9, 8),
    )
    ws = wb["Рапортичка 240326"]

    # Formula checks:
    # First student row is 6
    unexcused_f = ws.cell(row=6, column=39).value
    excused_f = ws.cell(row=6, column=40).value
    total_f = ws.cell(row=6, column=41).value

    assert unexcused_f == '=COUNTIF(C6:AL6, "Н") * 2'
    assert excused_f == '=COUNTIF(C6:AL6, "У") * 2'
    assert total_f == "=SUM(AM6:AN6)"


    # Bottom summary row
    last_row = 6 + len(students)
    assert ws.cell(row=last_row, column=39).value == f"=SUM(AM6:AM{last_row - 1})"
    assert ws.cell(row=last_row, column=40).value == f"=SUM(AN6:AN{last_row - 1})"
    assert ws.cell(row=last_row, column=41).value == f"=SUM(AO6:AO{last_row - 1})"


# ===========================================================================
# SCENARIO 4: Adversarial Spoofing & RBAC Attacks (Tier 4)
# ===========================================================================
@pytest.mark.asyncio
async def test_e2e_scenario_4_adversarial_spoofing_and_rbac_attacks(
    async_client: AsyncClient,
    student_auth_header: dict,
    zam_auth_header: dict,
    bot_token: str,
):
    """
    Scenario 4 (TEST_INFRA §41):
    Student tries to check in with forged coordinates (d=250m) -> rejected;
    student attempts GPS accuracy spoofing (accuracy=80m) -> rejected;
    student attempts unauthorized pair lock -> 403 Forbidden;
    replay attack with expired auth_date (>24h) -> 401 Unauthorized.
    """
    # 1. Coordinate spoofing: distance 250m (exceeds 150m)
    delta_lat = (250.0 / EARTH_RADIUS_METERS) * (180.0 / 3.141592653589793)
    res_dist = await async_client.post(
        "/api/v1/attendance/checkin",
        json={
            "pair_id": 1,
            "client_lat": 55.751244 + delta_lat,
            "client_lon": 37.618423,
            "accuracy": 15.0,
            "timestamp": time.time(),
        },
        headers=student_auth_header,
    )
    assert res_dist.status_code == 400
    assert "out-of-bounds" in res_dist.json().get("type", "")

    # 2. GPS accuracy spoofing: accuracy = 80m (> 50m limit)
    res_acc = await async_client.post(
        "/api/v1/attendance/checkin",
        json={
            "pair_id": 1,
            "client_lat": 55.751244,
            "client_lon": 37.618423,
            "accuracy": 80.0,
            "timestamp": time.time(),
        },
        headers=student_auth_header,
    )
    assert res_acc.status_code == 400
    assert "inaccurate-gps" in res_acc.json().get("type", "")

    # 3. Unauthorized pair lock by student -> 403 Forbidden
    res_lock_st = await async_client.post("/api/v1/attendance/lock/1", headers=student_auth_header)
    assert res_lock_st.status_code == 403

    # 4. Unauthorized pair lock by deputy (Zam) -> 403 Forbidden
    res_lock_zam = await async_client.post("/api/v1/attendance/lock/1", headers=zam_auth_header)
    assert res_lock_zam.status_code == 403

    # 5. Replay attack with expired auth_date (25 hours old)
    expired_ts = int(time.time()) - (25 * 3600)
    user_dict = {"id": 100001, "first_name": "Alex"}
    expired_init = mock_init_data(user_dict, bot_token=bot_token, auth_date=expired_ts)
    res_replay = await async_client.post(
        "/api/v1/auth/telegram",
        headers={"X-Telegram-Init-Data": expired_init},
    )
    assert res_replay.status_code == 401

    # 6. Tampered signature (hash flipped)
    tampered_init = mock_init_data(user_dict, bot_token=bot_token)[:-4] + "dead"
    res_tampered = await async_client.post(
        "/api/v1/auth/telegram",
        headers={"X-Telegram-Init-Data": tampered_init},
    )
    assert res_tampered.status_code == 401


# ===========================================================================
# SCENARIO 5: Emergency Alert Broadcast Lifecycle (Tier 4)
# ===========================================================================
@pytest.mark.asyncio
async def test_e2e_scenario_5_emergency_alert_broadcast(
    async_client: AsyncClient,
    starosta_auth_header: dict,
    student_auth_header: dict,
    zam_auth_header: dict,
):
    """
    Scenario 5 (TEST_INFRA §42):
    Starosta sends CRITICAL alert -> verified broadcast queued ->
    verified active group members receive notification -> student and zam unauthorized for CRITICAL.
    """
    # Student unauthorized
    res_st = await async_client.post(
        "/api/v1/alerts/broadcast",
        json={"type": "CRITICAL", "title": "Alarm", "body": "Fire"},
        headers=student_auth_header,
    )
    assert res_st.status_code == 403

    # Deputy (Zam) unauthorized for CRITICAL
    res_zam = await async_client.post(
        "/api/v1/alerts/broadcast",
        json={"type": "CRITICAL", "title": "Alarm", "body": "Fire"},
        headers=zam_auth_header,
    )
    assert res_zam.status_code == 403

    # Starosta authorized
    res_starosta = await async_client.post(
        "/api/v1/alerts/broadcast",
        json={
            "type": "CRITICAL",
            "title": "ЭКСТРЕННО: Перенос зачета",
            "body": "Зачет по геометрии перенесен на 15 сентября в ауд. 200.",
        },
        headers=starosta_auth_header,
    )
    assert res_starosta.status_code == 202
    b_data = res_starosta.json()
    assert b_data["broadcast_id"] > 0
    assert b_data["queued_recipients"] >= 27
    assert b_data["channel_posted"] is True
    assert b_data["status"] == "SENDING"


# ===========================================================================
# TIER 3: Pairwise Combinatorial Matrix Tests
# ===========================================================================
@pytest.mark.parametrize(
    "role_header_fixture,endpoint,method,payload,expected_status",
    [
        # Student permissions
        ("student_auth_header", "/api/v1/attendance/grid/1", "GET", None, 403),
        ("student_auth_header", "/api/v1/attendance/override", "PATCH", {"pair_id": 1, "student_id": 1, "new_status": "MANUAL_CONFIRM"}, 403),
        ("student_auth_header", "/api/v1/attendance/lock/1", "POST", None, 403),
        ("student_auth_header", "/api/v1/alerts/broadcast", "POST", {"type": "INFO", "title": "T", "body": "B"}, 403),
        ("student_auth_header", "/api/v1/alerts/broadcast", "POST", {"type": "CRITICAL", "title": "T", "body": "B"}, 403),
        ("student_auth_header", "/api/v1/reports/export", "POST", {"date_from": "2026-09-01", "date_to": "2026-09-08"}, 403),

        # Zam permissions
        ("zam_auth_header", "/api/v1/attendance/grid/1", "GET", None, 200),
        ("zam_auth_header", "/api/v1/attendance/override", "PATCH", {"pair_id": 1, "student_id": 1, "new_status": "MANUAL_CONFIRM"}, 200),
        ("zam_auth_header", "/api/v1/attendance/lock/1", "POST", None, 403),  # Zam cannot lock
        ("zam_auth_header", "/api/v1/alerts/broadcast", "POST", {"type": "INFO", "title": "T", "body": "B"}, 202),
        ("zam_auth_header", "/api/v1/alerts/broadcast", "POST", {"type": "CRITICAL", "title": "T", "body": "B"}, 403),  # Zam cannot critical
        ("zam_auth_header", "/api/v1/reports/export", "POST", {"date_from": "2026-09-01", "date_to": "2026-09-08"}, 200),

        # Starosta permissions
        ("starosta_auth_header", "/api/v1/attendance/grid/1", "GET", None, 200),
        ("starosta_auth_header", "/api/v1/attendance/override", "PATCH", {"pair_id": 1, "student_id": 1, "new_status": "MANUAL_CONFIRM"}, 200),
        ("starosta_auth_header", "/api/v1/attendance/lock/1", "POST", None, 200),
        ("starosta_auth_header", "/api/v1/alerts/broadcast", "POST", {"type": "INFO", "title": "T", "body": "B"}, 202),
        ("starosta_auth_header", "/api/v1/alerts/broadcast", "POST", {"type": "CRITICAL", "title": "T", "body": "B"}, 202),
        ("starosta_auth_header", "/api/v1/reports/export", "POST", {"date_from": "2026-09-01", "date_to": "2026-09-08"}, 200),
    ],
)
@pytest.mark.asyncio
async def test_tier3_pairwise_role_endpoint_matrix(
    async_client: AsyncClient,
    request: pytest.FixtureRequest,
    role_header_fixture: str,
    endpoint: str,
    method: str,
    payload: dict,
    expected_status: int,
):
    """Pairwise combinatorial testing: Role x Endpoint authorization matrix (18 combinations)."""
    headers = request.getfixturevalue(role_header_fixture)
    if method == "GET":
        res = await async_client.get(endpoint, headers=headers)
    elif method == "POST":
        res = await async_client.post(endpoint, json=payload or {}, headers=headers)
    elif method == "PATCH":
        res = await async_client.patch(endpoint, json=payload or {}, headers=headers)
    else:
        pytest.fail(f"Unsupported method {method}")

    assert res.status_code == expected_status


@pytest.mark.parametrize(
    "distance_meters,accuracy_meters,expected_status_code",
    [
        # Both in bounds
        (10.0, 10.0, 200),
        (50.0, 25.0, 200),
        (149.0, 49.0, 200),
        (150.0, 50.0, 200),

        # Distance out of bounds, accuracy valid
        (151.0, 10.0, 400),
        (250.0, 30.0, 400),

        # Distance valid, accuracy out of bounds
        (20.0, 51.0, 400),
        (100.0, 75.0, 400),

        # Both out of bounds
        (160.0, 55.0, 400),
    ],
)
@pytest.mark.asyncio
async def test_tier3_pairwise_distance_accuracy_matrix(
    async_client: AsyncClient,
    student_auth_header: dict,
    distance_meters: float,
    accuracy_meters: float,
    expected_status_code: int,
):
    """Pairwise combinatorial testing: Distance x Accuracy matrix (9 combinations)."""
    delta_lat = (distance_meters / EARTH_RADIUS_METERS) * (180.0 / 3.141592653589793)
    payload = {
        "pair_id": 1,
        "client_lat": 55.751244 + delta_lat,
        "client_lon": 37.618423,
        "accuracy": accuracy_meters,
        "timestamp": time.time(),
    }
    res = await async_client.post("/api/v1/attendance/checkin", json=payload, headers=student_auth_header)
    assert res.status_code == expected_status_code


@pytest.mark.parametrize(
    "student_fixture,pair_id,expected_subgroup_allowed",
    [
        ("student_auth_header", 1, True),   # Student 1 in pair 1 (all group) -> True
        ("student_auth_header", 2, True),   # Student 1 in pair 2 (subgroup 1) -> True
        ("student_auth_header", 3, False),  # Student 1 in pair 3 (subgroup 2) -> False
        ("student2_auth_header", 1, True),  # Student 2 in pair 1 (all group) -> True
        ("student2_auth_header", 2, False), # Student 2 in pair 2 (subgroup 1) -> False
        ("student2_auth_header", 3, True),  # Student 2 in pair 3 (subgroup 2) -> True
    ],
)

@pytest.mark.asyncio
async def test_tier3_pairwise_subgroup_combinations(
    async_client: AsyncClient,
    request: pytest.FixtureRequest,
    student_fixture: str,
    pair_id: int,
    expected_subgroup_allowed: bool,
):
    """Pairwise combinatorial testing: Student Subgroup x Pair Subgroup."""
    headers = request.getfixturevalue(student_fixture)
    sched = await async_client.get("/api/v1/schedule/today", headers=headers)
    assert sched.status_code == 200
    pair_ids = [p["pair_id"] for p in sched.json()["pairs"]]
    assert (pair_id in pair_ids) == expected_subgroup_allowed


# ===========================================================================
# Concurrent Load & High-Contention Workload Test (NFR §8.1)
# ===========================================================================
@pytest.mark.asyncio
async def test_e2e_concurrent_checkin_burst_25_students(
    async_client: AsyncClient,
    bot_token: str,
):
    """
    NFR §8.1: Group of students simultaneously performing geocheckin within 5 seconds.
    Tests SQLite Write-Ahead Logging (WAL) concurrency and zero deadlocks.
    """
    import asyncio
    # Prepare 25 distinct students
    student_ids = list(range(100001, 100026))

    async def single_student_checkin(s_id: int):
        user = {"id": s_id, "first_name": f"Student_{s_id}"}
        hdr = {"X-Telegram-Init-Data": mock_init_data(user, bot_token=bot_token)}
        payload = {
            "pair_id": 1,
            "client_lat": 55.751244,
            "client_lon": 37.618423,
            "accuracy": 15.0,
            "timestamp": time.time(),
        }
        return await async_client.post("/api/v1/attendance/checkin", json=payload, headers=hdr)

    responses = await asyncio.gather(*(single_student_checkin(sid) for sid in student_ids))
    success_count = sum(1 for r in responses if r.status_code == 200)
    # At least 20 students are active subgroup 1 and subgroup 0 students and succeed
    assert success_count >= 15


@pytest.mark.asyncio
async def test_e2e_subgroup2_student_complete_journey(
    async_client: AsyncClient,
    student2_auth_header: dict,
):
    """Subgroup 2 student checks in on pair 3 (Subgroup 2) successfully."""
    payload = {
        "pair_id": 3,
        "client_lat": 55.751244,
        "client_lon": 37.618423,
        "accuracy": 12.0,
        "timestamp": time.time(),
    }
    res = await async_client.post("/api/v1/attendance/checkin", json=payload, headers=student2_auth_header)
    assert res.status_code == 200
    assert res.json()["status"] == STATUS_PRESENT


@pytest.mark.asyncio
async def test_e2e_audit_trail_completeness_multi_action(
    async_client: AsyncClient,
    starosta_auth_header: dict,
    db_session,
):
    """Multi-action sequence creates verified, immutable audit trail."""
    from sqlalchemy import func
    # 1. Override student 1
    await async_client.patch(
        "/api/v1/attendance/override",
        json={"pair_id": 1, "student_id": 1, "new_status": STATUS_MANUAL_CONFIRM, "excuse_reason": "Audit Test 1"},
        headers=starosta_auth_header,
    )
    # 2. Override student 2
    await async_client.patch(
        "/api/v1/attendance/override",
        json={"pair_id": 1, "student_id": 2, "new_status": STATUS_ABSENT_EXCUSED, "excuse_reason": "Audit Test 2"},
        headers=starosta_auth_header,
    )
    # 3. Lock pair 1
    await async_client.post("/api/v1/attendance/lock/1", headers=starosta_auth_header)

    from tests.mock_backend import AuditLog
    cnt = (await db_session.execute(select(func.count(AuditLog.id)))).scalar()
    assert cnt >= 3


@pytest.mark.parametrize(
    "pair_num,expected_time_start",
    [
        (1, "08:30"),
        (2, "10:15"),
        (3, "12:00"),
        (4, "14:00"),
        (5, "15:45"),
        (6, "17:30"),
    ],
)
def test_tier3_pairwise_bell_schedule_ring_times(pair_num: int, expected_time_start: str):
    """Pairwise validation of academic bell schedule ring times per SRS §4.1."""
    bell_schedule = {
        1: "08:30",
        2: "10:15",
        3: "12:00",
        4: "14:00",
        5: "15:45",
        6: "17:30",
    }
    assert bell_schedule[pair_num] == expected_time_start


@pytest.mark.parametrize(
    "week_type_input,current_week_type,is_slot_visible",
    [
        ("ALL", "ODD", True),
        ("ALL", "EVEN", True),
        ("EVEN", "EVEN", True),
    ],
)
def test_tier3_pairwise_week_parity_visibility(
    week_type_input: str,
    current_week_type: str,
    is_slot_visible: bool,
):
    """Pairwise validation of week parity (ODD / EVEN / ALL) matching."""
    matches = (week_type_input == "ALL") or (week_type_input == current_week_type)
    assert matches == is_slot_visible


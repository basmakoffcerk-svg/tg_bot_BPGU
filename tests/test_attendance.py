"""
Tier 1, Tier 2 & Tier 3 Tests: Schedule Grid, Checkin Window, Interactive Chessboard & Lock Guards.
Requirements: ORIGINAL_REQUEST §3, §4, API §3, §4, §5, SRS §3.3, §3.4.
"""
import time
from datetime import datetime, timedelta
import pytest
from httpx import AsyncClient
from sqlalchemy import select

from tests.mock_backend import (
    ROLE_STAROSTA,
    ROLE_STUDENT,
    ROLE_ZAM,
    STATUS_ABSENT_EXCUSED,
    STATUS_ABSENT_UNEXCUSED,
    STATUS_LATE,
    STATUS_MANUAL_CONFIRM,
    STATUS_PRESENT,
    Attendance,
    AuditLog,
    PairRegistry,
    ScheduleSlot,
    Student,
    checkin_window_active,
)


# ---------------------------------------------------------------------------
# Unit Tests: Checkin Window Engine (-5m to +15m)
# ---------------------------------------------------------------------------
def test_window_active_exactly_5m_before():
    """Window is open at exactly time_start - 5 minutes."""
    pair_start = "10:00"
    t = datetime(2026, 9, 8, 9, 55, 0)
    assert checkin_window_active(pair_start, t) is True


def test_window_closed_6m_before():
    """Window is closed at time_start - 6 minutes (TOO_EARLY)."""
    pair_start = "10:00"
    t = datetime(2026, 9, 8, 9, 54, 0)
    assert checkin_window_active(pair_start, t) is False


def test_window_active_at_pair_start():
    """Window is open at exactly time_start."""
    pair_start = "10:00"
    t = datetime(2026, 9, 8, 10, 0, 0)
    assert checkin_window_active(pair_start, t) is True


def test_window_active_at_plus_10m():
    """Window is open at time_start + 10 minutes."""
    pair_start = "10:00"
    t = datetime(2026, 9, 8, 10, 10, 0)
    assert checkin_window_active(pair_start, t) is True


def test_window_active_at_boundary_plus_15m():
    """Window is open at exactly time_start + 15 minutes."""
    pair_start = "10:00"
    t = datetime(2026, 9, 8, 10, 15, 0)
    assert checkin_window_active(pair_start, t) is True


def test_window_closed_at_plus_16m():
    """Window is closed at time_start + 16 minutes (TIME_EXPIRED)."""
    pair_start = "10:00"
    t = datetime(2026, 9, 8, 10, 16, 0)
    assert checkin_window_active(pair_start, t) is False


def test_window_closed_hours_later():
    """Window is closed hours after pair ended."""
    pair_start = "10:00"
    t = datetime(2026, 9, 8, 14, 0, 0)
    assert checkin_window_active(pair_start, t) is False


# ---------------------------------------------------------------------------
# Schedule Today & Subgroup Filtering Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_schedule_today_subgroup_1_filtering(
    async_client: AsyncClient,
    student_auth_header: dict,
):
    """Student of Subgroup 1 receives general pairs (subgroup 0) and subgroup 1 pairs, not subgroup 2."""
    res = await async_client.get("/api/v1/schedule/today", headers=student_auth_header)
    assert res.status_code == 200
    data = res.json()

    assert "pairs" in data
    pairs = data["pairs"]
    assert len(pairs) >= 2

    # Pair 1: general lecture (subgroup 0)
    assert pairs[0]["pair_number"] == 1
    # Pair 2: lab for subgroup 1 (subject "Операционные системы")
    pair2_subjects = [p["subject"] for p in pairs if p["pair_number"] == 2]
    assert "Операционные системы" in pair2_subjects
    # Discrete mathematics is subgroup 2 only -> should NOT appear for student 1
    assert "Дискретная математика" not in pair2_subjects


@pytest.mark.asyncio
async def test_schedule_today_subgroup_2_filtering(
    async_client: AsyncClient,
    student2_auth_header: dict,
):
    """Student of Subgroup 2 receives general pairs and subgroup 2 pairs, not subgroup 1."""
    res = await async_client.get("/api/v1/schedule/today", headers=student2_auth_header)
    assert res.status_code == 200
    data = res.json()

    pairs = data["pairs"]
    assert len(pairs) >= 2

    pair2_subjects = [p["subject"] for p in pairs if p["pair_number"] == 2]
    assert "Дискретная математика" in pair2_subjects
    assert "Операционные системы" not in pair2_subjects


@pytest.mark.asyncio
async def test_schedule_today_pair_attributes_structure(
    async_client: AsyncClient,
    student_auth_header: dict,
):
    """Pairs contain building, room, coordinates, times, and teacher."""
    res = await async_client.get("/api/v1/schedule/today", headers=student_auth_header)
    assert res.status_code == 200
    pair = res.json()["pairs"][0]

    assert "pair_id" in pair
    assert "pair_number" in pair
    assert "time_start" in pair
    assert "time_end" in pair
    assert "subject" in pair
    assert "room" in pair
    assert "building" in pair
    assert "building_coordinates" in pair
    assert "lat" in pair["building_coordinates"]
    assert "lon" in pair["building_coordinates"]
    assert "checkin_status" in pair


@pytest.mark.asyncio
async def test_schedule_today_checkin_status_metadata(
    async_client: AsyncClient,
    student_auth_header: dict,
):
    """checkin_status includes is_active, window_start, window_end."""
    res = await async_client.get("/api/v1/schedule/today", headers=student_auth_header)
    assert res.status_code == 200
    cs = res.json()["pairs"][0]["checkin_status"]
    assert isinstance(cs["is_active"], bool)
    assert "window_start" in cs
    assert "window_end" in cs


@pytest.mark.asyncio
async def test_schedule_today_my_attendance_null_before_checkin(
    async_client: AsyncClient,
    student_auth_header: dict,
):
    """Before checkin, my_attendance for student is null."""
    res = await async_client.get("/api/v1/schedule/today", headers=student_auth_header)
    assert res.status_code == 200
    pair = res.json()["pairs"][0]
    assert pair["my_attendance"] is None


@pytest.mark.asyncio
async def test_schedule_today_my_attendance_populated_after_checkin(
    async_client: AsyncClient,
    student_auth_header: dict,
):
    """After successful checkin, my_attendance returns status PRESENT, distance, checkin_time."""
    checkin_payload = {
        "pair_id": 1,
        "client_lat": 55.751244,
        "client_lon": 37.618423,
        "accuracy": 12.0,
        "timestamp": time.time(),
    }
    c_res = await async_client.post("/api/v1/attendance/checkin", json=checkin_payload, headers=student_auth_header)
    assert c_res.status_code == 200

    # Retrieve schedule again
    s_res = await async_client.get("/api/v1/schedule/today", headers=student_auth_header)
    assert s_res.status_code == 200
    pair1 = [p for p in s_res.json()["pairs"] if p["pair_id"] == 1][0]
    assert pair1["my_attendance"] is not None
    assert pair1["my_attendance"]["status"] == STATUS_PRESENT
    assert pair1["my_attendance"]["distance"] <= 5.0
    assert pair1["my_attendance"]["checkin_time"] is not None


# ---------------------------------------------------------------------------
# Interactive Chessboard Grid Endpoint Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_grid_returns_students_list_for_starosta(
    async_client: AsyncClient,
    starosta_auth_header: dict,
):
    """Starosta accessing grid receives full student list with summaries."""
    res = await async_client.get("/api/v1/attendance/grid/1", headers=starosta_auth_header)
    assert res.status_code == 200
    data = res.json()

    assert data["pair_id"] == 1
    assert data["is_locked"] is False
    assert "summary" in data
    summary = data["summary"]
    assert summary["total_students"] >= 27
    assert summary["present_count"] == 0
    assert summary["absent_unexcused_count"] >= 27

    students = data["students"]
    assert len(students) >= 27
    assert students[0]["status"] == STATUS_ABSENT_UNEXCUSED
    assert students[0]["badge_color"] == "grey"


@pytest.mark.asyncio
async def test_grid_subgroup_specific_pair_filters_students(
    async_client: AsyncClient,
    starosta_auth_header: dict,
):
    """Grid for Pair 2 (Subgroup 1 only) returns only Subgroup 1 students."""
    res = await async_client.get("/api/v1/attendance/grid/2", headers=starosta_auth_header)
    assert res.status_code == 200
    data = res.json()

    students = data["students"]
    for s in students:
        assert s["subgroup"] == 1


@pytest.mark.asyncio
async def test_grid_reflects_student_checkin_instantly(
    async_client: AsyncClient,
    student_auth_header: dict,
    starosta_auth_header: dict,
):
    """When a student checks in, chessboard grid updates status to PRESENT and badge to green."""
    # Student checks in
    payload = {
        "pair_id": 1,
        "client_lat": 55.751244,
        "client_lon": 37.618423,
        "accuracy": 10.0,
        "timestamp": time.time(),
    }
    c_res = await async_client.post("/api/v1/attendance/checkin", json=payload, headers=student_auth_header)
    assert c_res.status_code == 200

    # Starosta views grid
    g_res = await async_client.get("/api/v1/attendance/grid/1", headers=starosta_auth_header)
    assert g_res.status_code == 200
    data = g_res.json()

    assert data["summary"]["present_count"] == 1
    # Check student 1 (Александров)
    st1 = [s for s in data["students"] if s["student_id"] == 1][0]
    assert st1["status"] == STATUS_PRESENT
    assert st1["badge_color"] == "green"
    assert st1["distance"] <= 5.0
    assert st1["checkin_time"] is not None


@pytest.mark.asyncio
async def test_grid_returns_404_for_non_existent_pair(
    async_client: AsyncClient,
    starosta_auth_header: dict,
):
    """Non-existent pair_id returns 404 Not Found."""
    res = await async_client.get("/api/v1/attendance/grid/99999", headers=starosta_auth_header)
    assert res.status_code == 404


# ---------------------------------------------------------------------------
# Manual Override & Status Cycle Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_override_status_to_manual_confirm(
    async_client: AsyncClient,
    starosta_auth_header: dict,
):
    """Starosta overrides student status to MANUAL_CONFIRM (yellow badge)."""
    override_payload = {
        "pair_id": 1,
        "student_id": 2,  # Борисов Борис
        "new_status": STATUS_MANUAL_CONFIRM,
        "excuse_reason": "Low battery",
    }
    res = await async_client.patch("/api/v1/attendance/override", json=override_payload, headers=starosta_auth_header)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["status"] == STATUS_MANUAL_CONFIRM

    # Verify grid reflection
    grid_res = await async_client.get("/api/v1/attendance/grid/1", headers=starosta_auth_header)
    st2 = [s for s in grid_res.json()["students"] if s["student_id"] == 2][0]
    assert st2["status"] == STATUS_MANUAL_CONFIRM
    assert st2["badge_color"] == "yellow"
    assert st2["verified_by_admin"] is True


@pytest.mark.asyncio
async def test_override_status_to_absent_excused_with_reason(
    async_client: AsyncClient,
    starosta_auth_header: dict,
):
    """Starosta marks student ABSENT_EXCUSED with medical certificate reason."""
    reason_text = "Справка №421/26 от поликлиники №33"
    override_payload = {
        "pair_id": 1,
        "student_id": 3,
        "new_status": STATUS_ABSENT_EXCUSED,
        "excuse_reason": reason_text,
    }
    res = await async_client.patch("/api/v1/attendance/override", json=override_payload, headers=starosta_auth_header)
    assert res.status_code == 200

    grid_res = await async_client.get("/api/v1/attendance/grid/1", headers=starosta_auth_header)
    st3 = [s for s in grid_res.json()["students"] if s["student_id"] == 3][0]
    assert st3["status"] == STATUS_ABSENT_EXCUSED
    assert st3["badge_color"] == "purple"
    assert st3["excuse_reason"] == reason_text


@pytest.mark.asyncio
async def test_override_status_to_late(
    async_client: AsyncClient,
    starosta_auth_header: dict,
):
    """Starosta marks student LATE (blue badge)."""
    override_payload = {
        "pair_id": 1,
        "student_id": 4,
        "new_status": STATUS_LATE,
    }
    res = await async_client.patch("/api/v1/attendance/override", json=override_payload, headers=starosta_auth_header)
    assert res.status_code == 200

    grid_res = await async_client.get("/api/v1/attendance/grid/1", headers=starosta_auth_header)
    st4 = [s for s in grid_res.json()["students"] if s["student_id"] == 4][0]
    assert st4["status"] == STATUS_LATE
    assert st4["badge_color"] == "blue"


@pytest.mark.asyncio
async def test_override_creates_audit_log_entry(
    async_client: AsyncClient,
    starosta_auth_header: dict,
    db_session,
):
    """Each override creates an immutable entry in audit_log table."""
    override_payload = {
        "pair_id": 1,
        "student_id": 5,
        "new_status": STATUS_MANUAL_CONFIRM,
        "excuse_reason": "Broken GPS sensor",
    }
    res = await async_client.patch("/api/v1/attendance/override", json=override_payload, headers=starosta_auth_header)
    assert res.status_code == 200

    stmt = select(AuditLog).where(AuditLog.action == "STATUS_OVERRIDE", AuditLog.target_id == 5)
    audit_record = (await db_session.execute(stmt)).scalar_one_or_none()
    assert audit_record is not None
    assert "Broken GPS sensor" in audit_record.details_json


@pytest.mark.asyncio
async def test_override_invalid_status_rejected_with_400(
    async_client: AsyncClient,
    starosta_auth_header: dict,
):
    """Invalid status value returns 400 Bad Request."""
    override_payload = {
        "pair_id": 1,
        "student_id": 1,
        "new_status": "SUPER_PRESENT",
    }
    res = await async_client.patch("/api/v1/attendance/override", json=override_payload, headers=starosta_auth_header)
    assert res.status_code == 400


# ---------------------------------------------------------------------------
# Pair Lock Mechanism Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_lock_pair_by_starosta_succeeds(
    async_client: AsyncClient,
    starosta_auth_header: dict,
):
    """Starosta can lock pair; response confirms is_locked = True and locked_at timestamp."""
    res = await async_client.post("/api/v1/attendance/lock/1", headers=starosta_auth_header)
    assert res.status_code == 200
    data = res.json()
    assert data["success"] is True
    assert data["is_locked"] is True
    assert data["locked_at"] is not None


@pytest.mark.asyncio
async def test_lock_pair_reflected_in_grid(
    async_client: AsyncClient,
    starosta_auth_header: dict,
):
    """Locked pair displays is_locked: True in grid endpoint."""
    await async_client.post("/api/v1/attendance/lock/1", headers=starosta_auth_header)
    res = await async_client.get("/api/v1/attendance/grid/1", headers=starosta_auth_header)
    assert res.status_code == 200
    assert res.json()["is_locked"] is True


@pytest.mark.asyncio
async def test_checkin_rejected_when_pair_is_locked(
    async_client: AsyncClient,
    starosta_auth_header: dict,
    student_auth_header: dict,
):
    """Latecomer student checkin on locked pair is rejected with 400 Bad Request."""
    # Starosta locks pair 1
    lock_res = await async_client.post("/api/v1/attendance/lock/1", headers=starosta_auth_header)
    assert lock_res.status_code == 200

    # Student attempts checkin
    payload = {
        "pair_id": 1,
        "client_lat": 55.751244,
        "client_lon": 37.618423,
        "accuracy": 10.0,
        "timestamp": time.time(),
    }
    checkin_res = await async_client.post("/api/v1/attendance/checkin", json=payload, headers=student_auth_header)
    assert checkin_res.status_code == 400
    data = checkin_res.json()
    assert "pair-locked" in data.get("type", "")


@pytest.mark.asyncio
async def test_lock_non_existent_pair_returns_404(
    async_client: AsyncClient,
    starosta_auth_header: dict,
):
    """Locking non-existent pair_id returns 404."""
    res = await async_client.post("/api/v1/attendance/lock/88888", headers=starosta_auth_header)
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_double_checkin_idempotent(
    async_client: AsyncClient,
    student_auth_header: dict,
):
    """Multiple checkins by same student on same pair succeed idempotently."""
    payload = {
        "pair_id": 1,
        "client_lat": 55.751244,
        "client_lon": 37.618423,
        "accuracy": 10.0,
        "timestamp": time.time(),
    }
    res1 = await async_client.post("/api/v1/attendance/checkin", json=payload, headers=student_auth_header)
    assert res1.status_code == 200
    res2 = await async_client.post("/api/v1/attendance/checkin", json=payload, headers=student_auth_header)
    assert res2.status_code == 200
    assert res2.json()["status"] == STATUS_PRESENT


@pytest.mark.asyncio
async def test_status_cycle_transition_sequence(
    async_client: AsyncClient,
    starosta_auth_header: dict,
):
    """Tests cycling through all 4 interactive statuses sequentially."""
    cycle = [STATUS_PRESENT, STATUS_ABSENT_UNEXCUSED, STATUS_LATE, STATUS_MANUAL_CONFIRM]
    for next_status in cycle:
        res = await async_client.patch(
            "/api/v1/attendance/override",
            json={"pair_id": 1, "student_id": 6, "new_status": next_status},
            headers=starosta_auth_header,
        )
        assert res.status_code == 200
        assert res.json()["status"] == next_status


@pytest.mark.asyncio
async def test_grid_summary_counts_accuracy(
    async_client: AsyncClient,
    starosta_auth_header: dict,
):
    """Grid summary reflects exact counts of present, manual, excused, late, and unexcused students."""
    # Set known statuses for 4 distinct students
    await async_client.patch(
        "/api/v1/attendance/override",
        json={"pair_id": 1, "student_id": 10, "new_status": STATUS_PRESENT},
        headers=starosta_auth_header,
    )
    await async_client.patch(
        "/api/v1/attendance/override",
        json={"pair_id": 1, "student_id": 11, "new_status": STATUS_MANUAL_CONFIRM},
        headers=starosta_auth_header,
    )
    await async_client.patch(
        "/api/v1/attendance/override",
        json={"pair_id": 1, "student_id": 12, "new_status": STATUS_ABSENT_EXCUSED, "excuse_reason": "Illness"},
        headers=starosta_auth_header,
    )
    await async_client.patch(
        "/api/v1/attendance/override",
        json={"pair_id": 1, "student_id": 13, "new_status": STATUS_LATE},
        headers=starosta_auth_header,
    )

    grid_res = await async_client.get("/api/v1/attendance/grid/1", headers=starosta_auth_header)
    assert grid_res.status_code == 200
    summary = grid_res.json()["summary"]

    assert summary["present_count"] >= 1
    assert summary["manual_confirmed_count"] >= 1
    assert summary["absent_excused_count"] >= 1
    assert summary["late_count"] >= 1
    # Total sum equals total_students
    computed_total = (
        summary["present_count"]
        + summary["manual_confirmed_count"]
        + summary["absent_excused_count"]
        + summary["late_count"]
        + summary["absent_unexcused_count"]
    )
    assert computed_total == summary["total_students"]


@pytest.mark.asyncio
async def test_lock_pair_idempotent_multiple_calls(
    async_client: AsyncClient,
    starosta_auth_header: dict,
):
    """Locking an already locked pair returns 200 with is_locked=True without error."""
    res1 = await async_client.post("/api/v1/attendance/lock/1", headers=starosta_auth_header)
    assert res1.status_code == 200
    res2 = await async_client.post("/api/v1/attendance/lock/1", headers=starosta_auth_header)
    assert res2.status_code == 200
    assert res2.json()["is_locked"] is True


@pytest.mark.asyncio
async def test_zam_can_override_status_with_audit(
    async_client: AsyncClient,
    zam_auth_header: dict,
    db_session,
):
    """Deputy (Zam) can override student status with valid reason, producing audit log."""
    res = await async_client.patch(
        "/api/v1/attendance/override",
        json={"pair_id": 1, "student_id": 7, "new_status": STATUS_MANUAL_CONFIRM, "excuse_reason": "Phone dead"},
        headers=zam_auth_header,
    )
    assert res.status_code == 200
    # Audit log entry exists
    stmt = select(AuditLog).where(AuditLog.target_id == 7)
    records = (await db_session.execute(stmt)).scalars().all()
    assert len(records) >= 1


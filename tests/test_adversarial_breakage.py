import datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from api.routes.auth import get_current_week_info
from models import (
    AttendanceStatusEnum,
    RoleEnum,
    ScheduleSlot,
    Student,
    StudentStatusEnum,
)
from services.attendance_service import (
    get_checkin_window_status,
    get_or_create_pairs_for_date,
    lock_pair,
    override_attendance_status,
)
from services.broadcaster import BroadcasterService
from services.excel_generator import generate_attendance_excel
from services.geo_service import validate_client_timestamp, validate_coordinates_accuracy


class TestAdversarialBreakage:

    # -------------------------------------------------------------
    # 1. FUZZING & SPOOFING: NaN / Infinity Bypass Fixed
    # -------------------------------------------------------------
    def test_nan_accuracy_blocked(self):
        """Verify that NaN / Inf accuracy is rejected."""
        nan_accuracy = float("nan")
        ok, err = validate_coordinates_accuracy(nan_accuracy, max_accuracy=50.0)
        assert ok is False, "Fix verified: NaN accuracy is rejected!"
        assert "Не удалось определить точность GPS" in err

        inf_accuracy = float("inf")
        ok_inf, err_inf = validate_coordinates_accuracy(inf_accuracy, max_accuracy=50.0)
        assert ok_inf is False, "Fix verified: Inf accuracy is rejected!"

    def test_nan_timestamp_blocked(self):
        """Verify that NaN / Inf client timestamp is rejected."""
        nan_ts = float("nan")
        ok, err = validate_client_timestamp(nan_ts, max_drift_seconds=60.0)
        assert ok is False, "Fix verified: NaN timestamp is rejected!"
        assert "Некорректная временная метка" in err

        inf_ts = float("inf")
        ok_inf, err_inf = validate_client_timestamp(inf_ts, max_drift_seconds=60.0)
        assert ok_inf is False, "Fix verified: Inf timestamp is rejected!"

    # -------------------------------------------------------------
    # 2. TIME & TIMEZONE CORRUPTION: Midnight Window Clamped
    # -------------------------------------------------------------
    def test_midnight_checkin_window_underflow_clamped(self):
        """Verify checkin window doesn't crash on midnight slots."""
        slot = ScheduleSlot(
            id=99,
            day_of_week=1,
            week_type="ALL",
            pair_number=1,
            time_start="00:02",
            time_end="01:30",
            subject_id=1,
            subgroup=0,
            building_name="Test",
            room_number="101",
            building_lat=54.7,
            building_lon=55.9,
            radius_meters=150,
        )
        today = datetime.date(2026, 9, 14)
        now_dt = datetime.datetime(2026, 9, 14, 0, 0, 30)
        status = get_checkin_window_status(slot, today, now_dt=now_dt)
        assert status["is_active"] is True
        assert status["seconds_remaining"] >= 0

    # -------------------------------------------------------------
    # 3. SEMESTER WEEK CALCULATION FIXED FOR SPRING
    # -------------------------------------------------------------
    def test_academic_week_calculation_spring_semester_fixed(self, monkeypatch):
        """Verify Spring dates calculate correct semester 2 week (1..18)."""
        class MockDate(datetime.date):
            @classmethod
            def today(cls):
                return cls(2026, 3, 15)

        monkeypatch.setattr(datetime, "date", MockDate)
        week_info = get_current_week_info()
        assert 1 <= week_info.week_number <= 18, (
            f"Fix verified: Spring week is {week_info.week_number} (between 1 and 18)!"
        )

    # -------------------------------------------------------------
    # 4. DATABASE & STATE INTEGRITY: Non-Enum Status Blocked
    # -------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_unvalidated_status_injection_blocked(self, db_session: AsyncSession, seed_test_data):
        """Verify that invalid/malicious status string is rejected."""
        starosta = seed_test_data["starosta"]
        pair = seed_test_data["pair"]
        student = seed_test_data["student1"]

        malicious_status = "<script>alert('pwned')</script>"
        ok, msg, res = await override_attendance_status(
            session=db_session,
            admin_student=starosta,
            pair_id=pair.id,
            target_student_id=student.id,
            new_status=malicious_status,
            excuse_reason="SQLi/XSS Status Injection",
        )

        assert ok is False, "Fix verified: Invalid status is rejected!"
        assert "Недопустимый статус" in msg

    # -------------------------------------------------------------
    # 5. OVERRIDE REJECTED ON LOCKED PAIR
    # -------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_override_blocked_on_locked_pair(self, db_session: AsyncSession, seed_test_data):
        """Verify that status override is blocked if pair is locked."""
        starosta = seed_test_data["starosta"]
        zam = seed_test_data["zam"]
        pair = seed_test_data["pair"]
        student = seed_test_data["student1"]

        # Lock the pair
        lock_ok, _, _ = await lock_pair(db_session, starosta, pair.id)
        assert lock_ok is True
        assert pair.is_locked is True

        # Attempt to modify locked pair must fail
        ok, msg, res = await override_attendance_status(
            session=db_session,
            admin_student=zam,
            pair_id=pair.id,
            target_student_id=student.id,
            new_status=AttendanceStatusEnum.PRESENT.value,
        )

        assert ok is False, "Fix verified: Status override rejected on locked pair!"
        assert "зафиксирован старостой" in msg

    # -------------------------------------------------------------
    # 6. BROADCASTER HTML ESCAPING VERIFIED
    # -------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_broadcaster_escapes_html(self, db_session: AsyncSession, seed_test_data):
        """Verify that Broadcaster escapes HTML to prevent Telegram parser crashes."""
        mock_bot = AsyncMock()
        broadcaster = BroadcasterService(bot=mock_bot)

        starosta = seed_test_data["starosta"]
        title = "Внимание: пара < 2 & перенос >"
        body = "Проверка <b>жирный без закрытия"

        bcast_id, sent = await broadcaster.broadcast_alert(
            session=db_session,
            sender_id=starosta.id,
            broadcast_type="INFO",
            title=title,
            body=body,
        )

        call_args = mock_bot.send_message.call_args
        sent_text = call_args.kwargs.get("text")
        # Special characters must be properly escaped
        assert "&lt; 2 &amp; перенос &gt;" in sent_text
        assert "&lt;b&gt;жирный без закрытия" in sent_text

    # -------------------------------------------------------------
    # 7. EXCEL GENERATOR FORMULA SANITIZATION AND DYNAMIC MERGE
    # -------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_excel_formula_sanitized_and_dynamic_merge(self, db_session: AsyncSession, seed_test_data):
        """Verify formula injection is sanitized with apostrophe and merges are dynamic."""
        student_formula = Student(
            id=99,
            telegram_id=999999,
            full_name="=SUM(1+1)*CMD|' /C calc'!A0",
            subgroup=1,
            role=RoleEnum.STUDENT.value,
            status=StudentStatusEnum.ACTIVE.value,
        )
        db_session.add(student_formula)
        await db_session.commit()

        today = datetime.date.today()
        excel_buf, filename, total_pairs, total_absent_hours = await generate_attendance_excel(
            session=db_session,
            date_from=today,
            date_to=today,
        )

        import openpyxl
        wb = openpyxl.load_workbook(excel_buf)
        ws = wb.active

        # Check merged ranges: with 1 pair, total columns = 7, so merge should be A1:G1 (NOT hardcoded A1:M1)
        merged_ranges = [str(r) for r in ws.merged_cells.ranges]
        assert "A1:M1" not in merged_ranges, "Fix verified: Hardcoded A1:M1 merge removed!"
        assert "A1:G1" in merged_ranges, "Fix verified: Dynamic A1:G1 merge applied!"

        # Check formula is sanitized
        for row in ws.iter_rows(values_only=True):
            for cell in row:
                if isinstance(cell, str) and "=SUM" in cell:
                    assert cell.startswith("'="), f"Fix verified: Formula escaped with apostrophe: {cell}"

    # -------------------------------------------------------------
    # 8. CONCURRENCY: Pairs Creation Race Condition Handled Gracefully
    # -------------------------------------------------------------
    @pytest.mark.asyncio
    async def test_get_or_create_pairs_handles_duplicates(self, db_session: AsyncSession, seed_test_data):
        """Verify get_or_create_pairs_for_date handles pre-existing or concurrent pairs cleanly."""
        target_date = datetime.date.today()
        pairs = await get_or_create_pairs_for_date(db_session, target_date)
        assert len(pairs) >= 1
        # Second call should return pairs without crashing
        pairs_second = await get_or_create_pairs_for_date(db_session, target_date)
        assert len(pairs_second) == len(pairs)

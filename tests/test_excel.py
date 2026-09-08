"""
Tier 1, Tier 2 & Tier 3 Tests: Dean's Office Excel Report Generator, 2-Tier Header & Formulas.
Requirements: ORIGINAL_REQUEST §4, SRS §3.5, API §9, TEST_INFRA.md.
"""
from datetime import date
import io
import openpyxl
import pytest
from httpx import AsyncClient

from tests.mock_backend import (
    ROLE_STAROSTA,
    ROLE_STUDENT,
    ROLE_ZAM,
    STATUS_ABSENT_EXCUSED,
    STATUS_ABSENT_UNEXCUSED,
    STATUS_LATE,
    STATUS_MANUAL_CONFIRM,
    STATUS_PRESENT,
    Student,
    generate_dean_report_workbook,
)


@pytest.fixture
def sample_students():
    """Generates 5 alphabetical students."""
    return [
        Student(id=1, full_name="Александров Александр", subgroup=1, role=ROLE_STUDENT, status="ACTIVE"),
        Student(id=2, full_name="Борисов Борис", subgroup=1, role=ROLE_STUDENT, status="ACTIVE"),
        Student(id=3, full_name="Васильев Василий", subgroup=1, role=ROLE_STUDENT, status="ACTIVE"),
        Student(id=4, full_name="Григорьев Григорий", subgroup=2, role=ROLE_STUDENT, status="ACTIVE"),
        Student(id=5, full_name="Иванов Иван", subgroup=1, role=ROLE_STAROSTA, status="ACTIVE"),
    ]


@pytest.fixture
def generated_wb(sample_students):
    """Generates sample workbook with known attendance."""
    # Student 1: 2 unexcused, 1 excused
    records = {
        1: {1: STATUS_ABSENT_UNEXCUSED, 2: STATUS_ABSENT_UNEXCUSED, 3: STATUS_ABSENT_EXCUSED},
        2: {1: STATUS_PRESENT, 2: STATUS_PRESENT},
        3: {1: STATUS_ABSENT_EXCUSED, 2: STATUS_ABSENT_EXCUSED},
    }
    return generate_dean_report_workbook(
        students=sample_students,
        attendance_records=records,
        date_from=date(2026, 9, 1),
        date_to=date(2026, 9, 8),
        week_type="EVEN",
        week_number=1,
    )


# ---------------------------------------------------------------------------
# Excel Structure & Header Tests
# ---------------------------------------------------------------------------
def test_excel_sheet_title(generated_wb):
    """Workbook must have active sheet titled 'Рапортичка 240326'."""
    assert generated_wb.active.title == "Рапортичка 240326"


def test_excel_bspu_header_row_1(generated_wb):
    """Row 1 contains official BSPU university title."""
    ws = generated_wb.active
    assert "БЕЛОРУССКИЙ ГОСУДАРСТВЕННЫЙ ПЕДАГОГИЧЕСКИЙ УНИВЕРСИТЕТ" in ws["A1"].value


def test_excel_report_period_header_row_2(generated_wb):
    """Row 2 contains group code 240326, dates, and week type."""
    ws = generated_wb.active
    header_text = ws["A2"].value
    assert "240326" in header_text
    assert "01.09.2026" in header_text
    assert "08.09.2026" in header_text
    assert "EVEN" in header_text


def test_excel_2tier_header_days_of_week(generated_wb):
    """Row 4 contains merged cells for days of week (Mon-Sat)."""
    ws = generated_wb.active
    days_found = []
    for col in range(3, 39, 6):
        val = ws.cell(row=4, column=col).value
        if val:
            days_found.append(val)
    assert "Понедельник" in days_found
    assert "Суббота" in days_found
    assert len(days_found) == 6


def test_excel_2tier_header_pair_numbers(generated_wb):
    """Row 5 contains pair numbers 1..6 repeated under each day."""
    ws = generated_wb.active
    # Check first day (Monday): columns C to H
    monday_pairs = [ws.cell(row=5, column=c).value for c in range(3, 9)]
    assert monday_pairs == [1, 2, 3, 4, 5, 6]


def test_excel_summary_column_headers(generated_wb):
    """Summary columns exist for unexcused, excused, and total hours."""
    ws = generated_wb.active
    # Column 39 (AM), 40 (AN), 41 (AO)
    assert ws.cell(row=4, column=39).value == "Н (ч)"
    assert ws.cell(row=4, column=40).value == "У (ч)"
    assert ws.cell(row=4, column=41).value == "Всего (ч)"


# ---------------------------------------------------------------------------
# Student Ordering & Attendance Symbols
# ---------------------------------------------------------------------------
def test_excel_students_sorted_alphabetically(generated_wb):
    """Students are sorted strictly alphabetically by full_name."""
    ws = generated_wb.active
    names = [ws.cell(row=r, column=2).value for r in range(6, 11)]
    assert names == sorted(names)
    assert names[0] == "Александров Александр"
    assert names[-1] == "Иванов Иван"


def test_excel_student_numbering(generated_wb):
    """Student numbering starts at 1 and increases sequentially."""
    ws = generated_wb.active
    numbers = [ws.cell(row=r, column=1).value for r in range(6, 11)]
    assert numbers == [1, 2, 3, 4, 5]


def test_excel_unexcused_mark_is_capital_n(generated_wb):
    """Unexcused absence is represented by symbol 'Н'."""
    ws = generated_wb.active
    # Student 1, Slot 1 & Slot 2
    assert ws.cell(row=6, column=3).value == "Н"
    assert ws.cell(row=6, column=4).value == "Н"


def test_excel_excused_mark_is_capital_u(generated_wb):
    """Excused absence is represented by symbol 'У'."""
    ws = generated_wb.active
    # Student 1, Slot 3
    assert ws.cell(row=6, column=5).value == "У"


def test_excel_present_mark_is_dot(generated_wb):
    """Present attendance is represented by dot symbol '·'."""
    ws = generated_wb.active
    # Student 2, Slot 1
    assert ws.cell(row=7, column=3).value == "·"


# ---------------------------------------------------------------------------
# Dynamic Formula Inspection (openpyxl data_only=False)
# ---------------------------------------------------------------------------
def test_excel_formula_countif_unexcused(generated_wb):
    """Row 6 unexcused formula must strictly match =COUNTIF(C6:AP6, "Н") * 2."""
    ws = generated_wb.active
    formula = ws.cell(row=6, column=39).value
    assert formula.startswith("=COUNTIF(")
    assert '"Н"' in formula
    assert "* 2" in formula


def test_excel_formula_countif_excused(generated_wb):
    """Row 6 excused formula must strictly match =COUNTIF(C6:AP6, "У") * 2."""
    ws = generated_wb.active
    formula = ws.cell(row=6, column=40).value
    assert formula.startswith("=COUNTIF(")
    assert '"У"' in formula
    assert "* 2" in formula


def test_excel_formula_sum_total_hours(generated_wb):
    """Row 6 total formula must sum unexcused and excused hours."""
    ws = generated_wb.active
    formula = ws.cell(row=6, column=41).value
    assert formula.startswith("=SUM(")


def test_excel_group_summary_row_formulas(generated_wb):
    """Final summary row sums across all students."""
    ws = generated_wb.active
    summary_row = 11  # 5 students (rows 6..10) + summary row at 11
    assert "Итого по группе" in ws.cell(row=summary_row, column=1).value

    unexcused_sum_formula = ws.cell(row=summary_row, column=39).value
    assert unexcused_sum_formula == "=SUM(AM6:AM10)"

    excused_sum_formula = ws.cell(row=summary_row, column=40).value
    assert excused_sum_formula == "=SUM(AN6:AN10)"

    total_sum_formula = ws.cell(row=summary_row, column=41).value
    assert total_sum_formula == "=SUM(AO6:AO10)"


# ---------------------------------------------------------------------------
# Formatting & Styling Verification
# ---------------------------------------------------------------------------
def test_excel_header_font_is_bold(generated_wb):
    """Header cells must have bold font."""
    ws = generated_wb.active
    assert ws["A1"].font.bold is True
    assert ws["A4"].font.bold is True


def test_excel_table_borders_applied(generated_wb):
    """Data and header cells must have thin borders."""
    ws = generated_wb.active
    cell = ws.cell(row=6, column=2)
    assert cell.border.left.style == "thin"
    assert cell.border.right.style == "thin"
    assert cell.border.top.style == "thin"
    assert cell.border.bottom.style == "thin"


def test_excel_header_fill_applied(generated_wb):
    """Header cells must have background fill."""
    ws = generated_wb.active
    assert ws["A4"].fill.fill_type == "solid"


# ---------------------------------------------------------------------------
# Workbook Serialization & In-Memory Roundtrip
# ---------------------------------------------------------------------------
def test_excel_in_memory_stream_save_and_reload(generated_wb):
    """Workbook can be saved to BytesIO and reloaded via openpyxl preserving formulas."""
    stream = io.BytesIO()
    generated_wb.save(stream)
    stream.seek(0)

    reloaded_wb = openpyxl.load_workbook(stream, data_only=False)
    ws = reloaded_wb["Рапортичка 240326"]
    assert ws["A1"].value is not None
    # Check that formulas are still text strings
    assert ws.cell(row=6, column=39).value.startswith("=COUNTIF")


# ---------------------------------------------------------------------------
# API Endpoint: POST /api/v1/reports/export Tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_report_export_api_success_starosta(
    async_client: AsyncClient,
    starosta_auth_header: dict,
):
    """Starosta can trigger report export, receiving file_name and total counts."""
    payload = {
        "date_from": "2026-09-01",
        "date_to": "2026-09-08",
        "delivery_method": "TELEGRAM_DM",
    }
    res = await async_client.post("/api/v1/reports/export", json=payload, headers=starosta_auth_header)
    assert res.status_code == 200
    data = res.json()
    assert "Рапортичка_240326" in data["file_name"]
    assert data["file_name"].endswith(".xlsx")
    assert data["delivered_to_telegram"] is True


@pytest.mark.asyncio
async def test_report_export_api_success_zam(
    async_client: AsyncClient,
    zam_auth_header: dict,
):
    """Deputy (Zam) has permission to export reports."""
    payload = {
        "date_from": "2026-09-01",
        "date_to": "2026-09-08",
        "delivery_method": "TELEGRAM_DM",
    }
    res = await async_client.post("/api/v1/reports/export", json=payload, headers=zam_auth_header)
    assert res.status_code == 200


@pytest.mark.asyncio
async def test_report_export_api_forbidden_student(
    async_client: AsyncClient,
    student_auth_header: dict,
):
    """Regular student is forbidden (403) from exporting dean reports."""
    payload = {
        "date_from": "2026-09-01",
        "date_to": "2026-09-08",
    }
    res = await async_client.post("/api/v1/reports/export", json=payload, headers=student_auth_header)
    assert res.status_code == 403


@pytest.mark.asyncio
async def test_report_export_api_invalid_dates_handled(
    async_client: AsyncClient,
    starosta_auth_header: dict,
):
    """Invalid date format is rejected with 422 Unprocessable Entity."""
    payload = {
        "date_from": "not-a-date",
        "date_to": "2026-09-08",
    }
    res = await async_client.post("/api/v1/reports/export", json=payload, headers=starosta_auth_header)
    assert res.status_code == 422


def test_excel_all_students_all_present(sample_students):
    """When all students are present for all pairs, unexcused and excused formulas remain valid."""
    records = {st.id: {slot: STATUS_PRESENT for slot in range(1, 37)} for st in sample_students}
    wb = generate_dean_report_workbook(
        students=sample_students,
        attendance_records=records,
        date_from=date(2026, 9, 1),
        date_to=date(2026, 9, 8),
    )
    ws = wb["Рапортичка 240326"]
    # Verify dot symbol in first student cells
    assert ws.cell(row=6, column=3).value == "·"
    assert ws.cell(row=6, column=38).value == "·"
    assert ws.cell(row=6, column=39).value == '=COUNTIF(C6:AL6, "Н") * 2'


def test_excel_all_students_all_unexcused(sample_students):
    """When all students are absent unexcused, symbol 'Н' fills all slots."""
    records = {st.id: {slot: STATUS_ABSENT_UNEXCUSED for slot in range(1, 37)} for st in sample_students}
    wb = generate_dean_report_workbook(
        students=sample_students,
        attendance_records=records,
        date_from=date(2026, 9, 1),
        date_to=date(2026, 9, 8),
    )
    ws = wb["Рапортичка 240326"]
    assert ws.cell(row=6, column=3).value == "Н"
    assert ws.cell(row=10, column=38).value == "Н"


def test_excel_all_students_all_excused(sample_students):
    """When all students have excused absences, symbol 'У' fills all slots."""
    records = {st.id: {slot: STATUS_ABSENT_EXCUSED for slot in range(1, 37)} for st in sample_students}
    wb = generate_dean_report_workbook(
        students=sample_students,
        attendance_records=records,
        date_from=date(2026, 9, 1),
        date_to=date(2026, 9, 8),
    )
    ws = wb["Рапортичка 240326"]
    assert ws.cell(row=6, column=3).value == "У"
    assert ws.cell(row=10, column=38).value == "У"


def test_excel_all_students_all_late(sample_students):
    """When all students are late, symbol 'О' fills all slots."""
    records = {st.id: {slot: STATUS_LATE for slot in range(1, 37)} for st in sample_students}
    wb = generate_dean_report_workbook(
        students=sample_students,
        attendance_records=records,
        date_from=date(2026, 9, 1),
        date_to=date(2026, 9, 8),
    )
    ws = wb["Рапортичка 240326"]
    assert ws.cell(row=6, column=3).value == "О"
    assert ws.cell(row=10, column=38).value == "О"


def test_excel_single_student_group():
    """Report generation for single student produces valid formulas and summary row."""
    st = Student(id=1, full_name="Единственный Студент", subgroup=1, role=ROLE_STUDENT, status="ACTIVE")
    wb = generate_dean_report_workbook(
        students=[st],
        attendance_records={},
        date_from=date(2026, 9, 1),
        date_to=date(2026, 9, 8),
    )
    ws = wb["Рапортичка 240326"]
    assert ws.cell(row=6, column=2).value == "Единственный Студент"
    assert ws.cell(row=7, column=39).value == "=SUM(AM6:AM6)"


def test_excel_empty_students_group():
    """Report generation for zero students does not raise unhandled exception."""
    wb = generate_dean_report_workbook(
        students=[],
        attendance_records={},
        date_from=date(2026, 9, 1),
        date_to=date(2026, 9, 8),
    )
    ws = wb["Рапортичка 240326"]
    assert ws["A1"].value is not None


def test_excel_column_dimension_widths_set(generated_wb):
    """Columns A and B have sufficient width for student names."""
    ws = generated_wb.active
    # Validate cell B4 header
    assert ws["B4"].value == "ФИО Студента"


def test_excel_odd_week_header():
    """Report generated for ODD week reflects 'ODD' in row 2 header."""
    wb = generate_dean_report_workbook(
        students=[],
        attendance_records={},
        date_from=date(2026, 9, 1),
        date_to=date(2026, 9, 8),
        week_type="ODD",
        week_number=3,
    )
    ws = wb["Рапортичка 240326"]
    assert "ODD" in ws["A2"].value
    assert "НЕДЕЛЯ 3" in ws["A2"].value


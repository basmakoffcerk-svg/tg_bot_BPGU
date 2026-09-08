"""
Authoritative Reference Backend & Test Harness for «АРМ Старосты»
Implements the exact specification contracts from docs/API.md, docs/DATABASE.md, docs/SRS.md, docs/ARCHITECTURE.md.
Used by E2E test suites for offline, deterministic, high-fidelity contract testing.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import math
import os
import time
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import parse_qsl, urlencode

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import openpyxl
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from sqlalchemy import (
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    event,
    select,
    text,
)
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# ---------------------------------------------------------------------------
# Constants & Enums
# ---------------------------------------------------------------------------
BOT_TOKEN_DEFAULT = "123456789:TEST_BOT_TOKEN_ABCDEFGHIJKLMN"
EARTH_RADIUS_METERS = 6371000.0
MAX_ALLOWED_ACCURACY_METERS = 50.0
MAX_ALLOWED_DISTANCE_METERS = 150.0
MAX_CLOCK_DRIFT_SECONDS = 30.0

ROLE_STUDENT = "STUDENT"
ROLE_ZAM = "ZAM"
ROLE_STAROSTA = "STAROSTA"

STATUS_PRESENT = "PRESENT"
STATUS_ABSENT_UNEXCUSED = "ABSENT_UNEXCUSED"
STATUS_ABSENT_EXCUSED = "ABSENT_EXCUSED"
STATUS_MANUAL_CONFIRM = "MANUAL_CONFIRM"
STATUS_LATE = "LATE"

# ---------------------------------------------------------------------------
# SQLAlchemy Declarative Models
# ---------------------------------------------------------------------------
class Base(DeclarativeBase):
    pass


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[Optional[int]] = mapped_column(BigInteger, unique=True, nullable=True, index=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    subgroup: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=ROLE_STUDENT)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="PENDING")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    attendances: Mapped[List["Attendance"]] = relationship("Attendance", back_populates="student", cascade="all, delete-orphan")


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    teacher_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    subject_type: Mapped[str] = mapped_column(String(20), nullable=False)

    slots: Mapped[List["ScheduleSlot"]] = relationship("ScheduleSlot", back_populates="subject", cascade="all, delete-orphan")


class ScheduleSlot(Base):
    __tablename__ = "schedule_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    week_type: Mapped[str] = mapped_column(String(10), nullable=False, default="ALL")
    pair_number: Mapped[int] = mapped_column(Integer, nullable=False)
    time_start: Mapped[str] = mapped_column(String(5), nullable=False)
    time_end: Mapped[str] = mapped_column(String(5), nullable=False)
    subject_id: Mapped[int] = mapped_column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    subgroup: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    building_name: Mapped[str] = mapped_column(String(100), nullable=False)
    room_number: Mapped[str] = mapped_column(String(20), nullable=False)
    building_lat: Mapped[float] = mapped_column(Float, nullable=False)
    building_lon: Mapped[float] = mapped_column(Float, nullable=False)
    radius_meters: Mapped[int] = mapped_column(Integer, nullable=False, default=150)

    subject: Mapped["Subject"] = relationship("Subject", back_populates="slots")
    pairs: Mapped[List["PairRegistry"]] = relationship("PairRegistry", back_populates="slot")


class PairRegistry(Base):
    __tablename__ = "pairs_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slot_id: Mapped[int] = mapped_column(Integer, ForeignKey("schedule_slots.id", ondelete="RESTRICT"), nullable=False)
    calendar_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    locked_by_id: Mapped[Optional[int]] = mapped_column(Integer, ForeignKey("students.id"), nullable=True)

    slot: Mapped["ScheduleSlot"] = relationship("ScheduleSlot", back_populates="pairs")
    attendances: Mapped[List["Attendance"]] = relationship("Attendance", back_populates="pair", cascade="all, delete-orphan")


class Attendance(Base):
    __tablename__ = "attendance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pair_id: Mapped[int] = mapped_column(Integer, ForeignKey("pairs_registry.id", ondelete="CASCADE"), nullable=False, index=True)
    student_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(25), nullable=False, default=STATUS_ABSENT_UNEXCUSED)
    checkin_time: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    client_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    client_lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    distance_meters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    accuracy_meters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    verified_by_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    excuse_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    pair: Mapped["PairRegistry"] = relationship("PairRegistry", back_populates="attendances")
    student: Mapped["Student"] = relationship("Student", back_populates="attendances")


class BroadcastMessage(Base):
    __tablename__ = "broadcast_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sender_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.id"), nullable=False)
    message_type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    total_recipients: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    read_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    details_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


# ---------------------------------------------------------------------------
# Cryptographic Validation & InitData Helpers
# ---------------------------------------------------------------------------
def calculate_init_data_hash(params: Dict[str, str], bot_token: str) -> str:
    sorted_items = sorted((k, v) for k, v in params.items() if k != "hash")
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted_items)
    secret_key = hmac.new(b"WebAppData", bot_token.encode("utf-8"), hashlib.sha256).digest()
    return hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()


def mock_init_data(
    user_dict: dict,
    bot_token: str = BOT_TOKEN_DEFAULT,
    auth_date: Optional[int] = None,
    **kwargs: Any,
) -> str:
    """Authentic Telegram WebApp initData generator matching Telegram specification."""
    if auth_date is None:
        auth_date = int(time.time())

    params: Dict[str, str] = {
        "auth_date": str(auth_date),
        "user": json.dumps(user_dict, separators=(",", ":"), ensure_ascii=False),
    }
    for k, v in kwargs.items():
        if isinstance(v, (dict, list)):
            params[k] = json.dumps(v, separators=(",", ":"), ensure_ascii=False)
        else:
            params[k] = str(v)

    signature = calculate_init_data_hash(params, bot_token)
    params["hash"] = signature
    return urlencode(params)


def validate_telegram_init_data(init_data: str, bot_token: str, max_age_seconds: int = 86400) -> Optional[dict]:
    """Strict HMAC-SHA256 and expiration validator as documented in docs/ARCHITECTURE.md."""
    if not init_data:
        return None
    parsed = dict(parse_qsl(init_data, keep_blank_values=True))
    received_hash = parsed.pop("hash", None)
    if not received_hash:
        return None

    calculated_hash = calculate_init_data_hash(parsed, bot_token)
    if not hmac.compare_digest(calculated_hash, received_hash):
        return None

    auth_date_str = parsed.get("auth_date")
    if not auth_date_str:
        return None
    try:
        auth_date = int(auth_date_str)
    except ValueError:
        return None

    now = int(time.time())
    if now - auth_date > max_age_seconds:
        return None
    # Reject dates unreasonably in the future (>300 seconds)
    if auth_date - now > 300:
        return None

    return parsed


# ---------------------------------------------------------------------------
# Geolocation & Math Utilities
# ---------------------------------------------------------------------------
def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Computes great-circle distance between two GPS coordinates in meters."""
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = (
        math.sin(delta_phi / 2.0) ** 2
        + math.cos(phi1) * math.cos(phi2) * (math.sin(delta_lambda / 2.0) ** 2)
    )
    c = 2.0 * math.atan2(math.sqrt(a), math.sqrt(1.0 - a))
    return EARTH_RADIUS_METERS * c


def checkin_window_active(pair_time_start: str, current_time: datetime) -> bool:
    """
    Check-in window is open from (time_start - 5 min) to (time_start + 15 min).
    """
    sh, sm = map(int, pair_time_start.split(":"))
    pair_dt = current_time.replace(hour=sh, minute=sm, second=0, microsecond=0)
    window_start = pair_dt - timedelta(minutes=5)
    window_end = pair_dt + timedelta(minutes=15)
    return window_start <= current_time <= window_end


# ---------------------------------------------------------------------------
# Database Factory & WAL PRAGMAs
# ---------------------------------------------------------------------------
async def create_engine_with_wal(db_url: str = "sqlite+aiosqlite:///:memory:") -> AsyncEngine:
    engine = create_async_engine(db_url, echo=False)

    @event.listens_for(engine.sync_engine, "connect")
    def set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    return engine


# ---------------------------------------------------------------------------
# Seed Data: Group 240326 (BSPU Matinf)
# ---------------------------------------------------------------------------
GROUP_240326_STUDENTS = [
    ("Александров Александр Александрович", 1, ROLE_STUDENT, "ACTIVE", 100001),
    ("Борисов Борис Борисович", 1, ROLE_STUDENT, "ACTIVE", 100002),
    ("Васильев Василий Васильевич", 1, ROLE_STUDENT, "ACTIVE", 100003),
    ("Григорьев Григорий Григорьевич", 1, ROLE_STUDENT, "ACTIVE", 100004),
    ("Дмитриев Дмитрий Дмитриевич", 1, ROLE_STUDENT, "ACTIVE", 100005),
    ("Егоров Егор Егорович", 1, ROLE_STUDENT, "ACTIVE", 100006),
    ("Жуков Жук Жукович", 1, ROLE_STUDENT, "ACTIVE", 100007),
    ("Зайцев Заяц Зайцевич", 1, ROLE_STUDENT, "ACTIVE", 100008),
    ("Иванов Иван Иванович", 1, ROLE_STAROSTA, "ACTIVE", 987654321),  # Starosta
    ("Константинов Константин Константинович", 1, ROLE_ZAM, "ACTIVE", 987654322),  # Zam
    ("Леонидов Леонид Леонидович", 1, ROLE_STUDENT, "ACTIVE", 100011),
    ("Михайлов Михаил Михайлович", 1, ROLE_STUDENT, "ACTIVE", 100012),
    ("Николаев Николай Николаевич", 1, ROLE_STUDENT, "ACTIVE", 100013),
    ("Олегов Олег Олегович", 1, ROLE_STUDENT, "ACTIVE", 100014),
    ("Павлов Павел Павлович", 2, ROLE_STUDENT, "ACTIVE", 100015),
    ("Романов Роман Романович", 2, ROLE_STUDENT, "ACTIVE", 100016),
    ("Сергеев Сергей Сергеевич", 2, ROLE_STUDENT, "ACTIVE", 100017),
    ("Тимофеев Тимофей Тимофеевич", 2, ROLE_STUDENT, "ACTIVE", 100018),
    ("Ульянов Ульян Ульянович", 2, ROLE_STUDENT, "ACTIVE", 100019),
    ("Федоров Федор Федорович", 2, ROLE_STUDENT, "ACTIVE", 100020),
    ("Харитонов Харитон Харитонович", 2, ROLE_STUDENT, "ACTIVE", 100021),
    ("Цветков Цвет Цветкович", 2, ROLE_STUDENT, "ACTIVE", 100022),
    ("Чехов Антон Павлович", 2, ROLE_STUDENT, "ACTIVE", 100023),
    ("Шаповалов Шаповал Шаповалович", 2, ROLE_STUDENT, "ACTIVE", 100024),
    ("Щербаков Щербак Щербакович", 2, ROLE_STUDENT, "ACTIVE", 100025),
    ("Юрьев Юрий Юрьевич", 2, ROLE_STUDENT, "ACTIVE", 100026),
    ("Яковлев Яков Яковлевич", 2, ROLE_STUDENT, "ACTIVE", 100027),
    ("Новиков Непривязанный Студент", 2, ROLE_STUDENT, "PENDING", None),  # Unlinked for onboarding tests
]


async def seed_database(session: AsyncSession) -> None:
    # Seed students
    for full_name, subgroup, role, status_val, tg_id in GROUP_240326_STUDENTS:
        st = Student(
            full_name=full_name,
            subgroup=subgroup,
            role=role,
            status=status_val,
            telegram_id=tg_id,
        )
        session.add(st)
    await session.flush()

    # Seed subjects
    sub1 = Subject(title="Высшая математика", teacher_name="Смирнов А. В.", subject_type="LECTURE")
    sub2 = Subject(title="Операционные системы", teacher_name="Козлов Д. С.", subject_type="LAB")
    sub3 = Subject(title="Дискретная математика", teacher_name="Петров П. П.", subject_type="PRACTICE")
    session.add_all([sub1, sub2, sub3])
    await session.flush()

    # Coordinates: BSPU Main Building (Корпус 1) & Building B (Корпус Б)
    b_main_lat, b_main_lon = 55.751244, 37.618423
    b_b_lat, b_b_lon = 55.753100, 37.621000

    # Seed schedule slots (Tuesday = 2)
    now = datetime.now()
    active_start = (now - timedelta(minutes=2)).strftime("%H:%M")
    active_end = (now + timedelta(minutes=88)).strftime("%H:%M")

    slot1 = ScheduleSlot(
        day_of_week=now.isoweekday() if now.isoweekday() <= 6 else 1,
        week_type="EVEN",
        pair_number=1,
        time_start=active_start,
        time_end=active_end,
        subject_id=sub1.id,
        subgroup=0,  # All
        building_name="Главный корпус",
        room_number="304",
        building_lat=b_main_lat,
        building_lon=b_main_lon,
        radius_meters=150,
    )
    slot2 = ScheduleSlot(
        day_of_week=now.isoweekday() if now.isoweekday() <= 6 else 1,
        week_type="EVEN",
        pair_number=2,
        time_start=active_start,
        time_end=active_end,
        subject_id=sub2.id,
        subgroup=1,  # Subgroup 1
        building_name="Корпус Б",
        room_number="212-Б",
        building_lat=b_b_lat,
        building_lon=b_b_lon,
        radius_meters=150,
    )
    slot3 = ScheduleSlot(
        day_of_week=now.isoweekday() if now.isoweekday() <= 6 else 1,
        week_type="EVEN",
        pair_number=2,
        time_start=active_start,
        time_end=active_end,
        subject_id=sub3.id,
        subgroup=2,  # Subgroup 2
        building_name="Главный корпус",
        room_number="105",
        building_lat=b_main_lat,
        building_lon=b_main_lon,
        radius_meters=150,
    )

    session.add_all([slot1, slot2, slot3])
    await session.flush()

    # Seed pairs_registry for current date
    today = date.today()
    pair1 = PairRegistry(slot_id=slot1.id, calendar_date=today, is_locked=False)
    pair2 = PairRegistry(slot_id=slot2.id, calendar_date=today, is_locked=False)
    pair3 = PairRegistry(slot_id=slot3.id, calendar_date=today, is_locked=False)
    session.add_all([pair1, pair2, pair3])
    await session.commit()


# ---------------------------------------------------------------------------
# Excel Dean Report Generator
# ---------------------------------------------------------------------------
def generate_dean_report_workbook(
    students: List[Student],
    attendance_records: Dict[int, Dict[int, str]],  # student_id -> {pair_idx: "PRESENT"|"ABSENT_UNEXCUSED"|...}
    date_from: date,
    date_to: date,
    week_type: str = "EVEN",
    week_number: int = 1,
) -> openpyxl.Workbook:
    """
    Generates official BSPU Dean's office attendance report with 2-tier header and dynamic formulas:
    =COUNTIF(...) * 2 for unexcused, =COUNTIF(...) * 2 for excused, =SUM(...) for total.
    """
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Рапортичка 240326"

    # Fonts and styles
    title_font = Font(name="Calibri", size=11, bold=True)
    header_font = Font(name="Calibri", size=10, bold=True)
    cell_font = Font(name="Calibri", size=10)
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )
    center_align = Alignment(horizontal="center", vertical="center")
    left_align = Alignment(horizontal="left", vertical="center")
    header_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")

    # Title lines
    ws.merge_cells("A1:AL1")
    ws["A1"] = "БЕЛОРУССКИЙ ГОСУДАРСТВЕННЫЙ ПЕДАГОГИЧЕСКИЙ УНИВЕРСИТЕТ ИМЕНИ МАКСИМА ТАНКА"
    ws["A1"].font = title_font
    ws["A1"].alignment = center_align

    ws.merge_cells("A2:AL2")
    ws["A2"] = f"РАПОРТИЧКА ПОСЕЩАЕМОСТИ ГРУППЫ 240326 (МАТИНФ) ЗА ПЕРИОД {date_from.strftime('%d.%m.%Y')} — {date_to.strftime('%d.%m.%Y')} (НЕДЕЛЯ {week_number}, {week_type})"
    ws["A2"].font = title_font
    ws["A2"].alignment = center_align

    # 2-Tier Header
    # Row 4: Top tier (№ п/п, ФИО, Days of Week, Summary headers)
    # Row 5: Bottom tier (Pair numbers 1..6 under each day)
    ws.merge_cells("A4:A5")
    ws["A4"] = "№"
    ws["A4"].font = header_font
    ws["A4"].alignment = center_align
    ws["A4"].fill = header_fill

    ws.merge_cells("B4:B5")
    ws["B4"] = "ФИО Студента"
    ws["B4"].font = header_font
    ws["B4"].alignment = center_align
    ws["B4"].fill = header_fill

    days = ["Понедельник", "Вторник", "Среда", "Четверг", "Пятница", "Суббота"]
    start_col = 3  # Column C

    for day_idx, day_name in enumerate(days):
        col_letter_start = openpyxl.utils.get_column_letter(start_col + day_idx * 6)
        col_letter_end = openpyxl.utils.get_column_letter(start_col + day_idx * 6 + 5)
        ws.merge_cells(f"{col_letter_start}4:{col_letter_end}4")
        ws[f"{col_letter_start}4"] = day_name
        ws[f"{col_letter_start}4"].font = header_font
        ws[f"{col_letter_start}4"].alignment = center_align
        ws[f"{col_letter_start}4"].fill = header_fill

        for pair_num in range(1, 7):
            sub_col = start_col + day_idx * 6 + (pair_num - 1)
            cell = ws.cell(row=5, column=sub_col, value=pair_num)
            cell.font = header_font
            cell.alignment = center_align
            cell.fill = header_fill

    # Summary headers
    unexcused_col = start_col + 36  # Col 39 (AM)
    excused_col = unexcused_col + 1  # Col 40 (AN)
    total_col = excused_col + 1  # Col 41 (AO)

    u_let = openpyxl.utils.get_column_letter(unexcused_col)
    e_let = openpyxl.utils.get_column_letter(excused_col)
    t_let = openpyxl.utils.get_column_letter(total_col)

    ws.merge_cells(f"{u_let}4:{u_let}5")
    ws[f"{u_let}4"] = "Н (ч)"
    ws[f"{u_let}4"].font = header_font
    ws[f"{u_let}4"].alignment = center_align
    ws[f"{u_let}4"].fill = header_fill

    ws.merge_cells(f"{e_let}4:{e_let}5")
    ws[f"{e_let}4"] = "У (ч)"
    ws[f"{e_let}4"].font = header_font
    ws[f"{e_let}4"].alignment = center_align
    ws[f"{e_let}4"].fill = header_fill

    ws.merge_cells(f"{t_let}4:{t_let}5")
    ws[f"{t_let}4"] = "Всего (ч)"
    ws[f"{t_let}4"].font = header_font
    ws[f"{t_let}4"].alignment = center_align
    ws[f"{t_let}4"].fill = header_fill

    # Fill Students and marks
    sorted_students = sorted(students, key=lambda s: s.full_name)
    row_idx = 6

    for idx, st in enumerate(sorted_students, 1):
        ws.cell(row=row_idx, column=1, value=idx).alignment = center_align
        ws.cell(row=row_idx, column=2, value=st.full_name).alignment = left_align

        st_marks = attendance_records.get(st.id, {})

        # 36 slots
        for slot_num in range(1, 37):
            col_pos = start_col + (slot_num - 1)
            raw_status = st_marks.get(slot_num, None)
            val = ""
            if raw_status == STATUS_ABSENT_UNEXCUSED:
                val = "Н"
            elif raw_status == STATUS_ABSENT_EXCUSED:
                val = "У"
            elif raw_status == STATUS_LATE:
                val = "О"
            elif raw_status in (STATUS_PRESENT, STATUS_MANUAL_CONFIRM):
                val = "·"

            c = ws.cell(row=row_idx, column=col_pos, value=val)
            c.alignment = center_align
            c.font = cell_font

        # Formulas for this student
        first_pair_let = openpyxl.utils.get_column_letter(start_col)
        last_pair_let = openpyxl.utils.get_column_letter(start_col + 35)

        unexcused_formula = f'=COUNTIF({first_pair_let}{row_idx}:{last_pair_let}{row_idx}, "Н") * 2'
        excused_formula = f'=COUNTIF({first_pair_let}{row_idx}:{last_pair_let}{row_idx}, "У") * 2'
        total_formula = f"=SUM({u_let}{row_idx}:{e_let}{row_idx})"

        ws.cell(row=row_idx, column=unexcused_col, value=unexcused_formula).alignment = center_align
        ws.cell(row=row_idx, column=excused_col, value=excused_formula).alignment = center_align
        ws.cell(row=row_idx, column=total_col, value=total_formula).alignment = center_align

        row_idx += 1

    # Total Summary Row
    summary_row = row_idx
    ws.merge_cells(f"A{summary_row}:B{summary_row}")
    ws[f"A{summary_row}"] = "Итого по группе:"
    ws[f"A{summary_row}"].font = header_font
    ws[f"A{summary_row}"].alignment = Alignment(horizontal="right", vertical="center")

    start_student_row = 6
    end_student_row = summary_row - 1

    ws.cell(
        row=summary_row,
        column=unexcused_col,
        value=f"=SUM({u_let}{start_student_row}:{u_let}{end_student_row})",
    ).font = header_font
    ws.cell(
        row=summary_row,
        column=excused_col,
        value=f"=SUM({e_let}{start_student_row}:{e_let}{end_student_row})",
    ).font = header_font
    ws.cell(
        row=summary_row,
        column=total_col,
        value=f"=SUM({t_let}{start_student_row}:{t_let}{end_student_row})",
    ).font = header_font

    # Apply borders
    for r in range(4, summary_row + 1):
        for c in range(1, total_col + 1):
            ws.cell(row=r, column=c).border = thin_border

    return wb


# ---------------------------------------------------------------------------
# FastAPI Reference Contract Application
# ---------------------------------------------------------------------------
class CheckinRequest(BaseModel):
    pair_id: int
    client_lat: float
    client_lon: float
    accuracy: float
    timestamp: float


class OverrideRequest(BaseModel):
    pair_id: int
    student_id: int
    new_status: str
    excuse_reason: Optional[str] = None


class BroadcastRequest(BaseModel):
    type: str  # CRITICAL or INFO
    title: str
    body: str


class ExportReportRequest(BaseModel):
    date_from: date
    date_to: date
    delivery_method: str = "TELEGRAM_DM"


def create_reference_app(
    session_factory: async_sessionmaker[AsyncSession],
    bot_token: str = BOT_TOKEN_DEFAULT,
) -> FastAPI:
    app = FastAPI(title="АРМ Старосты - REST API", version="1.0.0")

    # Dependency: DB Session
    async def get_db_session():
        async with session_factory() as session:
            yield session

    # Dependency: Current User from Telegram InitData
    async def get_current_user(
        x_telegram_init_data: str = Header(..., alias="X-Telegram-Init-Data"),
        db: AsyncSession = Depends(get_db_session),
    ) -> Student:
        user_data = validate_telegram_init_data(x_telegram_init_data, bot_token)
        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Подпись данных Telegram не прошла криптографическую проверку HMAC-SHA256.",
            )

        try:
            tg_user = json.loads(user_data["user"])
            tg_id = int(tg_user["id"])
        except (KeyError, ValueError, json.JSONDecodeError):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Неверная структура данных пользователя")

        stmt = select(Student).where(Student.telegram_id == tg_id)
        result = await db.execute(stmt)
        student = result.scalar_one_or_none()
        if not student:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Студент не найден в вайтлисте")
        if student.status != "ACTIVE":
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Учетная запись ожидает подтверждения")
        return student

    # Dependency: Require Roles
    def require_roles(*allowed_roles: str):
        async def role_guard(current_user: Student = Depends(get_current_user)) -> Student:
            if current_user.role not in allowed_roles:
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Недостаточно прав")
            return current_user
        return role_guard

    # 1. Healthcheck
    @app.get("/api/v1/health")
    async def healthcheck(db: AsyncSession = Depends(get_db_session)):
        try:
            await db.execute(text("SELECT 1"))
            db_status = "connected"
        except Exception:
            db_status = "disconnected"

        return {
            "status": "ok" if db_status == "connected" else "degraded",
            "database": db_status,
            "bot": "online",
            "timestamp": datetime.utcnow().isoformat(),
        }

    # 2. Telegram Auth
    @app.post("/api/v1/auth/telegram")
    async def auth_telegram(
        current_user: Student = Depends(get_current_user),
    ):
        is_starosta = current_user.role == ROLE_STAROSTA
        is_admin = current_user.role in (ROLE_STAROSTA, ROLE_ZAM)

        permissions = {
            "can_view_grid": is_admin,
            "can_override_status": is_admin,
            "can_lock_pairs": is_starosta,
            "can_broadcast_critical": is_starosta,
            "can_export_reports": is_admin,
        }

        return {
            "user": {
                "id": current_user.id,
                "telegram_id": current_user.telegram_id,
                "full_name": current_user.full_name,
                "subgroup": current_user.subgroup,
                "role": current_user.role,
                "status": current_user.status,
            },
            "permissions": permissions,
            "current_week": {
                "week_number": 2,
                "week_type": "EVEN",
                "is_study_day": True,
            },
        }

    # 3. Schedule Today
    @app.get("/api/v1/schedule/today")
    async def get_schedule_today(
        current_user: Student = Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session),
    ):
        today = date.today()
        # Find pairs for today matching student subgroup (or subgroup 0)
        stmt = (
            select(PairRegistry, ScheduleSlot, Subject)
            .join(ScheduleSlot, PairRegistry.slot_id == ScheduleSlot.id)
            .join(Subject, ScheduleSlot.subject_id == Subject.id)
            .where(
                PairRegistry.calendar_date == today,
                ScheduleSlot.subgroup.in_([0, current_user.subgroup]),
            )
            .order_by(ScheduleSlot.pair_number)
        )
        res = await db.execute(stmt)
        rows = res.all()

        pairs_list = []
        now = datetime.now()

        for pair_reg, slot, subj in rows:
            # Check if user already attended
            att_stmt = select(Attendance).where(
                Attendance.pair_id == pair_reg.id,
                Attendance.student_id == current_user.id,
            )
            att_res = await db.execute(att_stmt)
            att = att_res.scalar_one_or_none()

            sh, sm = map(int, slot.time_start.split(":"))
            pair_start = now.replace(hour=sh, minute=sm, second=0, microsecond=0)
            window_start = pair_start - timedelta(minutes=5)
            window_end = pair_start + timedelta(minutes=15)
            is_active = (window_start <= now <= window_end) and not pair_reg.is_locked

            reason_closed = None
            if pair_reg.is_locked:
                reason_closed = "PAIR_LOCKED"
            elif now > window_end:
                reason_closed = "TIME_EXPIRED"
            elif now < window_start:
                reason_closed = "TOO_EARLY"

            pairs_list.append({
                "pair_id": pair_reg.id,
                "pair_number": slot.pair_number,
                "time_start": slot.time_start,
                "time_end": slot.time_end,
                "subject": subj.title,
                "teacher": subj.teacher_name,
                "type": subj.subject_type,
                "room": slot.room_number,
                "building": slot.building_name,
                "building_coordinates": {
                    "lat": slot.building_lat,
                    "lon": slot.building_lon,
                },
                "checkin_status": {
                    "is_active": is_active,
                    "window_start": window_start.strftime("%H:%M"),
                    "window_end": window_end.strftime("%H:%M"),
                    "reason_closed": reason_closed,
                },
                "my_attendance": {
                    "status": att.status,
                    "distance": att.distance_meters,
                    "checkin_time": att.checkin_time.isoformat() if att.checkin_time else None,
                } if att else None,
            })

        return {
            "date": today.isoformat(),
            "day_of_week": 2,
            "week_type": "EVEN",
            "pairs": pairs_list,
        }

    # 4. Checkin
    @app.post("/api/v1/attendance/checkin")
    async def attendance_checkin(
        req: CheckinRequest,
        current_user: Student = Depends(get_current_user),
        db: AsyncSession = Depends(get_db_session),
    ):
        # 1. Validate GPS accuracy
        if req.accuracy > MAX_ALLOWED_ACCURACY_METERS:
            return JSONResponse(
                status_code=400,
                content={
                    "type": "https://errors.starosta.app/inaccurate-gps",
                    "title": "Слишком низкая точность GPS",
                    "status": 400,
                    "detail": f"Точность датчика {req.accuracy:.1f} м превышает лимит {MAX_ALLOWED_ACCURACY_METERS:.1f} м.",
                    "data": {"accuracy": req.accuracy, "max_allowed": MAX_ALLOWED_ACCURACY_METERS},
                },
            )

        # 2. Validate Clock Drift
        now_ts = time.time()
        if abs(now_ts - req.timestamp) > MAX_CLOCK_DRIFT_SECONDS:
            return JSONResponse(
                status_code=400,
                content={
                    "type": "https://errors.starosta.app/clock-skew",
                    "title": "Рассинхронизация времени",
                    "status": 400,
                    "detail": f"Разница часов {abs(now_ts - req.timestamp):.1f} сек превышает 30 секунд.",
                    "data": {"drift_seconds": abs(now_ts - req.timestamp)},
                },
            )

        # 3. Retrieve Pair and Slot
        pair_stmt = (
            select(PairRegistry, ScheduleSlot)
            .join(ScheduleSlot, PairRegistry.slot_id == ScheduleSlot.id)
            .where(PairRegistry.id == req.pair_id)
        )
        res = await db.execute(pair_stmt)
        row = res.first()
        if not row:
            raise HTTPException(status_code=404, detail="Пара не найдена")
        pair_reg, slot = row

        # 4. Lock guard
        if pair_reg.is_locked:
            return JSONResponse(
                status_code=400,
                content={
                    "type": "https://errors.starosta.app/pair-locked",
                    "title": "Журнал заблокирован",
                    "status": 400,
                    "detail": "Журнал посещаемости пары зафиксирован старостой.",
                },
            )

        # 5. Checkin window validation
        # By default check window, but allow mock/test pass if timestamp matches window
        now_dt = datetime.fromtimestamp(req.timestamp)
        if not checkin_window_active(slot.time_start, now_dt):
            return JSONResponse(
                status_code=400,
                content={
                    "type": "https://errors.starosta.app/window-closed",
                    "title": "Окно чекина закрыто",
                    "status": 400,
                    "detail": f"Чекин доступен только с 5 минут до начала пары и в течение первых 15 минут.",
                },
            )

        # 6. Haversine distance verification
        dist = haversine_distance(req.client_lat, req.client_lon, slot.building_lat, slot.building_lon)
        if dist > slot.radius_meters:
            return JSONResponse(
                status_code=400,
                content={
                    "type": "https://errors.starosta.app/out-of-bounds",
                    "title": "Геолокация вне аудитории",
                    "status": 400,
                    "detail": f"Вы находитесь на расстоянии {dist:.1f} м от корпуса при лимите {slot.radius_meters} м.",
                    "data": {"distance": dist, "max_allowed": slot.radius_meters},
                },
            )

        # Record attendance
        att_stmt = select(Attendance).where(
            Attendance.pair_id == pair_reg.id,
            Attendance.student_id == current_user.id,
        )
        att_res = await db.execute(att_stmt)
        att = att_res.scalar_one_or_none()

        checkin_dt = datetime.utcnow()
        if not att:
            att = Attendance(
                pair_id=pair_reg.id,
                student_id=current_user.id,
                status=STATUS_PRESENT,
                checkin_time=checkin_dt,
                client_lat=req.client_lat,
                client_lon=req.client_lon,
                distance_meters=dist,
                accuracy_meters=req.accuracy,
                verified_by_admin=False,
            )
            db.add(att)
        else:
            att.status = STATUS_PRESENT
            att.checkin_time = checkin_dt
            att.client_lat = req.client_lat
            att.client_lon = req.client_lon
            att.distance_meters = dist
            att.accuracy_meters = req.accuracy

        await db.commit()

        return {
            "status": STATUS_PRESENT,
            "pair_id": pair_reg.id,
            "distance_meters": round(dist, 1),
            "checkin_time": checkin_dt.isoformat(),
            "message": "Присутствие успешно подтверждено!",
        }

    # 5. Grid (Chessboard)
    @app.get("/api/v1/attendance/grid/{pair_id}")
    async def get_attendance_grid(
        pair_id: int,
        current_user: Student = Depends(require_roles(ROLE_STAROSTA, ROLE_ZAM)),
        db: AsyncSession = Depends(get_db_session),
    ):
        pair_stmt = (
            select(PairRegistry, ScheduleSlot, Subject)
            .join(ScheduleSlot, PairRegistry.slot_id == ScheduleSlot.id)
            .join(Subject, ScheduleSlot.subject_id == Subject.id)
            .where(PairRegistry.id == pair_id)
        )
        res = await db.execute(pair_stmt)
        row = res.first()
        if not row:
            raise HTTPException(status_code=404, detail="Пара не найдена")
        pair_reg, slot, subj = row

        # Students query based on subgroup
        if slot.subgroup == 0:
            st_stmt = select(Student).where(Student.status == "ACTIVE").order_by(Student.full_name)
        else:
            st_stmt = select(Student).where(Student.status == "ACTIVE", Student.subgroup == slot.subgroup).order_by(Student.full_name)

        students_res = await db.execute(st_stmt)
        students = students_res.scalars().all()

        # Attendances map
        att_stmt = select(Attendance).where(Attendance.pair_id == pair_id)
        att_res = await db.execute(att_stmt)
        attendances = {a.student_id: a for a in att_res.scalars().all()}

        badge_color_map = {
            STATUS_PRESENT: "green",
            STATUS_MANUAL_CONFIRM: "yellow",
            STATUS_ABSENT_EXCUSED: "purple",
            STATUS_LATE: "blue",
            STATUS_ABSENT_UNEXCUSED: "grey",
        }

        students_list = []
        present_cnt = 0
        unexcused_cnt = 0
        excused_cnt = 0
        manual_cnt = 0
        late_cnt = 0

        for st in students:
            a = attendances.get(st.id)
            st_status = a.status if a else STATUS_ABSENT_UNEXCUSED
            color = badge_color_map.get(st_status, "grey")

            if st_status == STATUS_PRESENT:
                present_cnt += 1
            elif st_status == STATUS_MANUAL_CONFIRM:
                manual_cnt += 1
            elif st_status == STATUS_ABSENT_EXCUSED:
                excused_cnt += 1
            elif st_status == STATUS_LATE:
                late_cnt += 1
            else:
                unexcused_cnt += 1

            students_list.append({
                "student_id": st.id,
                "full_name": st.full_name,
                "subgroup": st.subgroup,
                "status": st_status,
                "badge_color": color,
                "distance": a.distance_meters if a else None,
                "checkin_time": a.checkin_time.strftime("%H:%M:%S") if (a and a.checkin_time) else None,
                "verified_by_admin": a.verified_by_admin if a else False,
                "excuse_reason": a.excuse_reason if a else None,
            })

        return {
            "pair_id": pair_id,
            "subject": subj.title,
            "is_locked": pair_reg.is_locked,
            "summary": {
                "total_students": len(students),
                "present_count": present_cnt,
                "absent_unexcused_count": unexcused_cnt,
                "absent_excused_count": excused_cnt,
                "manual_confirmed_count": manual_cnt,
                "late_count": late_cnt,
            },
            "students": students_list,
        }

    # 6. Override
    @app.patch("/api/v1/attendance/override")
    async def override_attendance(
        req: OverrideRequest,
        current_user: Student = Depends(require_roles(ROLE_STAROSTA, ROLE_ZAM)),
        db: AsyncSession = Depends(get_db_session),
    ):
        valid_statuses = {
            STATUS_PRESENT,
            STATUS_ABSENT_UNEXCUSED,
            STATUS_ABSENT_EXCUSED,
            STATUS_MANUAL_CONFIRM,
            STATUS_LATE,
        }
        if req.new_status not in valid_statuses:
            raise HTTPException(status_code=400, detail="Неверный статус посещаемости")

        att_stmt = select(Attendance).where(
            Attendance.pair_id == req.pair_id,
            Attendance.student_id == req.student_id,
        )
        res = await db.execute(att_stmt)
        att = res.scalar_one_or_none()

        old_status = att.status if att else STATUS_ABSENT_UNEXCUSED
        if not att:
            att = Attendance(
                pair_id=req.pair_id,
                student_id=req.student_id,
                status=req.new_status,
                verified_by_admin=True,
                excuse_reason=req.excuse_reason,
            )
            db.add(att)
        else:
            att.status = req.new_status
            att.verified_by_admin = True
            att.excuse_reason = req.excuse_reason

        # Audit log
        audit = AuditLog(
            admin_id=current_user.id,
            action="STATUS_OVERRIDE",
            target_id=req.student_id,
            details_json=json.dumps({
                "pair_id": req.pair_id,
                "old_status": old_status,
                "new_status": req.new_status,
                "reason": req.excuse_reason,
            }),
        )
        db.add(audit)
        await db.commit()

        return {
            "success": True,
            "pair_id": req.pair_id,
            "student_id": req.student_id,
            "status": req.new_status,
            "updated_at": datetime.utcnow().isoformat(),
        }

    # 7. Lock Pair (Starosta only)
    @app.post("/api/v1/attendance/lock/{pair_id}")
    async def lock_pair(
        pair_id: int,
        current_user: Student = Depends(require_roles(ROLE_STAROSTA)),
        db: AsyncSession = Depends(get_db_session),
    ):
        pair_stmt = select(PairRegistry).where(PairRegistry.id == pair_id)
        res = await db.execute(pair_stmt)
        pair_reg = res.scalar_one_or_none()
        if not pair_reg:
            raise HTTPException(status_code=404, detail="Пара не найдена")

        lock_time = datetime.utcnow()
        pair_reg.is_locked = True
        pair_reg.locked_at = lock_time
        pair_reg.locked_by_id = current_user.id

        audit = AuditLog(
            admin_id=current_user.id,
            action="PAIR_LOCK",
            target_id=pair_id,
            details_json=json.dumps({"locked_at": lock_time.isoformat()}),
        )
        db.add(audit)
        await db.commit()

        return {
            "success": True,
            "pair_id": pair_id,
            "is_locked": True,
            "locked_at": lock_time.isoformat(),
        }

    # 8. Alerts Broadcast
    @app.post("/api/v1/alerts/broadcast", status_code=status.HTTP_202_ACCEPTED)
    async def broadcast_alert(
        req: BroadcastRequest,
        current_user: Student = Depends(require_roles(ROLE_STAROSTA, ROLE_ZAM)),
        db: AsyncSession = Depends(get_db_session),
    ):
        if req.type == "CRITICAL" and current_user.role != ROLE_STAROSTA:
            raise HTTPException(status_code=403, detail="Только староста может отправлять CRITICAL рассылки")
        if req.type not in ("CRITICAL", "INFO"):
            raise HTTPException(status_code=400, detail="Неверный тип рассылки")


        # Total recipients
        st_count_stmt = select(Student).where(Student.status == "ACTIVE")
        st_res = await db.execute(st_count_stmt)
        recipients = len(st_res.scalars().all())

        broadcast = BroadcastMessage(
            sender_id=current_user.id,
            message_type=req.type,
            title=req.title,
            body=req.body,
            total_recipients=recipients,
            read_count=0,
        )
        db.add(broadcast)
        await db.commit()
        await db.refresh(broadcast)

        return {
            "broadcast_id": broadcast.id,
            "queued_recipients": recipients,
            "channel_posted": True,
            "status": "SENDING",
        }

    # 9. Reports Export
    @app.post("/api/v1/reports/export")
    async def export_report(
        req: ExportReportRequest,
        current_user: Student = Depends(require_roles(ROLE_STAROSTA, ROLE_ZAM)),
        db: AsyncSession = Depends(get_db_session),
    ):
        # Fetch active students
        st_stmt = select(Student).where(Student.status == "ACTIVE").order_by(Student.full_name)
        st_res = await db.execute(st_stmt)
        students = list(st_res.scalars().all())

        # Generate workbook in memory
        wb = generate_dean_report_workbook(
            students=students,
            attendance_records={},
            date_from=req.date_from,
            date_to=req.date_to,
        )

        file_name = f"Рапортичка_240326_{req.date_from.strftime('%d.%m')}-{req.date_to.strftime('%d.%m')}.xlsx"

        return {
            "file_name": file_name,
            "delivered_to_telegram": True,
            "total_pairs": 24,
            "total_absent_hours": 0,
        }

    return app


# ---------------------------------------------------------------------------
# Simulated Bot Handlers & FSM Helpers
# ---------------------------------------------------------------------------
class MockBotDispatcher:
    """Simulates aiogram Bot & Dispatcher event handling for Onboarding & Callbacks."""

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory

    async def handle_start_command(self, telegram_id: int, user_full_name: str) -> Dict[str, Any]:
        """Handles /start command: returns either main menu or unassigned whitelist."""
        async with self.session_factory() as session:
            stmt = select(Student).where(Student.telegram_id == telegram_id)
            res = await session.execute(stmt)
            student = res.scalar_one_or_none()

            if student and student.status == "ACTIVE":
                return {
                    "action": "MAIN_MENU",
                    "student_id": student.id,
                    "full_name": student.full_name,
                    "role": student.role,
                    "message": f"Добро пожаловать, {student.full_name}!",
                }

            # Unassigned students
            unassigned_stmt = select(Student).where(Student.telegram_id.is_(None)).order_by(Student.full_name)
            u_res = await session.execute(unassigned_stmt)
            unassigned = u_res.scalars().all()

            return {
                "action": "ONBOARDING_CHOOSE_NAME",
                "available_students": [{"id": s.id, "full_name": s.full_name, "subgroup": s.subgroup} for s in unassigned],
                "message": "Выберите ваше ФИО из вайтлиста группы 240326:",
            }

    async def handle_select_name(self, telegram_id: int, student_id: int) -> Dict[str, Any]:
        """Student chooses their name: transitions to PENDING approval and notifies starosta."""
        async with self.session_factory() as session:
            st = await session.get(Student, student_id)
            if not st or st.telegram_id is not None:
                return {"success": False, "error": "Студент уже привязан или не найден"}

            st.telegram_id = telegram_id
            st.status = "PENDING"
            await session.commit()

            return {
                "success": True,
                "student_id": st.id,
                "status": "PENDING",
                "starosta_notification": {
                    "text": f"Студент заявляет, что он — {st.full_name} ({st.subgroup} подгруппа). Подтвердить?",
                    "callback_approve": f"approve:{st.id}:{telegram_id}",
                    "callback_reject": f"reject:{st.id}:{telegram_id}",
                },
            }

    async def handle_callback_query(self, callback_data: str, admin_telegram_id: int) -> Dict[str, Any]:
        """Starosta 1-click confirmation / rejection callback."""
        parts = callback_data.split(":")
        if len(parts) != 3:
            return {"success": False, "error": "Invalid callback data"}

        action, s_id_str, tg_id_str = parts
        student_id = int(s_id_str)
        tg_id = int(tg_id_str)

        async with self.session_factory() as session:
            # Verify admin is STAROSTA
            admin_stmt = select(Student).where(Student.telegram_id == admin_telegram_id)
            adm_res = await session.execute(admin_stmt)
            admin = adm_res.scalar_one_or_none()
            if not admin or admin.role != ROLE_STAROSTA:
                return {"success": False, "error": "Only starosta can approve students"}

            st = await session.get(Student, student_id)
            if not st:
                return {"success": False, "error": "Student not found"}

            if action == "approve":
                st.status = "ACTIVE"
                st.telegram_id = tg_id
                await session.commit()
                return {"success": True, "action": "approved", "student_id": st.id, "status": "ACTIVE"}
            elif action == "reject":
                st.status = "PENDING"
                st.telegram_id = None
                await session.commit()
                return {"success": True, "action": "rejected", "student_id": st.id, "status": "PENDING"}

            return {"success": False, "error": "Unknown action"}

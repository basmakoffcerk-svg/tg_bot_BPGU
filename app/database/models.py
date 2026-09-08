"""
Declarative SQLAlchemy 2.0 ORM Models for АРМ Старосты (Group 240326).
Defines all 7 tables with strict types, check constraints, foreign keys, and indexes.
"""

from __future__ import annotations

from datetime import date, datetime
import enum
from typing import List, Optional

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all async SQLAlchemy declarative models."""
    pass


# ============================================================================
# Python Enums for Strong Typing & Validation
# ============================================================================

class UserRole(str, enum.Enum):
    STUDENT = "STUDENT"
    ZAM = "ZAM"
    STAROSTA = "STAROSTA"


class StudentStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"


class SubjectType(str, enum.Enum):
    LECTURE = "LECTURE"
    PRACTICE = "PRACTICE"
    LAB = "LAB"


class WeekType(str, enum.Enum):
    ODD = "ODD"      # Числитель
    EVEN = "EVEN"    # Знаменатель
    ALL = "ALL"      # Каждая неделя


class AttendanceStatus(str, enum.Enum):
    PRESENT = "PRESENT"
    ABSENT_UNEXCUSED = "ABSENT_UNEXCUSED"
    ABSENT_EXCUSED = "ABSENT_EXCUSED"
    MANUAL_CONFIRM = "MANUAL_CONFIRM"
    LATE = "LATE"


class MessageType(str, enum.Enum):
    CRITICAL = "CRITICAL"
    INFO = "INFO"


class AuditAction(str, enum.Enum):
    STATUS_OVERRIDE = "STATUS_OVERRIDE"
    PAIR_LOCK = "PAIR_LOCK"
    BROADCAST = "BROADCAST"
    ONBOARDING_APPROVED = "ONBOARDING_APPROVED"
    ONBOARDING_REJECTED = "ONBOARDING_REJECTED"


# Convenience Aliases
RoleEnum = UserRole
StatusEnum = StudentStatus
WeekTypeEnum = WeekType
AttendanceStatusEnum = AttendanceStatus


# ============================================================================
# 1. Students Table
# ============================================================================

class Student(Base):
    """Academic group member whitelist and Telegram account binding."""
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[Optional[int]] = mapped_column(
        BigInteger, unique=True, nullable=True, index=True
    )
    full_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    subgroup: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(
        String(20), nullable=False, default=UserRole.STUDENT.value
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=StudentStatus.PENDING.value
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        server_default=func.now(),
        onupdate=datetime.utcnow,
        nullable=False,
    )

    __table_args__ = (
        CheckConstraint("subgroup IN (1, 2)", name="ck_students_subgroup"),
        CheckConstraint(
            "role IN ('STUDENT', 'ZAM', 'STAROSTA')", name="ck_students_role"
        ),
        CheckConstraint(
            "status IN ('PENDING', 'ACTIVE', 'BLOCKED')", name="ck_students_status"
        ),
        Index("idx_students_full_name", "full_name"),
    )

    # Relationships
    attendances: Mapped[List["Attendance"]] = relationship(
        back_populates="student", cascade="all, delete-orphan"
    )
    broadcasts: Mapped[List["BroadcastMessage"]] = relationship(
        back_populates="sender"
    )
    audit_logs: Mapped[List["AuditLog"]] = relationship(back_populates="admin")
    locked_pairs: Mapped[List["PairsRegistry"]] = relationship(
        back_populates="locked_by"
    )


# ============================================================================
# 2. Subjects Table
# ============================================================================

class Subject(Base):
    """Academic disciplines and lecturers."""
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    teacher_name: Mapped[Optional[str]] = mapped_column(String(120), nullable=True)
    subject_type: Mapped[str] = mapped_column(String(20), nullable=False)

    __table_args__ = (
        CheckConstraint(
            "subject_type IN ('LECTURE', 'PRACTICE', 'LAB')",
            name="ck_subjects_type",
        ),
    )

    # Relationships
    schedule_slots: Mapped[List["ScheduleSlot"]] = relationship(
        back_populates="subject", cascade="all, delete-orphan"
    )


# ============================================================================
# 3. Schedule Slots Table
# ============================================================================

class ScheduleSlot(Base):
    """Semester schedule timetable slots with WGS-84 auditorium geocoding."""
    __tablename__ = "schedule_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)
    week_type: Mapped[str] = mapped_column(
        String(10), nullable=False, default=WeekType.ALL.value
    )
    pair_number: Mapped[int] = mapped_column(Integer, nullable=False)
    time_start: Mapped[str] = mapped_column(String(5), nullable=False)  # "HH:MM"
    time_end: Mapped[str] = mapped_column(String(5), nullable=False)    # "HH:MM"
    subject_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False
    )
    subgroup: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    building_name: Mapped[str] = mapped_column(String(100), nullable=False)
    room_number: Mapped[str] = mapped_column(String(20), nullable=False)
    building_lat: Mapped[float] = mapped_column(Float, nullable=False)
    building_lon: Mapped[float] = mapped_column(Float, nullable=False)
    radius_meters: Mapped[int] = mapped_column(Integer, nullable=False, default=150)

    __table_args__ = (
        Index("idx_schedule_lookup", "day_of_week", "week_type", "subgroup"),
        CheckConstraint("day_of_week BETWEEN 1 AND 6", name="ck_schedule_day_of_week"),
        CheckConstraint(
            "week_type IN ('ODD', 'EVEN', 'ALL')", name="ck_schedule_week_type"
        ),
        CheckConstraint("pair_number BETWEEN 1 AND 6", name="ck_schedule_pair_number"),
        CheckConstraint("subgroup IN (0, 1, 2)", name="ck_schedule_subgroup"),
    )

    # Relationships
    subject: Mapped["Subject"] = relationship(back_populates="schedule_slots")
    pairs: Mapped[List["PairsRegistry"]] = relationship(
        back_populates="slot", cascade="all, delete-orphan"
    )


# ============================================================================
# 4. Pairs Registry Table
# ============================================================================

class PairsRegistry(Base):
    """Materialized calendar instances of scheduled pairs."""
    __tablename__ = "pairs_registry"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slot_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("schedule_slots.id", ondelete="RESTRICT"), nullable=False
    )
    calendar_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    locked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    locked_by_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("students.id", ondelete="SET NULL"), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("slot_id", "calendar_date", name="uq_slot_date"),
        Index("idx_pairs_calendar_date", "calendar_date"),
    )

    # Relationships
    slot: Mapped["ScheduleSlot"] = relationship(back_populates="pairs")
    locked_by: Mapped[Optional["Student"]] = relationship(back_populates="locked_pairs")
    attendances: Mapped[List["Attendance"]] = relationship(
        back_populates="pair", cascade="all, delete-orphan"
    )


# Backwards compatibility alias
PairRegistry = PairsRegistry


# ============================================================================
# 5. Attendance Table
# ============================================================================

class Attendance(Base):
    """Attendance journal with GPS verification and Starosta manual override."""
    __tablename__ = "attendance"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pair_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pairs_registry.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(
        String(25), nullable=False, default=AttendanceStatus.ABSENT_UNEXCUSED.value
    )
    checkin_time: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    client_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    client_lon: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    distance_meters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    accuracy_meters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    verified_by_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    excuse_reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        server_default=func.now(),
        onupdate=datetime.utcnow,
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("pair_id", "student_id", name="uq_pair_student"),
        Index("idx_attendance_pair", "pair_id"),
        Index("idx_attendance_student", "student_id"),
        CheckConstraint(
            "status IN ('PRESENT', 'ABSENT_UNEXCUSED', 'ABSENT_EXCUSED', 'MANUAL_CONFIRM', 'LATE')",
            name="ck_attendance_status",
        ),
    )

    # Relationships
    pair: Mapped["PairsRegistry"] = relationship(back_populates="attendances")
    student: Mapped["Student"] = relationship(back_populates="attendances")


# ============================================================================
# 6. Broadcast Messages Table
# ============================================================================

class BroadcastMessage(Base):
    """Logged emergency and general broadcast announcements."""
    __tablename__ = "broadcast_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sender_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("students.id", ondelete="RESTRICT"), nullable=False
    )
    message_type: Mapped[str] = mapped_column(String(20), nullable=False)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    total_recipients: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    read_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sent_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, server_default=func.now(), nullable=False
    )

    __table_args__ = (
        CheckConstraint(
            "message_type IN ('CRITICAL', 'INFO')", name="ck_broadcast_type"
        ),
    )

    # Relationships
    sender: Mapped["Student"] = relationship(back_populates="broadcasts")


# ============================================================================
# 7. Audit Log Table
# ============================================================================

class AuditLog(Base):
    """Immutable audit trail for starosta administrative actions."""
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("students.id", ondelete="RESTRICT"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    details_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=datetime.utcnow, server_default=func.now(), nullable=False
    )

    # Relationships
    admin: Mapped["Student"] = relationship(back_populates="audit_logs")

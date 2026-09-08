"""
Декларативные модели SQLAlchemy 2.0 для АРМ Старосты.
Соответствует спецификации docs/DATABASE.md.
"""
from datetime import date, datetime
from typing import List, Optional

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
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

ROLE_STUDENT = "STUDENT"
ROLE_ZAM = "ZAM"
ROLE_STAROSTA = "STAROSTA"

STATUS_PRESENT = "PRESENT"
STATUS_ABSENT_UNEXCUSED = "ABSENT_UNEXCUSED"
STATUS_ABSENT_EXCUSED = "ABSENT_EXCUSED"
STATUS_MANUAL_CONFIRM = "MANUAL_CONFIRM"
STATUS_LATE = "LATE"


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
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 1..6 (Пн..Сб)
    week_type: Mapped[str] = mapped_column(String(10), nullable=False, default="ALL")  # ODD, EVEN, ALL
    pair_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1..6
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

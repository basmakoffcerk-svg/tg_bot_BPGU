import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class SubjectTypeEnum(str, enum.Enum):
    LECTURE = "LECTURE"
    PRACTICE = "PRACTICE"
    LAB = "LAB"


class WeekTypeEnum(str, enum.Enum):
    ODD = "ODD"
    EVEN = "EVEN"
    ALL = "ALL"


class Subject(Base):
    __tablename__ = "subjects"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    teacher_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    subject_type: Mapped[str] = mapped_column(String(20), nullable=False, default=SubjectTypeEnum.LECTURE.value)

    # Relationships
    slots = relationship("ScheduleSlot", back_populates="subject", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Subject id={self.id} title='{self.title}' type='{self.subject_type}'>"


class ScheduleSlot(Base):
    __tablename__ = "schedule_slots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 (Mon) .. 6 (Sat)
    week_type: Mapped[str] = mapped_column(String(10), nullable=False, default=WeekTypeEnum.ALL.value)
    pair_number: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 .. 6
    time_start: Mapped[str] = mapped_column(String(5), nullable=False)  # "08:30"
    time_end: Mapped[str] = mapped_column(String(5), nullable=False)  # "10:00"
    subject_id: Mapped[int] = mapped_column(Integer, ForeignKey("subjects.id", ondelete="CASCADE"), nullable=False)
    subgroup: Mapped[int] = mapped_column(Integer, nullable=False, default=0)  # 0 = all, 1 = 1st, 2 = 2nd
    building_name: Mapped[str] = mapped_column(String(100), nullable=False)
    room_number: Mapped[str] = mapped_column(String(20), nullable=False)
    building_lat: Mapped[float] = mapped_column(Float, nullable=False)
    building_lon: Mapped[float] = mapped_column(Float, nullable=False)
    radius_meters: Mapped[int] = mapped_column(Integer, nullable=False, default=150)

    # Relationships
    subject = relationship("Subject", back_populates="slots")
    pairs = relationship("PairsRegistry", back_populates="slot", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<ScheduleSlot id={self.id} day={self.day_of_week} pair={self.pair_number} subg={self.subgroup}>"


class PairsRegistry(Base):
    __tablename__ = "pairs_registry"
    __table_args__ = (UniqueConstraint("slot_id", "calendar_date", name="uq_slot_date"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    slot_id: Mapped[int] = mapped_column(Integer, ForeignKey("schedule_slots.id", ondelete="RESTRICT"), nullable=False)
    calendar_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    is_locked: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    locked_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    locked_by_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("students.id"), nullable=True)

    # Relationships
    slot = relationship("ScheduleSlot", back_populates="pairs")
    locked_by = relationship("Student", foreign_keys=[locked_by_id])
    attendances = relationship("Attendance", back_populates="pair", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<PairsRegistry id={self.id} slot_id={self.slot_id} date={self.calendar_date} locked={self.is_locked}>"

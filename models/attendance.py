import enum
from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class AttendanceStatusEnum(str, enum.Enum):
    PRESENT = "PRESENT"
    ABSENT_UNEXCUSED = "ABSENT_UNEXCUSED"
    ABSENT_EXCUSED = "ABSENT_EXCUSED"
    MANUAL_CONFIRM = "MANUAL_CONFIRM"
    LATE = "LATE"


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint("pair_id", "student_id", name="uq_pair_student"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pair_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("pairs_registry.id", ondelete="CASCADE"), nullable=False, index=True
    )
    student_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("students.id", ondelete="CASCADE"), nullable=False, index=True
    )
    status: Mapped[str] = mapped_column(String(25), nullable=False, default=AttendanceStatusEnum.ABSENT_UNEXCUSED.value)
    checkin_time: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    client_lat: Mapped[float | None] = mapped_column(Float, nullable=True)
    client_lon: Mapped[float | None] = mapped_column(Float, nullable=True)
    distance_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    accuracy_meters: Mapped[float | None] = mapped_column(Float, nullable=True)
    verified_by_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    excuse_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    pair = relationship("PairsRegistry", back_populates="attendances")
    student = relationship("Student", back_populates="attendances")

    def __repr__(self) -> str:
        return f"<Attendance id={self.id} pair_id={self.pair_id} student_id={self.student_id} status='{self.status}'>"

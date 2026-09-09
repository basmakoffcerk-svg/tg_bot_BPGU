import enum
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class RoleEnum(str, enum.Enum):
    STUDENT = "STUDENT"
    ZAM = "ZAM"
    STAROSTA = "STAROSTA"


class StudentStatusEnum(str, enum.Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    BLOCKED = "BLOCKED"


class Student(Base):
    __tablename__ = "students"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    telegram_id: Mapped[int | None] = mapped_column(BigInteger, unique=True, nullable=True, index=True)
    full_name: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    subgroup: Mapped[int] = mapped_column(Integer, nullable=False)  # 1 or 2
    role: Mapped[str] = mapped_column(String(20), nullable=False, default=RoleEnum.STUDENT.value)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default=StudentStatusEnum.PENDING.value)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=func.now(), onupdate=func.now())

    # Relationships
    attendances = relationship("Attendance", back_populates="student", cascade="all, delete-orphan")
    audit_actions = relationship("AuditLog", back_populates="admin", foreign_keys="AuditLog.admin_id")
    broadcasts = relationship("BroadcastMessage", back_populates="sender")

    def __repr__(self) -> str:
        return f"<Student id={self.id} name='{self.full_name}' role='{self.role}' status='{self.status}'>"

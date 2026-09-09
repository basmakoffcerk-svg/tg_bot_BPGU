import enum
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from models.base import Base


class BroadcastTypeEnum(str, enum.Enum):
    CRITICAL = "CRITICAL"
    INFO = "INFO"


class BroadcastMessage(Base):
    __tablename__ = "broadcast_messages"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    sender_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.id"), nullable=False)
    message_type: Mapped[str] = mapped_column(String(20), nullable=False, default=BroadcastTypeEnum.INFO.value)
    title: Mapped[str] = mapped_column(String(150), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    total_recipients: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    read_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    sent_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # Relationships
    sender = relationship("Student", back_populates="broadcasts")


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    admin_id: Mapped[int] = mapped_column(Integer, ForeignKey("students.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    target_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=func.now())

    # Relationships
    admin = relationship("Student", foreign_keys=[admin_id], back_populates="audit_actions")

    def __repr__(self) -> str:
        return f"<AuditLog id={self.id} admin_id={self.admin_id} action='{self.action}'>"

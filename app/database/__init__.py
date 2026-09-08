"""
Database package for АРМ Старосты.
Provides SQLAlchemy async models, WAL-configured connection engine, and initial seeders.
"""

from app.database.connection import AsyncSessionLocal, engine, get_session, init_db
from app.database.models import (
    Attendance,
    AuditLog,
    Base,
    BroadcastMessage,
    PairsRegistry,
    PairRegistry,
    ScheduleSlot,
    Student,
    Subject,
    UserRole,
    StudentStatus,
    SubjectType,
    WeekType,
    AttendanceStatus,
    MessageType,
    AuditAction,
    RoleEnum,
    StatusEnum,
    WeekTypeEnum,
)

__all__ = [
    "Base",
    "engine",
    "AsyncSessionLocal",
    "get_session",
    "init_db",
    "Student",
    "Subject",
    "ScheduleSlot",
    "PairsRegistry",
    "PairRegistry",
    "Attendance",
    "BroadcastMessage",
    "AuditLog",
    "UserRole",
    "StudentStatus",
    "SubjectType",
    "WeekType",
    "AttendanceStatus",
    "MessageType",
    "AuditAction",
    "RoleEnum",
    "StatusEnum",
    "WeekTypeEnum",
]

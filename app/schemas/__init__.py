"""
Centralized re-export of all Pydantic v2 schemas.
"""
from app.schemas.base import BaseSchema
from app.schemas.error import ProblemDetail
from app.schemas.health import HealthCheckResponse
from app.schemas.auth import (
    UserProfile,
    PermissionsInfo,
    CurrentWeekInfo,
    TelegramAuthResponse,
)
from app.schemas.schedule import (
    BuildingCoordinates,
    CheckinStatusInfo,
    AttendanceStatus,
    PairItem,
    ScheduleTodayResponse,
)
from app.schemas.attendance import (
    CheckinRequest,
    CheckinResponse,
    StudentGridItem,
    GridSummary,
    GridResponse,
    OverrideRequest,
    OverrideResponse,
    LockPairResponse,
)
from app.schemas.alerts import BroadcastRequest, BroadcastResponse
from app.schemas.reports import ReportExportRequest, ReportExportResponse

__all__ = [
    "BaseSchema",
    "ProblemDetail",
    "HealthCheckResponse",
    "UserProfile",
    "PermissionsInfo",
    "CurrentWeekInfo",
    "TelegramAuthResponse",
    "BuildingCoordinates",
    "CheckinStatusInfo",
    "AttendanceStatus",
    "PairItem",
    "ScheduleTodayResponse",
    "CheckinRequest",
    "CheckinResponse",
    "StudentGridItem",
    "GridSummary",
    "GridResponse",
    "OverrideRequest",
    "OverrideResponse",
    "LockPairResponse",
    "BroadcastRequest",
    "BroadcastResponse",
    "ReportExportRequest",
    "ReportExportResponse",
]

"""
Core application services: Security, Geolocation, Time Utilities, and Exceptions.
"""

from app.core.exceptions import ProblemException, ProblemType, setup_exception_handlers
from app.core.geo import (
    EARTH_RADIUS_METERS,
    GeoVerificationResult,
    haversine_distance,
    validate_gps_accuracy,
    validate_sensor_timestamp,
    verify_geocheckin,
)
from app.core.security import (
    InitDataPayload,
    TelegramUser,
    get_current_active_student,
    get_current_telegram_user,
    get_current_user,
    get_validated_init_data,
    mock_init_data,
    require_roles,
    require_starosta,
    require_zam_or_starosta,
    validate_telegram_init_data,
)
from app.core.time_utils import (
    AcademicWeekInfo,
    CheckinWindowStatus,
    WeekTypeEnum,
    calculate_checkin_window,
    checkin_window_active,
    get_academic_week,
    get_current_week_info,
    is_checkin_window_open,
)

__all__ = [
    "ProblemException",
    "ProblemType",
    "setup_exception_handlers",
    "EARTH_RADIUS_METERS",
    "GeoVerificationResult",
    "haversine_distance",
    "validate_gps_accuracy",
    "validate_sensor_timestamp",
    "verify_geocheckin",
    "TelegramUser",
    "InitDataPayload",
    "mock_init_data",
    "validate_telegram_init_data",
    "get_validated_init_data",
    "get_current_telegram_user",
    "get_current_user",
    "get_current_active_student",
    "require_roles",
    "require_zam_or_starosta",
    "require_starosta",
    "WeekTypeEnum",
    "AcademicWeekInfo",
    "CheckinWindowStatus",
    "get_academic_week",
    "get_current_week_info",
    "checkin_window_active",
    "calculate_checkin_window",
    "is_checkin_window_open",
]

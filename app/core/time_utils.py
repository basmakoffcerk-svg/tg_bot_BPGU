"""
Academic calendar timetable, week parity (ODD/EVEN), and pair check-in window calculations.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from enum import Enum
from typing import Optional, Tuple
from zoneinfo import ZoneInfo
from pydantic import BaseModel, Field

from app.config import settings

# Canonical semester start reference date
DEFAULT_SEMESTER_START: date = date(2026, 9, 1)
DEFAULT_TIMEZONE_NAME: str = "Europe/Moscow"


class WeekTypeEnum(str, Enum):
    """Academic week parity type."""
    ODD = "ODD"    # Числитель
    EVEN = "EVEN"  # Знаменатель
    ALL = "ALL"    # Каждая неделя


class AcademicWeekInfo(BaseModel):
    """Academic week information structure."""
    week_number: int
    week_type: WeekTypeEnum
    is_study_day: bool


class CheckinWindowStatus(BaseModel):
    """Check-in window status."""
    is_active: bool = Field(..., description="Whether student can currently check in")
    window_start: str = Field(..., description="Window open time (HH:MM)")
    window_end: str = Field(..., description="Window close time (HH:MM)")
    seconds_remaining: Optional[int] = Field(None, description="Seconds remaining until window closes")
    seconds_until_start: Optional[int] = Field(None, description="Seconds until window opens")
    reason_closed: Optional[str] = Field(None, description="Reason code if window is not active")


def get_academic_timezone(tz_name: str = DEFAULT_TIMEZONE_NAME) -> ZoneInfo:
    """Returns ZoneInfo instance for local university time."""
    return ZoneInfo(tz_name)


def get_now_localized(tz_name: str = DEFAULT_TIMEZONE_NAME) -> datetime:
    """Returns current localized datetime."""
    return datetime.now(get_academic_timezone(tz_name))


def get_academic_week(
    target_date: Optional[date] = None,
    semester_start: date = DEFAULT_SEMESTER_START,
) -> Tuple[int, WeekTypeEnum, bool]:
    """
    Calculates academic week number (1-indexed), parity (ODD/EVEN), and study day status.
    Returns: (week_number, week_type, is_study_day)
    """
    if target_date is None:
        target_date = get_now_localized().date()

    ref_monday = semester_start - timedelta(days=semester_start.weekday())
    target_monday = target_date - timedelta(days=target_date.weekday())

    weeks_diff = (target_monday - ref_monday).days // 7
    week_number = max(1, 1 + weeks_diff)

    week_type = WeekTypeEnum.ODD if (week_number % 2 == 1) else WeekTypeEnum.EVEN

    # Monday=1, ..., Saturday=6, Sunday=7
    day_of_week = target_date.isoweekday()
    is_study_day = 1 <= day_of_week <= 6

    return week_number, week_type, is_study_day


def get_current_week_info(
    target_date: Optional[date] = None,
    semester_start: date = DEFAULT_SEMESTER_START,
) -> AcademicWeekInfo:
    """Returns strongly-typed AcademicWeekInfo."""
    w_num, w_type, is_study = get_academic_week(target_date, semester_start)
    return AcademicWeekInfo(
        week_number=w_num,
        week_type=w_type,
        is_study_day=is_study,
    )


def checkin_window_active(
    pair_time_start: str,
    current_time: datetime,
    before_minutes: int = 5,
    after_minutes: int = 15,
) -> bool:
    """
    Check-in window is open from (time_start - 5 min) to (time_start + 15 min).
    """
    sh, sm = map(int, pair_time_start.split(":"))
    pair_dt = current_time.replace(hour=sh, minute=sm, second=0, microsecond=0)
    window_start = pair_dt - timedelta(minutes=before_minutes)
    window_end = pair_dt + timedelta(minutes=after_minutes)
    return window_start <= current_time <= window_end


def calculate_checkin_window(
    pair_time_start: str,
    current_time: Optional[datetime] = None,
    calendar_date: Optional[date] = None,
    is_locked: bool = False,
    has_checked_in: bool = False,
    before_minutes: int = settings.CHECKIN_WINDOW_BEFORE_MINUTES,
    after_minutes: int = settings.CHECKIN_WINDOW_AFTER_MINUTES,
    tz_name: str = DEFAULT_TIMEZONE_NAME,
) -> CheckinWindowStatus:
    """
    Calculates checkin window boundaries [-before_minutes ... +after_minutes] and current status.
    """
    tz = get_academic_timezone(tz_name)
    now = current_time if current_time is not None else datetime.now(tz)
    if now.tzinfo is None:
        now = now.replace(tzinfo=tz)

    target_date = calendar_date if calendar_date is not None else now.date()
    sh, sm = map(int, pair_time_start.split(":"))
    pair_start_dt = datetime.combine(target_date, time(sh, sm), tzinfo=tz)

    window_open_dt = pair_start_dt - timedelta(minutes=before_minutes)
    window_close_dt = pair_start_dt + timedelta(minutes=after_minutes)

    open_str = window_open_dt.strftime("%H:%M")
    close_str = window_close_dt.strftime("%H:%M")

    # Priority 1: Locked
    if is_locked:
        return CheckinWindowStatus(
            is_active=False,
            window_start=open_str,
            window_end=close_str,
            seconds_remaining=None,
            seconds_until_start=None,
            reason_closed="PAIR_LOCKED",
        )

    # Priority 2: Already checked in
    if has_checked_in:
        return CheckinWindowStatus(
            is_active=False,
            window_start=open_str,
            window_end=close_str,
            seconds_remaining=None,
            seconds_until_start=None,
            reason_closed="ALREADY_CHECKED_IN",
        )

    # Priority 3: Before window open
    if now < window_open_dt:
        seconds_until = int((window_open_dt - now).total_seconds())
        return CheckinWindowStatus(
            is_active=False,
            window_start=open_str,
            window_end=close_str,
            seconds_remaining=None,
            seconds_until_start=seconds_until,
            reason_closed="PAIR_NOT_STARTED",
        )

    # Priority 4: In active window
    if window_open_dt <= now <= window_close_dt:
        seconds_left = max(0, int((window_close_dt - now).total_seconds()))
        return CheckinWindowStatus(
            is_active=True,
            window_start=open_str,
            window_end=close_str,
            seconds_remaining=seconds_left,
            seconds_until_start=None,
            reason_closed=None,
        )

    # Priority 5: Window expired
    return CheckinWindowStatus(
        is_active=False,
        window_start=open_str,
        window_end=close_str,
        seconds_remaining=0,
        seconds_until_start=None,
        reason_closed="TIME_EXPIRED",
    )


def is_checkin_window_open(
    calendar_date: date,
    time_start_str: str,
    current_dt: Optional[datetime] = None,
    before_minutes: int = 5,
    after_minutes: int = 15,
    is_locked: bool = False,
    tz_name: str = DEFAULT_TIMEZONE_NAME,
) -> bool:
    """Boolean check whether attendance check-in window is open."""
    status = calculate_checkin_window(
        pair_time_start=time_start_str,
        current_time=current_dt,
        calendar_date=calendar_date,
        before_minutes=before_minutes,
        after_minutes=after_minutes,
        is_locked=is_locked,
        tz_name=tz_name,
    )
    return status.is_active

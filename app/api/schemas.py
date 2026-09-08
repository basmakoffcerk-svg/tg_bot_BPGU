"""
Pydantic v2 схемы запросов и ответов REST API.
"""
from datetime import date, datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class UserProfileSchema(BaseModel):
    id: int
    telegram_id: Optional[int]
    full_name: str
    subgroup: int
    role: str
    status: str


class CurrentWeekSchema(BaseModel):
    week_number: int
    week_type: str
    is_study_day: bool


class AuthResponseSchema(BaseModel):
    user: UserProfileSchema
    permissions: Dict[str, bool]
    current_week: CurrentWeekSchema


class CoordinatesSchema(BaseModel):
    lat: float
    lon: float


class CheckinStatusSchema(BaseModel):
    is_active: bool
    window_start: str
    window_end: str
    seconds_remaining: Optional[int] = None
    reason_closed: Optional[str] = None


class AttendanceShortSchema(BaseModel):
    status: str
    distance: Optional[float]
    checkin_time: Optional[datetime]


class PairItemSchema(BaseModel):
    pair_id: int
    pair_number: int
    time_start: str
    time_end: str
    subject: str
    teacher: Optional[str]
    type: str
    room: str
    building: str
    building_coordinates: CoordinatesSchema
    checkin_status: CheckinStatusSchema
    my_attendance: Optional[AttendanceShortSchema] = None


class ScheduleTodayResponseSchema(BaseModel):
    date: date
    day_of_week: int
    week_type: str
    pairs: List[PairItemSchema]


class CheckinRequestSchema(BaseModel):
    pair_id: int
    client_lat: float
    client_lon: float
    accuracy: float
    timestamp: Optional[int] = None


class CheckinResponseSchema(BaseModel):
    status: str
    pair_id: int
    distance_meters: float
    checkin_time: datetime
    message: str


class GridStudentSchema(BaseModel):
    student_id: int
    full_name: str
    subgroup: int
    status: str
    badge_color: str
    distance: Optional[float] = None
    checkin_time: Optional[str] = None
    verified_by_admin: bool = False
    excuse_reason: Optional[str] = None
    note: Optional[str] = None


class AttendanceGridResponseSchema(BaseModel):
    pair_id: int
    subject: str
    is_locked: bool
    summary: Dict[str, int]
    students: List[GridStudentSchema]


class OverrideRequestSchema(BaseModel):
    pair_id: int
    student_id: int
    new_status: str
    excuse_reason: Optional[str] = None


class OverrideResponseSchema(BaseModel):
    success: bool
    pair_id: int
    student_id: int
    status: str
    updated_at: datetime


class LockPairResponseSchema(BaseModel):
    success: bool
    pair_id: int
    is_locked: bool
    locked_at: datetime


class BroadcastRequestSchema(BaseModel):
    type: str = Field(default="INFO", pattern="^(CRITICAL|INFO)$")
    title: str
    body: str


class BroadcastResponseSchema(BaseModel):
    broadcast_id: int
    queued_recipients: int
    channel_posted: bool
    status: str


class ExportReportRequestSchema(BaseModel):
    date_from: date
    date_to: date
    delivery_method: str = "TELEGRAM_DM"


class ExportReportResponseSchema(BaseModel):
    file_name: str
    delivered_to_telegram: bool
    total_pairs: int
    total_absent_hours: int

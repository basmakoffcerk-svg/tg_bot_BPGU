"""
Geolocation check-in, attendance matrix grid, status override, and pair locking schemas.
"""
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field
from app.schemas.base import BaseSchema


class CheckinRequest(BaseModel):
    """Payload for POST /api/v1/attendance/checkin."""
    pair_id: int = Field(..., gt=0, description="Target pair registry ID")
    client_lat: float = Field(..., ge=-90.0, le=90.0, description="Device GPS latitude")
    client_lon: float = Field(..., ge=-180.0, le=180.0, description="Device GPS longitude")
    accuracy: float = Field(..., gt=0.0, description="Horizontal GPS accuracy radius in meters (<= 50.0m)")
    timestamp: float = Field(..., description="Client epoch seconds when coordinates were sampled")


class CheckinResponse(BaseModel):
    """Response returned upon successful check-in."""
    status: str = Field(default="PRESENT", description="Assigned attendance status")
    pair_id: int = Field(..., description="Pair registry ID")
    distance_meters: float = Field(..., description="Calculated Haversine distance in meters")
    checkin_time: datetime = Field(..., description="Server timestamp of accepted check-in")
    message: str = Field(default="Присутствие успешно подтверждено!", description="User-facing success notice")


class StudentGridItem(BaseSchema):
    """Individual student row in the starosta chessboard grid."""
    student_id: int = Field(..., description="Student database identifier")
    full_name: str = Field(..., description="Student full name")
    subgroup: int = Field(..., description="Student academic subgroup (1 or 2)")
    status: str = Field(..., description="Attendance status code")
    badge_color: str = Field(default="grey", description="UI badge color for the chessboard (green, grey, yellow, blue, purple)")
    distance: Optional[float] = Field(None, description="Check-in distance in meters")
    checkin_time: Optional[str] = Field(None, description="Check-in time (HH:MM:SS format)")
    verified_by_admin: bool = Field(default=False, description="True if status was modified by starosta/zam")
    excuse_reason: Optional[str] = Field(None, description="Documented excuse reason if ABSENT_EXCUSED")
    note: Optional[str] = Field(None, description="Administrative note or comment")


class GridSummary(BaseModel):
    """Statistical summary for the attendance grid."""
    total_students: int = Field(..., description="Total student count in view")
    present_count: int = Field(..., description="Count of PRESENT students")
    absent_unexcused_count: int = Field(..., description="Count of ABSENT_UNEXCUSED students ('Н')")
    absent_excused_count: int = Field(..., description="Count of ABSENT_EXCUSED students ('У')")
    manual_confirmed_count: int = Field(..., description="Count of MANUAL_CONFIRM students")
    late_count: int = Field(default=0, description="Count of LATE students ('О')")


class GridResponse(BaseModel):
    """Response returned by GET /api/v1/attendance/grid/{pair_id}."""
    pair_id: int = Field(..., description="Pair registry ID")
    subject: str = Field(..., description="Academic discipline title")
    is_locked: bool = Field(..., description="True if the pair attendance journal is locked")
    summary: GridSummary
    students: List[StudentGridItem] = Field(default_factory=list)


class OverrideRequest(BaseModel):
    """Payload for PATCH /api/v1/attendance/override."""
    pair_id: int = Field(..., gt=0, description="Target pair registry ID")
    student_id: int = Field(..., gt=0, description="Target student ID")
    new_status: str = Field(..., description="New status to set")
    excuse_reason: Optional[str] = Field(None, max_length=500, description="Required explanation for excused status")


class OverrideResponse(BaseModel):
    """Response returned by PATCH /api/v1/attendance/override."""
    success: bool = Field(default=True)
    pair_id: int
    student_id: int
    status: str
    updated_at: datetime


class LockPairResponse(BaseModel):
    """Response returned by POST /api/v1/attendance/lock/{pair_id}."""
    success: bool = Field(default=True)
    pair_id: int
    is_locked: bool = Field(default=True)
    locked_at: datetime

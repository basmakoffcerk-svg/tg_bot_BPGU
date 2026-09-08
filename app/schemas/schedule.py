"""
Daily schedule, classroom coordinates, and pair item schemas.
"""
import datetime as dt
from typing import List, Literal, Optional
from pydantic import BaseModel, Field
from app.schemas.base import BaseSchema


class BuildingCoordinates(BaseModel):
    """Geographical reference coordinates for a university building / room."""
    lat: float = Field(..., ge=-90.0, le=90.0, description="Latitude in decimal degrees")
    lon: float = Field(..., ge=-180.0, le=180.0, description="Longitude in decimal degrees")


class CheckinStatusInfo(BaseModel):
    """Real-time availability of the GPS check-in window."""
    is_active: bool = Field(..., description="True if the pair is currently open for check-in")
    window_start: str = Field(..., description="Opening time in HH:MM format (-5 min from start)")
    window_end: str = Field(..., description="Closing time in HH:MM format (+15 min from start)")
    seconds_remaining: Optional[int] = Field(None, description="Seconds remaining before window closes")
    seconds_until_start: Optional[int] = Field(None, description="Seconds until window opens")
    reason_closed: Optional[str] = Field(
        None, description="Reason code when is_active is False"
    )


class AttendanceStatus(BaseSchema):
    """Personal check-in record for the authenticated student."""
    status: str = Field(
        ..., description="Current attendance status code"
    )
    distance: Optional[float] = Field(None, description="Recorded distance in meters from building center")
    checkin_time: Optional[dt.datetime] = Field(None, description="Timestamp when check-in was registered")


class PairItem(BaseModel):
    """Item representing a scheduled pair for today."""
    pair_id: int = Field(..., description="Unique ID from pairs_registry table")
    pair_number: int = Field(..., ge=1, le=6, description="Bell schedule slot number (1..6)")
    time_start: str = Field(..., description="Pair start time in HH:MM format (e.g. '08:30')")
    time_end: str = Field(..., description="Pair end time in HH:MM format (e.g. '10:00')")
    subject: str = Field(..., description="Academic discipline title")
    teacher: Optional[str] = Field(None, description="Instructor name")
    type: str = Field(default="LECTURE", description="Class type (LECTURE, PRACTICE, LAB)")
    room: str = Field(..., description="Classroom number (e.g. '304', '212-Б')")
    building: str = Field(..., description="Building name (e.g. 'Главный корпус')")
    building_coordinates: BuildingCoordinates
    checkin_status: CheckinStatusInfo
    my_attendance: Optional[AttendanceStatus] = Field(None, description="User's attendance record, if any")


class ScheduleTodayResponse(BaseModel):
    """Response returned by GET /api/v1/schedule/today."""
    date: dt.date = Field(..., description="Current calendar date (YYYY-MM-DD)")
    day_of_week: int = Field(..., ge=1, le=7, description="ISO weekday (1=Monday .. 7=Sunday)")
    week_type: str = Field(..., description="Current week parity (ODD/EVEN)")
    pairs: List[PairItem] = Field(default_factory=list, description="List of pairs for student's subgroup")

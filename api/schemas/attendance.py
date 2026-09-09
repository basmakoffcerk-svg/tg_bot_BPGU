from pydantic import BaseModel, Field


class CheckinRequest(BaseModel):
    pair_id: int
    client_lat: float
    client_lon: float
    accuracy: float = Field(..., description="GPS accuracy in meters")
    timestamp: float | None = None


class CheckinResponse(BaseModel):
    status: str
    pair_id: int
    distance_meters: float
    checkin_time: str
    message: str


class GridStudentItemSchema(BaseModel):
    student_id: int
    full_name: str
    subgroup: int
    status: str
    badge_color: str
    distance: float | None = None
    checkin_time: str | None = None
    verified_by_admin: bool = False
    excuse_reason: str | None = None


class GridSummarySchema(BaseModel):
    total_students: int
    present_count: int
    absent_unexcused_count: int
    absent_excused_count: int
    manual_confirmed_count: int
    late_count: int


class PairGridResponse(BaseModel):
    pair_id: int
    subject: str
    room: str
    building: str
    pair_number: int
    time_start: str
    time_end: str
    is_locked: bool
    locked_at: str | None = None
    summary: GridSummarySchema
    students: list[GridStudentItemSchema]


class OverrideStatusRequest(BaseModel):
    pair_id: int
    student_id: int
    new_status: str
    excuse_reason: str | None = None


class OverrideStatusResponse(BaseModel):
    success: bool
    pair_id: int
    student_id: int
    status: str
    updated_at: str


class LockPairResponse(BaseModel):
    success: bool
    pair_id: int
    is_locked: bool
    locked_at: str

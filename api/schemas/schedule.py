from pydantic import BaseModel


class BuildingCoordinatesSchema(BaseModel):
    lat: float
    lon: float


class CheckinWindowStatusSchema(BaseModel):
    is_active: bool
    window_start: str
    window_end: str
    seconds_remaining: int | None = None
    reason_closed: str | None = None


class StudentAttendanceSummarySchema(BaseModel):
    status: str
    distance: float | None = None
    checkin_time: str | None = None


class PairItemSchema(BaseModel):
    pair_id: int
    pair_number: int
    time_start: str
    time_end: str
    subject: str
    teacher: str | None = None
    type: str
    room: str
    building: str
    building_coordinates: BuildingCoordinatesSchema
    checkin_status: CheckinWindowStatusSchema
    my_attendance: StudentAttendanceSummarySchema | None = None


class DailyScheduleResponse(BaseModel):
    date: str
    day_of_week: int
    week_type: str
    pairs: list[PairItemSchema]

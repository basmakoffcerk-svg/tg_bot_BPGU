from pydantic import BaseModel, ConfigDict


class UserProfileSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    telegram_id: int | None
    full_name: str
    subgroup: int
    role: str
    status: str


class PermissionsSchema(BaseModel):
    can_view_grid: bool
    can_override_status: bool
    can_lock_pairs: bool
    can_broadcast_critical: bool
    can_export_reports: bool


class CurrentWeekSchema(BaseModel):
    week_number: int
    week_type: str
    is_study_day: bool


class AuthResponse(BaseModel):
    user: UserProfileSchema | None
    permissions: PermissionsSchema
    current_week: CurrentWeekSchema

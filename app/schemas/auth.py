"""
Authentication, profile, permissions, and academic week schemas.
"""
from typing import Literal, Optional
from pydantic import BaseModel, Field
from app.schemas.base import BaseSchema


class UserProfile(BaseSchema):
    """Authenticated student profile returned to Telegram Mini App."""
    id: int = Field(..., description="Student database identifier")
    telegram_id: Optional[int] = Field(None, description="Telegram User ID")
    full_name: str = Field(..., description="Full name according to dean's roster")
    subgroup: int = Field(..., ge=1, le=2, description="Academic subgroup (1 or 2)")
    role: str = Field(..., description="RBAC authorization role (STUDENT, ZAM, STAROSTA)")
    status: str = Field(..., description="Account lifecycle status (PENDING, ACTIVE, BLOCKED)")


class PermissionsInfo(BaseModel):
    """Action permission flags for UI rendering and feature gating."""
    can_view_grid: bool = Field(..., description="Permission to view class attendance grid")
    can_override_status: bool = Field(..., description="Permission to manually override student status")
    can_lock_pairs: bool = Field(..., description="Permission to permanently lock attendance for a pair")
    can_broadcast_critical: bool = Field(..., description="Permission to send emergency broadcasts")
    can_export_reports: bool = Field(..., description="Permission to trigger official Excel report exports")


class CurrentWeekInfo(BaseModel):
    """Academic calendar week metadata."""
    week_number: int = Field(..., ge=1, le=25, description="Semester week number (1..N)")
    week_type: Literal["ODD", "EVEN"] = Field(..., description="Week parity (ODD=Числитель, EVEN=Знаменатель)")
    is_study_day: bool = Field(..., description="True if today is a scheduled study day (Mon..Sat)")


class TelegramAuthResponse(BaseModel):
    """Response returned by POST /api/v1/auth/telegram."""
    user: UserProfile
    permissions: PermissionsInfo
    current_week: CurrentWeekInfo

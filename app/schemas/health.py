"""
Healthcheck and telemetry schemas.
"""
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class HealthCheckResponse(BaseModel):
    """Response returned by GET /api/v1/health."""
    status: str = Field(default="ok", description="Application service status")
    database: str = Field(default="connected", description="Database connectivity status")
    timestamp: datetime = Field(..., description="Current server UTC timestamp")
    version: str = Field(default="1.0.0", description="Application version")
    bot: Optional[str] = Field(default="online", description="Telegram bot configuration status")

"""
Official Excel report export request and response schemas.
"""
from datetime import date
from typing import Optional
from pydantic import BaseModel, Field, model_validator


class ReportExportRequest(BaseModel):
    """Payload for POST /api/v1/reports/export."""
    date_from: date = Field(..., description="Start date of reporting period")
    date_to: date = Field(..., description="End date of reporting period")
    delivery_method: str = Field(
        default="TELEGRAM_DM", description="Delivery channel for generated spreadsheet"
    )

    @model_validator(mode="after")
    def validate_date_range(self) -> "ReportExportRequest":
        if self.date_from > self.date_to:
            raise ValueError("Параметр date_from не может быть позже date_to.")
        return self


class ReportExportResponse(BaseModel):
    """Response returned by POST /api/v1/reports/export."""
    file_name: str = Field(..., description="Generated .xlsx file name")
    delivered_to_telegram: bool = Field(..., description="Whether file was delivered to requester's Telegram")
    total_pairs: int = Field(..., description="Number of pairs evaluated in period")
    total_absent_hours: int = Field(..., description="Total absent hours accumulated across group")
    download_url: Optional[str] = Field(None, description="Direct download link if delivery_method is DOWNLOAD")

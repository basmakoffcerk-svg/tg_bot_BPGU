from pydantic import BaseModel


class ExportReportRequest(BaseModel):
    date_from: str  # YYYY-MM-DD
    date_to: str  # YYYY-MM-DD
    delivery_method: str = "TELEGRAM_DM"  # or DIRECT_DOWNLOAD


class ExportReportResponse(BaseModel):
    file_name: str
    delivered_to_telegram: bool
    total_pairs: int
    total_absent_hours: int
    download_url: str | None = None

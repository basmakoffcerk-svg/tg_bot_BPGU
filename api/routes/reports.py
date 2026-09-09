import datetime
from urllib.parse import quote

from aiogram.types import BufferedInputFile
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import require_roles
from api.schemas.reports import ExportReportRequest, ExportReportResponse
from core.database import get_db
from models import RoleEnum, Student
from services.broadcaster import broadcaster_service
from services.excel_generator import generate_attendance_excel

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.post("/export", response_model=ExportReportResponse)
async def export_attendance_report(
    payload: ExportReportRequest,
    current_user: Student = Depends(require_roles(RoleEnum.STAROSTA, RoleEnum.ZAM)),
    db: AsyncSession = Depends(get_db),
):
    """
    Exports official attendance report (.xlsx) and delivers it to Starosta in Telegram DM.
    """
    try:
        date_from = datetime.datetime.strptime(payload.date_from, "%Y-%m-%d").date()
        date_to = datetime.datetime.strptime(payload.date_to, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"title": "Неверный формат даты", "detail": "Даты должны быть в формате YYYY-MM-DD."},
        )

    if date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"title": "Неверный диапазон дат", "detail": "Начальная дата не может быть позже конечной."},
        )
    if (date_to - date_from).days > 366:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"title": "Слишком широкий диапазон", "detail": "Диапазон дат не может превышать 1 год."},
        )

    excel_buf, filename, total_pairs, total_absent_hours = await generate_attendance_excel(
        session=db, date_from=date_from, date_to=date_to
    )

    delivered = False
    if payload.delivery_method == "TELEGRAM_DM" and current_user.telegram_id and broadcaster_service.bot:
        try:
            caption = (
                f"📊 <b>Рапортичка группы 240326</b>\n"
                f"Период: {date_from.strftime('%d.%m.%Y')} — {date_to.strftime('%d.%m.%Y')}\n"
                f"Всего пар: {total_pairs}\n"
                f"Суммарно пропущено часов: {total_absent_hours} ч."
            )
            input_file = BufferedInputFile(excel_buf.getvalue(), filename=filename)
            await broadcaster_service.bot.send_document(
                chat_id=current_user.telegram_id, document=input_file, caption=caption, parse_mode="HTML"
            )
            delivered = True
        except Exception:
            delivered = False

    return ExportReportResponse(
        file_name=filename,
        delivered_to_telegram=delivered,
        total_pairs=total_pairs,
        total_absent_hours=total_absent_hours,
    )


@router.get("/download")
async def download_attendance_report(
    date_from: str,
    date_to: str,
    current_user: Student = Depends(require_roles(RoleEnum.STAROSTA, RoleEnum.ZAM)),
    db: AsyncSession = Depends(get_db),
):
    """Direct HTTP stream download of the Excel report."""
    try:
        d_from = datetime.datetime.strptime(date_from, "%Y-%m-%d").date()
        d_to = datetime.datetime.strptime(date_to, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")

    if d_from > d_to:
        raise HTTPException(status_code=400, detail="date_from cannot be greater than date_to")
    if (d_to - d_from).days > 366:
        raise HTTPException(status_code=400, detail="Date range cannot exceed 1 year")

    excel_buf, filename, _, _ = await generate_attendance_excel(db, d_from, d_to)

    return StreamingResponse(
        excel_buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"},
    )

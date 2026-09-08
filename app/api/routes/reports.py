"""
Маршруты генерации и экспорта рапортичек посещаемости.
"""
from datetime import date
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import require_roles
from app.api.schemas import ExportReportRequestSchema, ExportReportResponseSchema
from app.core.database import get_db_session
from app.models import Attendance, PairRegistry, ScheduleSlot, Student, ROLE_STAROSTA, ROLE_ZAM
from app.services.excel_generator import generate_dean_report_xlsx

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.post("/export", response_model=ExportReportResponseSchema)
async def export_report(
    payload: ExportReportRequestSchema,
    current_user: Student = Depends(require_roles([ROLE_STAROSTA, ROLE_ZAM])),
    db: AsyncSession = Depends(get_db_session),
):
    """Триггер формирования рапортички в Excel за выбранный период."""
    # Получаем студентов
    st_stmt = select(Student).where(Student.status == "ACTIVE").order_by(Student.full_name)
    st_res = await db.execute(st_stmt)
    students = [{"id": s.id, "full_name": s.full_name, "subgroup": s.subgroup} for s in st_res.scalars().all()]

    # Получаем пары за период
    pairs_stmt = (
        select(PairRegistry)
        .options(selectinload(PairRegistry.slot).selectinload(ScheduleSlot.subject))
        .where(
            PairRegistry.calendar_date >= payload.date_from,
            PairRegistry.calendar_date <= payload.date_to,
        )
        .order_by(PairRegistry.calendar_date, PairRegistry.slot_id)
    )
    pairs_res = await db.execute(pairs_stmt)
    pairs = pairs_res.scalars().all()

    dates_and_pairs = []
    seen = set()
    for p in pairs:
        key = (p.calendar_date, p.slot.pair_number)
        if key not in seen:
            seen.add(key)
            dates_and_pairs.append((p.calendar_date, p.slot.pair_number, p.slot.subject.title))

    # Подсчет часов
    att_stmt = select(Attendance).join(PairRegistry).where(
        PairRegistry.calendar_date >= payload.date_from,
        PairRegistry.calendar_date <= payload.date_to,
    )
    att_res = await db.execute(att_stmt)
    attendances = att_res.scalars().all()
    
    total_absent_pairs = sum(1 for a in attendances if a.status in ("ABSENT_UNEXCUSED", "ABSENT_EXCUSED"))
    total_absent_hours = total_absent_pairs * 2

    file_name = f"Рапортичка_240326_{payload.date_from.strftime('%d.%m')}-{payload.date_to.strftime('%d.%m')}.xlsx"

    return ExportReportResponseSchema(
        file_name=file_name,
        delivered_to_telegram=True,
        total_pairs=len(dates_and_pairs),
        total_absent_hours=total_absent_hours,
    )


@router.get("/download")
async def download_report(
    date_from: date,
    date_to: date,
    current_user: Student = Depends(require_roles([ROLE_STAROSTA, ROLE_ZAM])),
    db: AsyncSession = Depends(get_db_session),
):
    """Прямое скачивание бинарного файла Excel (.xlsx) через браузер."""
    st_stmt = select(Student).where(Student.status == "ACTIVE").order_by(Student.full_name)
    st_res = await db.execute(st_stmt)
    students = [{"id": s.id, "full_name": s.full_name, "subgroup": s.subgroup} for s in st_res.scalars().all()]

    pairs_stmt = (
        select(PairRegistry)
        .options(selectinload(PairRegistry.slot).selectinload(ScheduleSlot.subject))
        .where(
            PairRegistry.calendar_date >= date_from,
            PairRegistry.calendar_date <= date_to,
        )
        .order_by(PairRegistry.calendar_date, PairRegistry.slot_id)
    )
    pairs_res = await db.execute(pairs_stmt)
    pairs = pairs_res.scalars().all()

    dates_and_pairs = []
    seen = set()
    pair_id_to_meta = {}
    for p in pairs:
        pair_id_to_meta[p.id] = (p.calendar_date, p.slot.pair_number)
        key = (p.calendar_date, p.slot.pair_number)
        if key not in seen:
            seen.add(key)
            dates_and_pairs.append((p.calendar_date, p.slot.pair_number, p.slot.subject.title))

    att_stmt = select(Attendance).join(PairRegistry).where(
        PairRegistry.calendar_date >= date_from,
        PairRegistry.calendar_date <= date_to,
    )
    att_res = await db.execute(att_stmt)
    
    matrix = {}
    for a in att_res.scalars().all():
        if a.pair_id in pair_id_to_meta:
            c_date, p_num = pair_id_to_meta[a.pair_id]
            matrix[(a.student_id, c_date, p_num)] = a.status

    xlsx_bytes = generate_dean_report_xlsx(
        group_name="240326 Матинф",
        university_name="БГПУ им. М. Танка",
        date_from=date_from,
        date_to=date_to,
        students=students,
        dates_and_pairs=dates_and_pairs,
        attendance_matrix=matrix,
    )

    filename = f"Raportichka_240326_{date_from.strftime('%d%m')}_{date_to.strftime('%d%m')}.xlsx"
    return Response(
        content=xlsx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

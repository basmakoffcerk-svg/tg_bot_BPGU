"""
Маршруты учебного расписания.
"""
from datetime import date, datetime, timedelta
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_current_user
from app.api.schemas import (
    AttendanceShortSchema,
    CheckinStatusSchema,
    CoordinatesSchema,
    PairItemSchema,
    ScheduleTodayResponseSchema,
)
from app.core.config import settings
from app.core.database import get_db_session
from app.models import Attendance, PairRegistry, ScheduleSlot, Student

router = APIRouter(prefix="/schedule", tags=["Schedule"])


@router.get("/today", response_model=ScheduleTodayResponseSchema)
async def get_schedule_today(
    current_user: Student = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Возвращает карточки расписания на текущий день с таймерами окон чекина."""
    today = date.today()
    dow = today.isocalendar()[2]  # 1..7 (Пн..Вс)
    week_num = today.isocalendar()[1]
    current_week_type = "ODD" if week_num % 2 != 0 else "EVEN"

    # Загружаем слоты расписания для подгруппы студента (или всей группы subgroup=0)
    stmt = (
        select(ScheduleSlot)
        .options(selectinload(ScheduleSlot.subject))
        .where(
            ScheduleSlot.day_of_week == dow,
            ScheduleSlot.week_type.in_([current_week_type, "ALL"]),
            ScheduleSlot.subgroup.in_([0, current_user.subgroup]),
        )
        .order_by(ScheduleSlot.pair_number)
    )
    res = await db.execute(stmt)
    slots = res.scalars().all()

    pairs_output: List[PairItemSchema] = []
    now_dt = datetime.now()

    for slot in slots:
        # Ищем или создаем запись пары в календаре
        pair_stmt = select(PairRegistry).where(
            PairRegistry.slot_id == slot.id,
            PairRegistry.calendar_date == today,
        )
        pair_res = await db.execute(pair_stmt)
        pair_record = pair_res.scalar_one_or_none()

        if not pair_record:
            pair_record = PairRegistry(slot_id=slot.id, calendar_date=today)
            db.add(pair_record)
            await db.commit()
            await db.refresh(pair_record)

        # Вычисляем окно чекина
        sh, sm = map(int, slot.time_start.split(":"))
        start_time = datetime.combine(today, datetime.min.time()).replace(hour=sh, minute=sm)
        window_start = start_time - timedelta(minutes=settings.CHECKIN_WINDOW_BEFORE_MINUTES)
        window_end = start_time + timedelta(minutes=settings.CHECKIN_WINDOW_AFTER_MINUTES)

        is_active = (window_start <= now_dt <= window_end) and not pair_record.is_locked
        seconds_remaining = int((window_end - now_dt).total_seconds()) if is_active else None
        
        reason_closed = None
        if pair_record.is_locked:
            reason_closed = "LOCKED_BY_ADMIN"
        elif now_dt < window_start:
            reason_closed = "NOT_STARTED_YET"
        elif now_dt > window_end:
            reason_closed = "TIME_EXPIRED"

        # Ищем чекин студента
        att_stmt = select(Attendance).where(
            Attendance.pair_id == pair_record.id,
            Attendance.student_id == current_user.id,
        )
        att_res = await db.execute(att_stmt)
        attendance_record = att_res.scalar_one_or_none()

        my_att = None
        if attendance_record:
            my_att = AttendanceShortSchema(
                status=attendance_record.status,
                distance=attendance_record.distance_meters,
                checkin_time=attendance_record.checkin_time,
            )

        pairs_output.append(
            PairItemSchema(
                pair_id=pair_record.id,
                pair_number=slot.pair_number,
                time_start=slot.time_start,
                time_end=slot.time_end,
                subject=slot.subject.title,
                teacher=slot.subject.teacher_name,
                type=slot.subject.subject_type,
                room=slot.room_number,
                building=slot.building_name,
                building_coordinates=CoordinatesSchema(
                    lat=slot.building_lat,
                    lon=slot.building_lon,
                ),
                checkin_status=CheckinStatusSchema(
                    is_active=is_active,
                    window_start=window_start.strftime("%H:%M"),
                    window_end=window_end.strftime("%H:%M"),
                    seconds_remaining=seconds_remaining,
                    reason_closed=reason_closed,
                ),
                my_attendance=my_att,
            )
        )

    return ScheduleTodayResponseSchema(
        date=today,
        day_of_week=dow,
        week_type=current_week_type,
        pairs=pairs_output,
    )

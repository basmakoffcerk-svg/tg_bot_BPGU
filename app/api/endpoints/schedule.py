"""
Academic timetable query with subgroup and week parity filtering.
"""
from datetime import date, datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_active_student, get_db
from app.config import settings
from app.core.time_utils import calculate_checkin_window, get_academic_week
from app.database.models import Attendance, PairsRegistry, ScheduleSlot, Student, Subject
from app.schemas.schedule import (
    AttendanceStatus,
    BuildingCoordinates,
    CheckinStatusInfo,
    PairItem,
    ScheduleTodayResponse,
)

router = APIRouter()


@router.get("/today", response_model=ScheduleTodayResponse, summary="Get today's schedule for student")
async def get_schedule_today(
    current_user: Student = Depends(get_current_active_student),
    db: AsyncSession = Depends(get_db),
) -> ScheduleTodayResponse:
    """
    Returns today's pair schedule filtered by:
    1. Calendar date & ISO weekday (1..6)
    2. Academic week parity (ODD / EVEN or ALL)
    3. Student academic subgroup (0 = common, or matches current_user.subgroup)
    """
    now_local = datetime.now(ZoneInfo(settings.TIMEZONE))
    today_date = now_local.date()
    iso_weekday = today_date.isoweekday()

    week_num, week_type_enum, is_study_day = get_academic_week(today_date)
    week_parity = week_type_enum.value

    # Query existing pairs for today in pairs_registry
    stmt = (
        select(PairsRegistry, ScheduleSlot, Subject)
        .join(ScheduleSlot, PairsRegistry.slot_id == ScheduleSlot.id)
        .join(Subject, ScheduleSlot.subject_id == Subject.id)
        .where(
            PairsRegistry.calendar_date == today_date,
            ScheduleSlot.subgroup.in_([0, current_user.subgroup]),
        )
        .order_by(ScheduleSlot.pair_number)
    )
    res = await db.execute(stmt)
    rows = list(res.all())

    # If no pairs exist for today in registry yet, initialize them from schedule_slots
    if not rows and is_study_day:
        slots_stmt = (
            select(ScheduleSlot, Subject)
            .join(Subject, ScheduleSlot.subject_id == Subject.id)
            .where(
                ScheduleSlot.day_of_week == iso_weekday,
                ScheduleSlot.week_type.in_([week_parity, "ALL"]),
            )
            .order_by(ScheduleSlot.pair_number)
        )
        slots_res = await db.execute(slots_stmt)
        slots_to_seed = slots_res.all()

        for slot_item, subj_item in slots_to_seed:
            new_pair = PairsRegistry(
                slot_id=slot_item.id,
                calendar_date=today_date,
                is_locked=False,
            )
            db.add(new_pair)
        await db.flush()

        # Re-query
        res = await db.execute(stmt)
        rows = list(res.all())

    pairs_list: list[PairItem] = []

    for pair_reg, slot, subj in rows:
        # Check personal attendance record
        att_stmt = select(Attendance).where(
            Attendance.pair_id == pair_reg.id,
            Attendance.student_id == current_user.id,
        )
        att_res = await db.execute(att_stmt)
        att = att_res.scalar_one_or_none()

        is_present = att is not None and att.status == "PRESENT"
        window = calculate_checkin_window(
            pair_time_start=slot.time_start,
            current_time=now_local,
            calendar_date=today_date,
            is_locked=pair_reg.is_locked,
            has_checked_in=is_present,
        )

        my_att_schema = None
        if att:
            my_att_schema = AttendanceStatus(
                status=att.status.value if hasattr(att.status, "value") else str(att.status),
                distance=att.distance_meters,
                checkin_time=att.checkin_time,
            )

        pairs_list.append(
            PairItem(
                pair_id=pair_reg.id,
                pair_number=slot.pair_number,
                time_start=slot.time_start,
                time_end=slot.time_end,
                subject=subj.title,
                teacher=subj.teacher_name,
                type=subj.subject_type.value if hasattr(subj.subject_type, "value") else str(subj.subject_type),
                room=slot.room_number,
                building=slot.building_name,
                building_coordinates=BuildingCoordinates(
                    lat=slot.building_lat,
                    lon=slot.building_lon,
                ),
                checkin_status=CheckinStatusInfo(
                    is_active=window.is_active,
                    window_start=window.window_start,
                    window_end=window.window_end,
                    seconds_remaining=window.seconds_remaining,
                    seconds_until_start=window.seconds_until_start,
                    reason_closed=window.reason_closed,
                ),
                my_attendance=my_att_schema,
            )
        )

    await db.commit()

    return ScheduleTodayResponse(
        date=today_date,
        day_of_week=iso_weekday,
        week_type=week_parity,
        pairs=pairs_list,
    )

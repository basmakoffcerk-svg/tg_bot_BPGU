import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user
from api.schemas.schedule import (
    BuildingCoordinatesSchema,
    CheckinWindowStatusSchema,
    DailyScheduleResponse,
    PairItemSchema,
    StudentAttendanceSummarySchema,
)
from core.database import get_db
from models import (
    Attendance,
    PairsRegistry,
    ScheduleSlot,
    Student,
    Subject,
    WeekTypeEnum,
)
from services.attendance_service import (
    get_checkin_window_status,
    get_or_create_pairs_for_date,
)

router = APIRouter(prefix="/schedule", tags=["Schedule"])


@router.get("/today", response_model=DailyScheduleResponse)
async def get_today_schedule(current_user: Student = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """
    Returns today's class schedule for the authenticated student's subgroup,
    including real-time check-in window countdown and attendance status.
    """
    today = datetime.date.today()
    dow = today.isoweekday()

    if dow > 6:
        # Sunday - no classes
        return DailyScheduleResponse(
            date=today.isoformat(), day_of_week=dow, week_type=WeekTypeEnum.ALL.value, pairs=[]
        )

    # Ensure pairs are instantiated in pairs_registry for today
    await get_or_create_pairs_for_date(db, today)

    # Fetch slots for this day for subgroup (0 or current_user.subgroup)
    res = await db.execute(
        select(PairsRegistry, ScheduleSlot, Subject)
        .join(ScheduleSlot, PairsRegistry.slot_id == ScheduleSlot.id)
        .join(Subject, ScheduleSlot.subject_id == Subject.id)
        .where(
            PairsRegistry.calendar_date == today,
            ScheduleSlot.day_of_week == dow,
            ScheduleSlot.subgroup.in_([0, current_user.subgroup]),
        )
        .order_by(ScheduleSlot.pair_number)
    )
    pair_records = res.all()

    # Fetch user's attendances for today
    pair_ids = [p[0].id for p in pair_records]
    user_attendances = {}
    if pair_ids:
        att_res = await db.execute(
            select(Attendance).where(Attendance.pair_id.in_(pair_ids), Attendance.student_id == current_user.id)
        )
        for att in att_res.scalars().all():
            user_attendances[att.pair_id] = att

    pair_items = []
    for pair_obj, slot_obj, subj_obj in pair_records:
        win_status = get_checkin_window_status(slot_obj, today)
        att = user_attendances.get(pair_obj.id)

        att_schema = None
        if att:
            att_schema = StudentAttendanceSummarySchema(
                status=att.status,
                distance=att.distance_meters,
                checkin_time=att.checkin_time.isoformat() if att.checkin_time else None,
            )

        pair_items.append(
            PairItemSchema(
                pair_id=pair_obj.id,
                pair_number=slot_obj.pair_number,
                time_start=slot_obj.time_start,
                time_end=slot_obj.time_end,
                subject=subj_obj.title,
                teacher=subj_obj.teacher_name,
                type=subj_obj.subject_type,
                room=slot_obj.room_number,
                building=slot_obj.building_name,
                building_coordinates=BuildingCoordinatesSchema(lat=slot_obj.building_lat, lon=slot_obj.building_lon),
                checkin_status=CheckinWindowStatusSchema(
                    is_active=win_status["is_active"] and not pair_obj.is_locked,
                    window_start=win_status["window_start"],
                    window_end=win_status["window_end"],
                    seconds_remaining=win_status.get("seconds_remaining"),
                    reason_closed="PAIR_LOCKED" if pair_obj.is_locked else win_status.get("reason_closed"),
                ),
                my_attendance=att_schema,
            )
        )

    return DailyScheduleResponse(
        date=today.isoformat(), day_of_week=dow, week_type=WeekTypeEnum.ALL.value, pairs=pair_items
    )

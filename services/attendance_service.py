import datetime
import json
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from core.config import settings
from models import (
    Attendance,
    AttendanceStatusEnum,
    AuditLog,
    PairsRegistry,
    RoleEnum,
    ScheduleSlot,
    Student,
)
from services.geo_service import (
    fast_geocheck,
    validate_client_timestamp,
    validate_coordinates_accuracy,
)


def get_current_time() -> datetime.datetime:
    """Returns current local datetime according to configured timezone."""
    try:
        return datetime.datetime.now(ZoneInfo(settings.TIMEZONE)).replace(tzinfo=None)
    except Exception:
        return datetime.datetime.now()


def parse_time_to_minutes(time_str: str) -> int:
    """Parses 'HH:MM' string to minutes from start of day."""
    parts = time_str.split(":")
    return int(parts[0]) * 60 + int(parts[1])


def get_checkin_window_status(
    slot: ScheduleSlot, calendar_date: datetime.date, now_dt: datetime.datetime | None = None
) -> dict:
    """
    Computes check-in window state for a pair slot:
    - Window starts: time_start - CHECKIN_WINDOW_BEFORE_MINUTES (5 min)
    - Window ends: time_start + CHECKIN_WINDOW_AFTER_MINUTES (15 min)
    """
    if now_dt is None:
        now_dt = get_current_time()

    slot_start_min = parse_time_to_minutes(slot.time_start)
    window_start_min = slot_start_min - settings.CHECKIN_WINDOW_BEFORE_MINUTES
    window_end_min = slot_start_min + settings.CHECKIN_WINDOW_AFTER_MINUTES

    w_start_hour = (window_start_min // 60) % 24
    w_start_minute = window_start_min % 60
    w_end_hour = (window_end_min // 60) % 24
    w_end_minute = window_end_min % 60

    window_start_str = f"{w_start_hour:02d}:{w_start_minute:02d}"
    window_end_str = f"{w_end_hour:02d}:{w_end_minute:02d}"

    # Only valid if calendar_date is today
    if calendar_date != now_dt.date():
        return {
            "is_active": False,
            "window_start": window_start_str,
            "window_end": window_end_str,
            "reason_closed": "DATE_MISMATCH",
            "seconds_remaining": 0,
        }

    now_min = now_dt.hour * 60 + now_dt.minute + (now_dt.second / 60.0)

    # Handle clamped start for edge cases near midnight
    effective_start_min = max(0, window_start_min)

    if now_min < effective_start_min:
        return {
            "is_active": False,
            "window_start": window_start_str,
            "window_end": window_end_str,
            "reason_closed": "NOT_STARTED_YET",
            "seconds_remaining": int((effective_start_min - now_min) * 60),
        }
    elif now_min > window_end_min:
        return {
            "is_active": False,
            "window_start": window_start_str,
            "window_end": window_end_str,
            "reason_closed": "TIME_EXPIRED",
            "seconds_remaining": 0,
        }
    else:
        seconds_left = int((window_end_min - now_min) * 60)
        return {
            "is_active": True,
            "window_start": window_start_str,
            "window_end": window_end_str,
            "seconds_remaining": max(0, seconds_left),
        }


async def get_or_create_pairs_for_date(session: AsyncSession, target_date: datetime.date) -> list[PairsRegistry]:
    """Ensures that PairsRegistry entries exist for all schedule slots of day_of_week."""
    dow = target_date.isoweekday()
    if dow > 6:
        return []

    # Get slots for this day of week
    res_slots = await session.execute(select(ScheduleSlot).where(ScheduleSlot.day_of_week == dow))
    slots = res_slots.scalars().all()

    pairs = []
    for slot in slots:
        res_pair = await session.execute(
            select(PairsRegistry).where(PairsRegistry.slot_id == slot.id, PairsRegistry.calendar_date == target_date)
        )
        pair = res_pair.scalar_one_or_none()
        if not pair:
            try:
                pair = PairsRegistry(slot_id=slot.id, calendar_date=target_date, is_locked=False)
                session.add(pair)
                await session.flush()
            except Exception:
                # Concurrently created by another request: rollback savepoint and reload
                await session.rollback()
                res_retry = await session.execute(
                    select(PairsRegistry).where(
                        PairsRegistry.slot_id == slot.id, PairsRegistry.calendar_date == target_date
                    )
                )
                pair = res_retry.scalar_one_or_none()
        if pair:
            pairs.append(pair)

    await session.commit()
    return pairs


async def process_checkin(
    session: AsyncSession,
    student: Student,
    pair_id: int,
    client_lat: float,
    client_lon: float,
    accuracy: float,
    client_timestamp: float | None = None,
) -> tuple[bool, str, dict]:
    """
    Executes student check-in on a pair:
    - Validates GPS accuracy
    - Checks pair lock and time window
    - Executes fast geocheck
    - Records attendance
    """
    # 1. Accuracy validation
    acc_ok, acc_err = validate_coordinates_accuracy(accuracy, settings.MAX_GPS_ACCURACY_METERS)
    if not acc_ok:
        return False, acc_err or "Inaccurate GPS", {"status_code": 400, "code": "INACCURATE_GPS"}

    # 2. Timestamp drift validation
    ts_ok, ts_err = validate_client_timestamp(client_timestamp)
    if not ts_ok:
        return False, ts_err or "Timestamp drift", {"status_code": 400, "code": "CLOCK_DRIFT"}

    # 3. Load pair with slot
    res = await session.execute(select(PairsRegistry).where(PairsRegistry.id == pair_id))
    pair = res.scalar_one_or_none()
    if not pair:
        return False, "Пара не найдена в реестре", {"status_code": 404, "code": "PAIR_NOT_FOUND"}

    if pair.is_locked:
        return False, "Журнал пары зафиксирован старостой. Чекин закрыт.", {"status_code": 400, "code": "PAIR_LOCKED"}

    slot_res = await session.execute(select(ScheduleSlot).where(ScheduleSlot.id == pair.slot_id))
    slot = slot_res.scalar_one_or_none()
    if not slot:
        return False, "Слот расписания не найден", {"status_code": 404, "code": "SLOT_NOT_FOUND"}

    # Subgroup check (if slot is subgroup-specific)
    if slot.subgroup != 0 and slot.subgroup != student.subgroup:
        return (
            False,
            f"Данное занятие проводится только для подгруппы {slot.subgroup}",
            {"status_code": 400, "code": "WRONG_SUBGROUP"},
        )

    # 4. Checkin window validation
    win_status = get_checkin_window_status(slot, pair.calendar_date)
    if not win_status["is_active"]:
        reason = win_status.get("reason_closed")
        if reason == "NOT_STARTED_YET":
            msg = f"Окно отметки откроется в {win_status['window_start']} (за 5 мин до начала пары)"
        elif reason == "TIME_EXPIRED":
            msg = f"Окно отметки закрылось в {win_status['window_end']} (первые 15 мин пары)"
        else:
            msg = "Окно отметки для этой пары в данный момент закрыто"
        return False, msg, {"status_code": 400, "code": "CHECKIN_WINDOW_CLOSED", "window": win_status}

    # 5. Geocheck (Bounding Box + Haversine)
    within_radius, distance = fast_geocheck(
        client_lat, client_lon, slot.building_lat, slot.building_lon, slot.radius_meters
    )

    if not within_radius:
        return (
            False,
            (
                f"Вы находитесь вне аудиторного фонда ({slot.building_name}). "
                f"Дистанция: {distance} м (лимит {slot.radius_meters} м)"
            ),
            {
                "status_code": 400,
                "code": "OUT_OF_BOUNDS",
                "distance": distance,
                "limit": slot.radius_meters,
                "building": slot.building_name,
            },
        )

    # 6. Upsert Attendance record
    now_time = get_current_time()
    att_res = await session.execute(
        select(Attendance).where(Attendance.pair_id == pair_id, Attendance.student_id == student.id)
    )
    attendance = att_res.scalar_one_or_none()
    if not attendance:
        attendance = Attendance(
            pair_id=pair_id,
            student_id=student.id,
            status=AttendanceStatusEnum.PRESENT.value,
            checkin_time=now_time,
            client_lat=client_lat,
            client_lon=client_lon,
            distance_meters=distance,
            accuracy_meters=accuracy,
            verified_by_admin=False,
        )
        session.add(attendance)
    else:
        attendance.status = AttendanceStatusEnum.PRESENT.value
        attendance.checkin_time = now_time
        attendance.client_lat = client_lat
        attendance.client_lon = client_lon
        attendance.distance_meters = distance
        attendance.accuracy_meters = accuracy
        attendance.verified_by_admin = False

    await session.commit()
    return (
        True,
        "Присутствие успешно подтверждено!",
        {"status": "PRESENT", "pair_id": pair_id, "distance_meters": distance, "checkin_time": now_time.isoformat()},
    )


async def get_pair_grid(session: AsyncSession, pair_id: int) -> dict | None:
    """Constructs the interactive Starosta attendance grid for a pair."""
    res_pair = await session.execute(select(PairsRegistry).where(PairsRegistry.id == pair_id))
    pair = res_pair.scalar_one_or_none()
    if not pair:
        return None

    res_slot = await session.execute(
        select(ScheduleSlot).options(selectinload(ScheduleSlot.subject)).where(ScheduleSlot.id == pair.slot_id)
    )
    slot = res_slot.scalar_one_or_none()
    if not slot:
        return None

    # Load all students
    query = select(Student)
    if slot.subgroup != 0:
        query = query.where(Student.subgroup == slot.subgroup)
    query = query.order_by(Student.full_name)

    res_students = await session.execute(query)
    students = res_students.scalars().all()

    # Load existing attendance records
    res_att = await session.execute(select(Attendance).where(Attendance.pair_id == pair_id))
    attendances = {att.student_id: att for att in res_att.scalars().all()}

    summary = {
        "total_students": len(students),
        "present_count": 0,
        "absent_unexcused_count": 0,
        "absent_excused_count": 0,
        "manual_confirmed_count": 0,
        "late_count": 0,
    }

    student_items = []
    for s in students:
        att = attendances.get(s.id)
        status = att.status if att else AttendanceStatusEnum.ABSENT_UNEXCUSED.value

        # Color badge mappings
        color_map = {
            AttendanceStatusEnum.PRESENT.value: "green",
            AttendanceStatusEnum.ABSENT_UNEXCUSED.value: "gray",
            AttendanceStatusEnum.MANUAL_CONFIRM.value: "yellow",
            AttendanceStatusEnum.LATE.value: "blue",
            AttendanceStatusEnum.ABSENT_EXCUSED.value: "purple",
        }

        # Update summary count
        if status == AttendanceStatusEnum.PRESENT.value:
            summary["present_count"] += 1
        elif status == AttendanceStatusEnum.ABSENT_UNEXCUSED.value:
            summary["absent_unexcused_count"] += 1
        elif status == AttendanceStatusEnum.MANUAL_CONFIRM.value:
            summary["manual_confirmed_count"] += 1
        elif status == AttendanceStatusEnum.LATE.value:
            summary["late_count"] += 1
        elif status == AttendanceStatusEnum.ABSENT_EXCUSED.value:
            summary["absent_excused_count"] += 1

        student_items.append(
            {
                "student_id": s.id,
                "full_name": s.full_name,
                "subgroup": s.subgroup,
                "status": status,
                "badge_color": color_map.get(status, "gray"),
                "distance": att.distance_meters if att else None,
                "checkin_time": att.checkin_time.strftime("%H:%M:%S") if att and att.checkin_time else None,
                "verified_by_admin": att.verified_by_admin if att else False,
                "excuse_reason": att.excuse_reason if att else None,
            }
        )

    subject_title = slot.subject.title if slot.subject else f"Пара #{slot.pair_number}"

    return {
        "pair_id": pair.id,
        "subject": subject_title,
        "room": slot.room_number,
        "building": slot.building_name,
        "pair_number": slot.pair_number,
        "time_start": slot.time_start,
        "time_end": slot.time_end,
        "is_locked": pair.is_locked,
        "locked_at": pair.locked_at.isoformat() if pair.locked_at else None,
        "summary": summary,
        "students": student_items,
    }


async def override_attendance_status(
    session: AsyncSession,
    admin_student: Student,
    pair_id: int,
    target_student_id: int,
    new_status: str,
    excuse_reason: str | None = None,
) -> tuple[bool, str, dict]:
    """Applies Starosta/Zam manual override to student attendance status."""
    res_pair = await session.execute(select(PairsRegistry).where(PairsRegistry.id == pair_id))
    pair = res_pair.scalar_one_or_none()
    if not pair:
        return False, "Пара не найдена", {}

    res_target = await session.execute(select(Student).where(Student.id == target_student_id))
    target = res_target.scalar_one_or_none()
    if not target:
        return False, "Студент не найден", {}

    # Validation of status
    valid_statuses = {s.value for s in AttendanceStatusEnum}
    if new_status not in valid_statuses:
        return False, f"Недопустимый статус посещаемости: {new_status}", {}

    if pair.is_locked:
        return False, "Журнал пары зафиксирован старостой. Изменение статуса заблокировано.", {}

    # Upsert attendance
    res_att = await session.execute(
        select(Attendance).where(Attendance.pair_id == pair_id, Attendance.student_id == target_student_id)
    )
    att = res_att.scalar_one_or_none()
    prev_status = att.status if att else "ABSENT_UNEXCUSED"

    now_dt = get_current_time()
    if not att:
        att = Attendance(
            pair_id=pair_id,
            student_id=target_student_id,
            status=new_status,
            verified_by_admin=True,
            excuse_reason=excuse_reason,
            created_at=now_dt,
            updated_at=now_dt,
        )
        session.add(att)
    else:
        att.status = new_status
        att.verified_by_admin = True
        att.excuse_reason = excuse_reason
        att.updated_at = now_dt

    # Record in AuditLog
    audit_entry = AuditLog(
        admin_id=admin_student.id,
        action="STATUS_OVERRIDE",
        target_id=target_student_id,
        details_json=json.dumps(
            {
                "pair_id": pair_id,
                "target_student_name": target.full_name,
                "prev_status": prev_status,
                "new_status": new_status,
                "excuse_reason": excuse_reason,
            },
            ensure_ascii=False,
        ),
    )
    session.add(audit_entry)
    await session.commit()

    return (
        True,
        "Статус успешно обновлен",
        {"pair_id": pair_id, "student_id": target_student_id, "status": new_status, "updated_at": now_dt.isoformat()},
    )


async def lock_pair(session: AsyncSession, admin_student: Student, pair_id: int) -> tuple[bool, str, dict]:
    """Locks attendance journal for a pair (only STAROSTA)."""
    if admin_student.role != RoleEnum.STAROSTA.value:
        return False, "Только староста может зафиксировать журнал пары", {}

    res_pair = await session.execute(select(PairsRegistry).where(PairsRegistry.id == pair_id))
    pair = res_pair.scalar_one_or_none()
    if not pair:
        return False, "Пара не найдена", {}

    now_dt = get_current_time()
    pair.is_locked = True
    pair.locked_at = now_dt
    pair.locked_by_id = admin_student.id

    audit_entry = AuditLog(
        admin_id=admin_student.id,
        action="PAIR_LOCK",
        target_id=pair_id,
        details_json=json.dumps({"locked_at": now_dt.isoformat()}),
    )
    session.add(audit_entry)
    await session.commit()

    return (
        True,
        "Журнал пары успешно зафиксирован",
        {"pair_id": pair_id, "is_locked": True, "locked_at": now_dt.isoformat()},
    )

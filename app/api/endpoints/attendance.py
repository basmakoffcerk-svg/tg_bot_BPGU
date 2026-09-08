"""
Geolocation check-in, attendance matrix chessboard, status override, and pair locking.
"""
from datetime import datetime, timezone
import json
import time
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.deps import (
    get_current_active_student,
    get_db,
    require_starosta,
    require_zam_or_starosta,
)
from app.config import settings
from app.core.exceptions import ProblemException, ProblemType
from app.core.geo import haversine_distance, validate_gps_accuracy, validate_sensor_timestamp
from app.core.time_utils import calculate_checkin_window
from app.database.models import (
    Attendance,
    AttendanceStatus,
    AuditLog,
    PairsRegistry,
    ScheduleSlot,
    Student,
)
from app.schemas.attendance import (
    CheckinRequest,
    CheckinResponse,
    GridResponse,
    GridSummary,
    LockPairResponse,
    OverrideRequest,
    OverrideResponse,
    StudentGridItem,
)

router = APIRouter()

VALID_STATUSES = {
    "PRESENT",
    "ABSENT_UNEXCUSED",
    "ABSENT_EXCUSED",
    "MANUAL_CONFIRM",
    "LATE",
}

BADGE_COLORS = {
    "PRESENT": "green",
    "ABSENT_UNEXCUSED": "grey",
    "MANUAL_CONFIRM": "yellow",
    "LATE": "blue",
    "ABSENT_EXCUSED": "purple",
}


# ============================================================================
# 1. Student Geolocation Check-in
# ============================================================================

@router.post("/checkin", response_model=CheckinResponse, summary="Perform GPS attendance check-in")
async def checkin(
    req: CheckinRequest,
    current_user: Student = Depends(get_current_active_student),
    db: AsyncSession = Depends(get_db),
) -> CheckinResponse:
    """
    Validates GPS sensor accuracy, timestamp skew, pair lock state,
    subgroup compatibility, check-in bell window, and Haversine distance.
    """
    now_ts = time.time()
    now_local = datetime.now(ZoneInfo(settings.TIMEZONE))

    # 1. Fetch pair registry
    pair_stmt = (
        select(PairsRegistry)
        .where(PairsRegistry.id == req.pair_id)
        .options(selectinload(PairsRegistry.slot))
    )
    pair = (await db.execute(pair_stmt)).scalar_one_or_none()
    if not pair:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Пара не найдена",
            detail=f"Занятие с pair_id={req.pair_id} не найдено в реестре пар.",
            type_=ProblemType.NOT_FOUND,
        )

    # 2. Check pair lock
    if pair.is_locked:
        raise ProblemException(
            status_code=status.HTTP_400_BAD_REQUEST,
            title="Журнал пары заблокирован",
            detail="Староста зафиксировал посещаемость на этой паре. Прием чекинов завершен.",
            type_=ProblemType.PAIR_LOCKED,
        )

    # 3. Check GPS accuracy (boundary: <= 50.0m)
    acc_valid, _ = validate_gps_accuracy(req.accuracy, settings.MAX_GPS_ACCURACY_METERS)
    if not acc_valid:
        raise ProblemException(
            status_code=status.HTTP_400_BAD_REQUEST,
            title="Неточный GPS сигнал",
            detail=f"Точность GPS ({req.accuracy:.1f} м) превышает допустимый порог ({settings.MAX_GPS_ACCURACY_METERS:.1f} м).",
            type_=ProblemType.INACCURATE_GPS,
            data={"accuracy": req.accuracy, "max_allowed": settings.MAX_GPS_ACCURACY_METERS},
        )

    # 4. Check timestamp skew (boundary: <= 30.0s)
    drift_valid, _ = validate_sensor_timestamp(req.timestamp, now_ts, settings.MAX_CLOCK_DRIFT_SECONDS)
    if not drift_valid:
        raise ProblemException(
            status_code=status.HTTP_400_BAD_REQUEST,
            title="Рассинхронизация времени",
            detail="Временная метка координат не совпадает с серверным временем (> 30 сек).",
            type_=ProblemType.CLOCK_SKEW,
            data={"timestamp": req.timestamp, "server_time": now_ts},
        )

    slot = pair.slot

    # 5. Check subgroup compatibility
    if slot.subgroup != 0 and slot.subgroup != current_user.subgroup:
        raise ProblemException(
            status_code=status.HTTP_400_BAD_REQUEST,
            title="Несоответствие подгруппы",
            detail=f"Данное занятие проводится для подгруппы {slot.subgroup}, вы состоите в подгруппе {current_user.subgroup}.",
            type_=ProblemType.OUT_OF_BOUNDS,
        )

    # 6. Check bell window (-5m to +15m)
    window = calculate_checkin_window(
        pair_time_start=slot.time_start,
        current_time=now_local,
        calendar_date=pair.calendar_date,
        is_locked=pair.is_locked,
    )
    if not window.is_active:
        raise ProblemException(
            status_code=status.HTTP_400_BAD_REQUEST,
            title="Окно чекина закрыто",
            detail="Чекин открыт строго за 5 минут до начала пары и первые 15 минут занятия.",
            type_=ProblemType.CHECKIN_WINDOW_CLOSED,
            data={"reason": window.reason_closed, "window_start": window.window_start, "window_end": window.window_end},
        )

    # 7. Check distance (boundary: <= 150.0m)
    dist = haversine_distance(req.client_lat, req.client_lon, slot.building_lat, slot.building_lon)
    max_radius = float(slot.radius_meters if slot.radius_meters else settings.MAX_ALLOWED_DISTANCE_METERS)

    if dist > max_radius:
        raise ProblemException(
            status_code=status.HTTP_400_BAD_REQUEST,
            title="Геолокация вне аудитории",
            detail=f"Вы находитесь на расстоянии {dist:.1f} м от корпуса при максимально допустимом лимите {max_radius:.1f} м.",
            type_=ProblemType.OUT_OF_BOUNDS,
            data={
                "distance": round(dist, 1),
                "accuracy": req.accuracy,
                "max_allowed": max_radius,
            },
        )

    # 8. Record attendance
    att_stmt = select(Attendance).where(
        Attendance.pair_id == pair.id,
        Attendance.student_id == current_user.id,
    )
    attendance = (await db.execute(att_stmt)).scalar_one_or_none()

    rounded_dist = round(dist, 1)

    if attendance:
        attendance.status = "PRESENT"
        attendance.checkin_time = now_local
        attendance.client_lat = req.client_lat
        attendance.client_lon = req.client_lon
        attendance.distance_meters = rounded_dist
        attendance.accuracy_meters = req.accuracy
        attendance.verified_by_admin = False
    else:
        attendance = Attendance(
            pair_id=pair.id,
            student_id=current_user.id,
            status="PRESENT",
            checkin_time=now_local,
            client_lat=req.client_lat,
            client_lon=req.client_lon,
            distance_meters=rounded_dist,
            accuracy_meters=req.accuracy,
            verified_by_admin=False,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(attendance)

    await db.commit()

    return CheckinResponse(
        status="PRESENT",
        pair_id=pair.id,
        distance_meters=rounded_dist,
        checkin_time=now_local,
        message="Присутствие успешно подтверждено!",
    )


# ============================================================================
# 2. Starosta Interactive Chessboard Grid
# ============================================================================

@router.get("/grid/{pair_id}", response_model=GridResponse, summary="Get pair attendance matrix")
async def get_attendance_grid(
    pair_id: int,
    current_admin: Student = Depends(require_zam_or_starosta),
    db: AsyncSession = Depends(get_db),
) -> GridResponse:
    """Returns attendance matrix for all students for a selected pair."""
    pair_stmt = (
        select(PairsRegistry)
        .where(PairsRegistry.id == pair_id)
        .options(selectinload(PairsRegistry.slot).selectinload(ScheduleSlot.subject))
    )
    pair = (await db.execute(pair_stmt)).scalar_one_or_none()
    if not pair:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Пара не найдена",
            detail=f"Занятие с pair_id={pair_id} не найдено.",
            type_=ProblemType.NOT_FOUND,
        )

    slot = pair.slot

    # Query students (filtered by subgroup if pair is subgroup-specific)
    students_stmt = select(Student).where(Student.status == "ACTIVE")
    if slot.subgroup in (1, 2):
        students_stmt = students_stmt.where(Student.subgroup == slot.subgroup)
    students_stmt = students_stmt.order_by(Student.full_name)
    students = list((await db.execute(students_stmt)).scalars().all())

    # Query attendance records
    att_stmt = select(Attendance).where(Attendance.pair_id == pair.id)
    attendances = (await db.execute(att_stmt)).scalars().all()
    att_map = {a.student_id: a for a in attendances}

    grid_items: list[StudentGridItem] = []
    summary_counts = {
        "PRESENT": 0,
        "ABSENT_UNEXCUSED": 0,
        "ABSENT_EXCUSED": 0,
        "MANUAL_CONFIRM": 0,
        "LATE": 0,
    }

    for s in students:
        att = att_map.get(s.id)
        st_val = att.status if att else "ABSENT_UNEXCUSED"
        st_str = st_val.value if hasattr(st_val, "value") else str(st_val)
        summary_counts[st_str] = summary_counts.get(st_str, 0) + 1

        checkin_str = None
        if att and att.checkin_time:
            checkin_str = att.checkin_time.strftime("%H:%M:%S")

        grid_items.append(
            StudentGridItem(
                student_id=s.id,
                full_name=s.full_name,
                subgroup=s.subgroup,
                status=st_str,
                badge_color=BADGE_COLORS.get(st_str, "grey"),
                distance=att.distance_meters if att else None,
                checkin_time=checkin_str,
                verified_by_admin=att.verified_by_admin if att else False,
                excuse_reason=att.excuse_reason if att else None,
            )
        )

    summary = GridSummary(
        total_students=len(students),
        present_count=summary_counts["PRESENT"],
        absent_unexcused_count=summary_counts["ABSENT_UNEXCUSED"],
        absent_excused_count=summary_counts["ABSENT_EXCUSED"],
        manual_confirmed_count=summary_counts["MANUAL_CONFIRM"],
        late_count=summary_counts["LATE"],
    )

    return GridResponse(
        pair_id=pair.id,
        subject=slot.subject.title,
        is_locked=pair.is_locked,
        summary=summary,
        students=grid_items,
    )


# ============================================================================
# 3. Status Override (Manual Edit by Starosta / Zam)
# ============================================================================

@router.patch("/override", response_model=OverrideResponse, summary="Manual attendance status override")
async def override_status(
    req: OverrideRequest,
    current_admin: Student = Depends(require_zam_or_starosta),
    db: AsyncSession = Depends(get_db),
) -> OverrideResponse:
    """Modifies student attendance status and records administrative audit log."""
    if req.new_status not in VALID_STATUSES:
        raise ProblemException(
            status_code=status.HTTP_400_BAD_REQUEST,
            title="Недопустимый статус",
            detail=f"Статус '{req.new_status}' не является допустимым.",
        )

    pair = await db.get(PairsRegistry, req.pair_id)
    if not pair:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Пара не найдена",
            detail=f"Занятие с pair_id={req.pair_id} не найдено.",
            type_=ProblemType.NOT_FOUND,
        )

    # Only STAROSTA can override a locked pair
    admin_role = current_admin.role.value if hasattr(current_admin.role, "value") else str(current_admin.role)
    if pair.is_locked and admin_role != "STAROSTA":
        raise ProblemException(
            status_code=status.HTTP_403_FORBIDDEN,
            title="Пара заблокирована",
            detail="Редактирование зафиксированной пары разрешено только старосте группы.",
            type_=ProblemType.FORBIDDEN_ROLE,
        )

    att_stmt = select(Attendance).where(
        Attendance.pair_id == req.pair_id,
        Attendance.student_id == req.student_id,
    )
    attendance = (await db.execute(att_stmt)).scalar_one_or_none()

    now_local = datetime.now(ZoneInfo(settings.TIMEZONE))
    old_status = attendance.status if attendance else "ABSENT_UNEXCUSED"
    old_status_str = old_status.value if hasattr(old_status, "value") else str(old_status)

    if attendance:
        attendance.status = req.new_status
        attendance.verified_by_admin = True
        attendance.excuse_reason = req.excuse_reason
        attendance.updated_at = now_local
    else:
        attendance = Attendance(
            pair_id=req.pair_id,
            student_id=req.student_id,
            status=req.new_status,
            verified_by_admin=True,
            excuse_reason=req.excuse_reason,
            created_at=now_local,
            updated_at=now_local,
        )
        db.add(attendance)

    # Insert audit entry
    audit_entry = AuditLog(
        admin_id=current_admin.id,
        action="STATUS_OVERRIDE",
        target_id=req.student_id,
        details_json=json.dumps({
            "pair_id": req.pair_id,
            "old_status": old_status_str,
            "new_status": req.new_status,
            "excuse_reason": req.excuse_reason,
        }, ensure_ascii=False),
        created_at=now_local,
    )
    db.add(audit_entry)

    await db.commit()

    return OverrideResponse(
        success=True,
        pair_id=req.pair_id,
        student_id=req.student_id,
        status=req.new_status,
        updated_at=now_local,
    )


# ============================================================================
# 4. Pair Lock Mechanism
# ============================================================================

@router.post("/lock/{pair_id}", response_model=LockPairResponse, summary="Lock pair attendance journal")
async def lock_pair(
    pair_id: int,
    starosta: Student = Depends(require_starosta),
    db: AsyncSession = Depends(get_db),
) -> LockPairResponse:
    """Permanently seals attendance for a pair (STAROSTA only)."""
    pair = await db.get(PairsRegistry, pair_id)
    if not pair:
        raise ProblemException(
            status_code=status.HTTP_404_NOT_FOUND,
            title="Пара не найдена",
            detail=f"Занятие с pair_id={pair_id} не найдено.",
            type_=ProblemType.NOT_FOUND,
        )

    now_local = datetime.now(ZoneInfo(settings.TIMEZONE))
    pair.is_locked = True
    pair.locked_at = now_local
    pair.locked_by_id = starosta.id

    audit_entry = AuditLog(
        admin_id=starosta.id,
        action="PAIR_LOCK",
        target_id=pair.id,
        details_json=json.dumps({"locked_at": now_local.isoformat()}),
        created_at=now_local,
    )
    db.add(audit_entry)

    await db.commit()

    return LockPairResponse(
        success=True,
        pair_id=pair.id,
        is_locked=True,
        locked_at=now_local,
    )

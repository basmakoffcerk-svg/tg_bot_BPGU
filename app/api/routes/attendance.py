"""
Маршруты посещаемости: геочекин студента, шахматка старосты, ручной оверрайд и лок пары.
"""
from datetime import datetime, timedelta
from typing import Dict
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.dependencies import get_current_user, require_roles
from app.api.schemas import (
    AttendanceGridResponseSchema,
    CheckinRequestSchema,
    CheckinResponseSchema,
    GridStudentSchema,
    LockPairResponseSchema,
    OverrideRequestSchema,
    OverrideResponseSchema,
)
from app.core.config import settings
from app.core.database import get_db_session
from app.models import (
    Attendance,
    AuditLog,
    PairRegistry,
    ScheduleSlot,
    Student,
    ROLE_STAROSTA,
    ROLE_ZAM,
    STATUS_ABSENT_EXCUSED,
    STATUS_ABSENT_UNEXCUSED,
    STATUS_LATE,
    STATUS_MANUAL_CONFIRM,
    STATUS_PRESENT,
)
from app.services.geo_service import validate_checkin_location

router = APIRouter(prefix="/attendance", tags=["Attendance"])


@router.post("/checkin", response_model=CheckinResponseSchema)
async def submit_checkin(
    payload: CheckinRequestSchema,
    current_user: Student = Depends(get_current_user),
    db: AsyncSession = Depends(get_db_session),
):
    """Принимает GPS координаты студента и регистрирует факт присутствия."""
    # 1. Загружаем пару и слот
    stmt = (
        select(PairRegistry)
        .options(selectinload(PairRegistry.slot))
        .where(PairRegistry.id == payload.pair_id)
    )
    res = await db.execute(stmt)
    pair = res.scalar_one_or_none()
    if not pair:
        raise HTTPException(status_code=404, detail="Пара не найдена в реестре.")

    if pair.is_locked:
        raise HTTPException(status_code=400, detail="Журнал посещаемости на эту пару зафиксирован старостой.")

    slot = pair.slot
    # Проверка подгруппы
    if slot.subgroup != 0 and slot.subgroup != current_user.subgroup:
        raise HTTPException(status_code=403, detail="Данная пара проводится для другой подгруппы.")

    # 2. Проверка временного окна
    sh, sm = map(int, slot.time_start.split(":"))
    now_dt = datetime.now()
    start_time = datetime.combine(pair.calendar_date, datetime.min.time()).replace(hour=sh, minute=sm)
    window_start = start_time - timedelta(minutes=settings.CHECKIN_WINDOW_BEFORE_MINUTES)
    window_end = start_time + timedelta(minutes=settings.CHECKIN_WINDOW_AFTER_MINUTES)

    if not (window_start <= now_dt <= window_end):
        raise HTTPException(status_code=400, detail="Окно геочекина закрыто. Отметка возможна за 5 мин до пары и первые 15 мин занятия.")

    # 3. Валидация геолокации
    is_valid, distance, err_msg = validate_checkin_location(
        client_lat=payload.client_lat,
        client_lon=payload.client_lon,
        accuracy=payload.accuracy,
        target_lat=slot.building_lat,
        target_lon=slot.building_lon,
        max_radius=slot.radius_meters,
        max_accuracy=settings.MAX_GPS_ACCURACY_METERS,
    )

    if not is_valid:
        raise HTTPException(
            status_code=400,
            detail={
                "error": "OUT_OF_BOUNDS" if distance > slot.radius_meters else "INACCURATE_GPS",
                "message": err_msg,
                "distance": distance,
                "max_allowed": slot.radius_meters,
            }
        )

    # 4. Запись чекина в базу данных
    att_stmt = select(Attendance).where(
        Attendance.pair_id == pair.id,
        Attendance.student_id == current_user.id,
    )
    att_res = await db.execute(att_stmt)
    att = att_res.scalar_one_or_none()

    if not att:
        att = Attendance(
            pair_id=pair.id,
            student_id=current_user.id,
            status=STATUS_PRESENT,
            checkin_time=now_dt,
            client_lat=payload.client_lat,
            client_lon=payload.client_lon,
            distance_meters=distance,
            accuracy_meters=payload.accuracy,
        )
        db.add(att)
    else:
        att.status = STATUS_PRESENT
        att.checkin_time = now_dt
        att.client_lat = payload.client_lat
        att.client_lon = payload.client_lon
        att.distance_meters = distance
        att.accuracy_meters = payload.accuracy

    await db.commit()
    await db.refresh(att)

    return CheckinResponseSchema(
        status=STATUS_PRESENT,
        pair_id=pair.id,
        distance_meters=round(distance, 1),
        checkin_time=att.checkin_time,
        message="Присутствие на паре успешно подтверждено!",
    )


@router.get("/grid/{pair_id}", response_model=AttendanceGridResponseSchema)
async def get_attendance_grid(
    pair_id: int,
    current_user: Student = Depends(require_roles([ROLE_STAROSTA, ROLE_ZAM])),
    db: AsyncSession = Depends(get_db_session),
):
    """Возвращает интерактивную шахматку группы для старосты."""
    pair_stmt = (
        select(PairRegistry)
        .options(selectinload(PairRegistry.slot).selectinload(ScheduleSlot.subject))
        .where(PairRegistry.id == pair_id)
    )
    pair_res = await db.execute(pair_stmt)
    pair = pair_res.scalar_one_or_none()
    if not pair:
        raise HTTPException(status_code=404, detail="Пара не найдена.")

    slot = pair.slot
    # Студенты нужной подгруппы (или вся группа)
    st_stmt = select(Student).where(Student.status == "ACTIVE")
    if slot.subgroup != 0:
        st_stmt = st_stmt.where(Student.subgroup == slot.subgroup)
    st_stmt = st_stmt.order_by(Student.full_name)
    st_res = await db.execute(st_stmt)
    students = st_res.scalars().all()

    # Записи посещаемости
    att_stmt = select(Attendance).where(Attendance.pair_id == pair_id)
    att_res = await db.execute(att_stmt)
    attendances = {a.student_id: a for a in att_res.scalars().all()}

    summary = {
        "total_students": len(students),
        "present_count": 0,
        "absent_unexcused_count": 0,
        "absent_excused_count": 0,
        "manual_confirmed_count": 0,
        "late_count": 0,
    }

    students_list = []
    color_map = {
        STATUS_PRESENT: "green",
        STATUS_ABSENT_UNEXCUSED: "gray",
        STATUS_MANUAL_CONFIRM: "yellow",
        STATUS_LATE: "blue",
        STATUS_ABSENT_EXCUSED: "purple",
    }

    for s in students:
        record = attendances.get(s.id)
        st = record.status if record else STATUS_ABSENT_UNEXCUSED

        if st == STATUS_PRESENT:
            summary["present_count"] += 1
        elif st == STATUS_MANUAL_CONFIRM:
            summary["manual_confirmed_count"] += 1
        elif st == STATUS_ABSENT_EXCUSED:
            summary["absent_excused_count"] += 1
        elif st == STATUS_LATE:
            summary["late_count"] += 1
        else:
            summary["absent_unexcused_count"] += 1

        students_list.append(
            GridStudentSchema(
                student_id=s.id,
                full_name=s.full_name,
                subgroup=s.subgroup,
                status=st,
                badge_color=color_map.get(st, "gray"),
                distance=record.distance_meters if record else None,
                checkin_time=record.checkin_time.strftime("%H:%M:%S") if record and record.checkin_time else None,
                verified_by_admin=record.verified_by_admin if record else False,
                excuse_reason=record.excuse_reason if record else None,
            )
        )

    return AttendanceGridResponseSchema(
        pair_id=pair.id,
        subject=slot.subject.title,
        is_locked=pair.is_locked,
        summary=summary,
        students=students_list,
    )


@router.patch("/override", response_model=OverrideResponseSchema)
async def override_attendance_status(
    payload: OverrideRequestSchema,
    current_user: Student = Depends(require_roles([ROLE_STAROSTA, ROLE_ZAM])),
    db: AsyncSession = Depends(get_db_session),
):
    """Ручной override статуса студента старостой."""
    pair_stmt = select(PairRegistry).where(PairRegistry.id == payload.pair_id)
    pair_res = await db.execute(pair_stmt)
    pair = pair_res.scalar_one_or_none()
    if not pair:
        raise HTTPException(status_code=404, detail="Пара не найдена.")

    att_stmt = select(Attendance).where(
        Attendance.pair_id == payload.pair_id,
        Attendance.student_id == payload.student_id,
    )
    att_res = await db.execute(att_stmt)
    att = att_res.scalar_one_or_none()

    now_dt = datetime.utcnow()
    if not att:
        att = Attendance(
            pair_id=payload.pair_id,
            student_id=payload.student_id,
            status=payload.new_status,
            verified_by_admin=True,
            excuse_reason=payload.excuse_reason,
            updated_at=now_dt,
        )
        db.add(att)
    else:
        att.status = payload.new_status
        att.verified_by_admin = True
        att.excuse_reason = payload.excuse_reason
        att.updated_at = now_dt

    # Запись в аудит-лог
    audit = AuditLog(
        admin_id=current_user.id,
        action="OVERRIDE_STATUS",
        target_id=payload.student_id,
        details_json=f'{{"pair_id": {payload.pair_id}, "new_status": "{payload.new_status}"}}',
    )
    db.add(audit)
    await db.commit()

    return OverrideResponseSchema(
        success=True,
        pair_id=payload.pair_id,
        student_id=payload.student_id,
        status=payload.new_status,
        updated_at=now_dt,
    )


@router.post("/lock/{pair_id}", response_model=LockPairResponseSchema)
async def lock_pair(
    pair_id: int,
    current_user: Student = Depends(require_roles([ROLE_STAROSTA])),
    db: AsyncSession = Depends(get_db_session),
):
    """Запирает журнал посещаемости пары от изменений студентами."""
    pair_stmt = select(PairRegistry).where(PairRegistry.id == pair_id)
    pair_res = await db.execute(pair_stmt)
    pair = pair_res.scalar_one_or_none()
    if not pair:
        raise HTTPException(status_code=404, detail="Пара не найдена.")

    now_dt = datetime.utcnow()
    pair.is_locked = True
    pair.locked_at = now_dt
    pair.locked_by_id = current_user.id

    audit = AuditLog(
        admin_id=current_user.id,
        action="LOCK_PAIR",
        target_id=pair_id,
        details_json=f'{{"locked_at": "{now_dt.isoformat()}"}}',
    )
    db.add(audit)
    await db.commit()

    return LockPairResponseSchema(
        success=True,
        pair_id=pair.id,
        is_locked=True,
        locked_at=now_dt,
    )

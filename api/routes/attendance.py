from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_current_user, require_roles
from api.schemas.attendance import (
    CheckinRequest,
    CheckinResponse,
    LockPairResponse,
    OverrideStatusRequest,
    OverrideStatusResponse,
    PairGridResponse,
)
from core.database import get_db
from models import RoleEnum, Student
from services.attendance_service import (
    get_pair_grid,
    lock_pair,
    override_attendance_status,
    process_checkin,
)

router = APIRouter(prefix="/attendance", tags=["Attendance"])


@router.post("/checkin", response_model=CheckinResponse)
async def submit_geocheckin(
    payload: CheckinRequest, current_user: Student = Depends(get_current_user), db: AsyncSession = Depends(get_db)
):
    """
    Submits student GPS coordinates for geovalidation and attendance check-in.
    """
    success, message, result_data = await process_checkin(
        session=db,
        student=current_user,
        pair_id=payload.pair_id,
        client_lat=payload.client_lat,
        client_lon=payload.client_lon,
        accuracy=payload.accuracy,
        client_timestamp=payload.timestamp,
    )

    if not success:
        status_code = result_data.get("status_code", status.HTTP_400_BAD_REQUEST)
        error_code = result_data.get("code", "CHECKIN_FAILED")
        raise HTTPException(
            status_code=status_code,
            detail={
                "type": f"https://errors.starosta.app/{error_code.lower().replace('_', '-')}",
                "title": "Ошибка отметки посещаемости",
                "status": status_code,
                "detail": message,
                "data": result_data,
            },
        )

    return CheckinResponse(
        status=result_data["status"],
        pair_id=result_data["pair_id"],
        distance_meters=result_data["distance_meters"],
        checkin_time=result_data["checkin_time"],
        message=message,
    )


@router.get("/grid/{pair_id}", response_model=PairGridResponse)
async def get_attendance_grid(
    pair_id: int,
    current_user: Student = Depends(require_roles(RoleEnum.STAROSTA, RoleEnum.ZAM)),
    db: AsyncSession = Depends(get_db),
):
    """
    Returns live attendance grid of the group for Starosta/Zam.
    """
    grid_data = await get_pair_grid(session=db, pair_id=pair_id)
    if not grid_data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"title": "Пара не найдена", "detail": f"Пара с ID {pair_id} не существует."},
        )
    return grid_data


@router.patch("/override", response_model=OverrideStatusResponse)
async def override_status(
    payload: OverrideStatusRequest,
    current_user: Student = Depends(require_roles(RoleEnum.STAROSTA, RoleEnum.ZAM)),
    db: AsyncSession = Depends(get_db),
):
    """
    Manually overrides student attendance status with audit logging.
    """
    success, message, result_data = await override_attendance_status(
        session=db,
        admin_student=current_user,
        pair_id=payload.pair_id,
        target_student_id=payload.student_id,
        new_status=payload.new_status,
        excuse_reason=payload.excuse_reason,
    )

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail={"title": "Ошибка изменения статуса", "detail": message}
        )

    return OverrideStatusResponse(
        success=True,
        pair_id=result_data["pair_id"],
        student_id=result_data["student_id"],
        status=result_data["status"],
        updated_at=result_data["updated_at"],
    )


@router.post("/lock/{pair_id}", response_model=LockPairResponse)
async def lock_pair_journal(
    pair_id: int, current_user: Student = Depends(require_roles(RoleEnum.STAROSTA)), db: AsyncSession = Depends(get_db)
):
    """
    Locks pair attendance journal, preventing further student check-ins.
    """
    success, message, result_data = await lock_pair(session=db, admin_student=current_user, pair_id=pair_id)

    if not success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail={"title": "Ошибка блокировки", "detail": message}
        )

    return LockPairResponse(
        success=True,
        pair_id=result_data["pair_id"],
        is_locked=result_data["is_locked"],
        locked_at=result_data["locked_at"],
    )

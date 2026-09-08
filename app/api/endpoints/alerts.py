"""
Emergency and informational group announcement broadcasts.
"""
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import APIRouter, Depends, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_zam_or_starosta
from app.config import settings
from app.core.exceptions import ProblemException, ProblemType
from app.database.models import BroadcastMessage, Student
from app.schemas.alerts import BroadcastRequest, BroadcastResponse

router = APIRouter()


@router.post(
    "/broadcast",
    response_model=BroadcastResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Queue group broadcast",
)
async def broadcast_alert(
    req: BroadcastRequest,
    current_admin: Student = Depends(require_zam_or_starosta),
    db: AsyncSession = Depends(get_db),
) -> BroadcastResponse:
    """
    Broadcasts critical emergency (@all + DMs) or informational announcements.
    CRITICAL type is restricted strictly to STAROSTA.
    """
    if req.type not in ("CRITICAL", "INFO"):
        raise ProblemException(
            status_code=status.HTTP_400_BAD_REQUEST,
            title="Неверный тип рассылки",
            detail="Тип рассылки должен быть CRITICAL или INFO.",
        )

    admin_role = current_admin.role.value if hasattr(current_admin.role, "value") else str(current_admin.role)
    if req.type == "CRITICAL" and admin_role != "STAROSTA":
        raise ProblemException(
            status_code=status.HTTP_403_FORBIDDEN,
            title="Недостаточно прав для экстренного алерта",
            detail="Отправка критических оповещений (@all + принудительный ЛС) разрешена только старосте группы.",
            type_=ProblemType.FORBIDDEN_ROLE,
        )

    # Count active recipients in group
    count_stmt = select(func.count(Student.id)).where(Student.status == "ACTIVE")
    recipient_count = (await db.execute(count_stmt)).scalar() or 0

    now_local = datetime.now(ZoneInfo(settings.TIMEZONE))
    broadcast = BroadcastMessage(
        sender_id=current_admin.id,
        message_type=req.type,
        title=req.title,
        body=req.body,
        total_recipients=recipient_count,
        read_count=0,
        sent_at=now_local,
    )
    db.add(broadcast)
    await db.commit()
    await db.refresh(broadcast)

    return BroadcastResponse(
        broadcast_id=broadcast.id,
        queued_recipients=recipient_count,
        channel_posted=True,
        status="SENDING",
    )

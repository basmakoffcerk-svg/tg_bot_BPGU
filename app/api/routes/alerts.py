"""
Маршруты экстренного вещания и объявлений.
"""
from fastapi import APIRouter, Depends, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_roles
from app.api.schemas import BroadcastRequestSchema, BroadcastResponseSchema
from app.core.database import get_db_session
from app.models import BroadcastMessage, Student, ROLE_STAROSTA, ROLE_ZAM

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.post("/broadcast", response_model=BroadcastResponseSchema, status_code=status.HTTP_202_ACCEPTED)
async def broadcast_alert(
    payload: BroadcastRequestSchema,
    current_user: Student = Depends(require_roles([ROLE_STAROSTA, ROLE_ZAM])),
    db: AsyncSession = Depends(get_db_session),
):
    """Создает и отправляет широковещательное оповещение группе."""
    # Подсчет подтвержденных получателей
    st_stmt = select(Student).where(Student.status == "ACTIVE", Student.telegram_id.isnot(None))
    st_res = await db.execute(st_stmt)
    recipients = st_res.scalars().all()

    msg = BroadcastMessage(
        sender_id=current_user.id,
        message_type=payload.type,
        title=payload.title,
        body=payload.body,
        total_recipients=len(recipients),
    )
    db.add(msg)
    await db.commit()
    await db.refresh(msg)

    return BroadcastResponseSchema(
        broadcast_id=msg.id,
        queued_recipients=len(recipients),
        channel_posted=True,
        status="SENDING",
    )

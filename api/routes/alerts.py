from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import require_roles
from api.schemas.alerts import BroadcastAlertRequest, BroadcastAlertResponse
from core.database import get_db
from models import BroadcastTypeEnum, RoleEnum, Student
from services.broadcaster import broadcaster_service

router = APIRouter(prefix="/alerts", tags=["Alerts"])


@router.post("/broadcast", response_model=BroadcastAlertResponse, status_code=status.HTTP_202_ACCEPTED)
async def send_broadcast_alert(
    payload: BroadcastAlertRequest,
    current_user: Student = Depends(require_roles(RoleEnum.STAROSTA, RoleEnum.ZAM)),
    db: AsyncSession = Depends(get_db),
):
    """
    Sends emergency or informational broadcast announcement to group and student DMs.
    """
    # Only Starosta can send CRITICAL alerts
    if payload.type == BroadcastTypeEnum.CRITICAL.value and current_user.role != RoleEnum.STAROSTA.value:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "title": "Запрещено",
                "detail": "Только староста может отправлять критические оповещения (@all + ЛС).",
            },
        )

    bcast_id, sent_count = await broadcaster_service.broadcast_alert(
        session=db, sender_id=current_user.id, broadcast_type=payload.type, title=payload.title, body=payload.body
    )

    return BroadcastAlertResponse(
        broadcast_id=bcast_id, queued_recipients=sent_count, channel_posted=True, status="SENT"
    )

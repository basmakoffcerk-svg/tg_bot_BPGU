from pydantic import BaseModel


class BroadcastAlertRequest(BaseModel):
    type: str  # CRITICAL or INFO
    title: str
    body: str


class BroadcastAlertResponse(BaseModel):
    broadcast_id: int
    queued_recipients: int
    channel_posted: bool
    status: str

"""
Emergency broadcasting and group notification schemas.
"""
from typing import Literal
from pydantic import BaseModel, Field


class BroadcastRequest(BaseModel):
    """Payload for POST /api/v1/alerts/broadcast."""
    type: str = Field(..., description="Severity level of the broadcast (CRITICAL, INFO)")
    title: str = Field(..., min_length=1, max_length=150, description="Announcement title")
    body: str = Field(..., min_length=1, max_length=4000, description="Message text")


class BroadcastResponse(BaseModel):
    """Response returned by POST /api/v1/alerts/broadcast (HTTP 202 Accepted)."""
    broadcast_id: int = Field(..., description="Broadcast history record ID")
    queued_recipients: int = Field(..., description="Number of recipients queued for message delivery")
    channel_posted: bool = Field(default=True, description="Whether message was dispatched to group chat")
    status: Literal["SENDING", "QUEUED"] = Field(default="SENDING", description="Delivery processing status")

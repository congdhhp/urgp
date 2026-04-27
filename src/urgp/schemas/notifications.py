"""Internal notification event schemas."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from urgp.models.enums import NotificationEventType


class NotificationRequest(BaseModel):
    """Internal message contract published to the notification queue."""

    manifest_id: uuid.UUID
    build_id: str = Field(..., min_length=1, max_length=255)
    product_id: str = Field(..., min_length=1, max_length=255)
    event_type: NotificationEventType
    triggered_at: datetime
    trigger_source: str = Field(..., min_length=1, max_length=255)


from datetime import datetime, timezone
from pydantic import BaseModel, Field


class EventCreate(BaseModel):
    event_name: str
    user_id: str
    properties: dict = {}
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
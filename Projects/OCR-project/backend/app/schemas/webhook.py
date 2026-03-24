import uuid
from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, field_validator


class WebhookCreate(BaseModel):
    name: str
    url: str
    secret: str
    events: List[str]

    @field_validator("url")
    @classmethod
    def url_must_be_https(cls, v: str) -> str:
        if not v.startswith("https://"):
            raise ValueError("Webhook URL must use HTTPS")
        return v


class WebhookUpdate(BaseModel):
    name: Optional[str] = None
    url: Optional[str] = None
    events: Optional[List[str]] = None
    is_active: Optional[bool] = None


class WebhookResponse(BaseModel):
    id: uuid.UUID
    name: str
    url: str
    events: List[str]
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class DeliveryResponse(BaseModel):
    id: uuid.UUID
    attempt_count: int
    last_status: Optional[int]
    last_error: Optional[str]
    delivered_at: Optional[datetime]
    created_at: datetime

    model_config = {"from_attributes": True}

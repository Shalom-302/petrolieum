# app/plugins/webhooks/schemas.py

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any  # Import Any from typing

class WebhookCreate(BaseModel):
    name: str
    event: str
    url: str
    secret: Optional[str] = None
    is_enabled: bool = True
    config: Dict[str, Any] = Field(default_factory=dict)  # Use Any instead of any

class WebhookUpdate(BaseModel):
    name: Optional[str] = None
    event: Optional[str] = None
    url: Optional[str] = None
    secret: Optional[str] = None
    is_enabled: Optional[bool] = None
    config: Optional[Dict[str, Any]] = None  # Use Any instead of any
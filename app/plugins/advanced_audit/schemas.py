# app/plugins/advanced_audit/schemas.py

from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, Dict

class AuditLogCreate(BaseModel):
    user_id: Optional[int] = None
    action: str
    resource: str
    details: Optional[str] = None

class AuditLogUpdate(BaseModel):
    user_id: Optional[int] = None
    action: str
    resource: str
    details: Optional[str] = None


class AuditLogOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    action: str
    resource: str
    details: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

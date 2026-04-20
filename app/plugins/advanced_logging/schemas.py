# app/plugins/advanced_logging/schemas.py
from pydantic import BaseModel
from typing import Optional, Dict

class LogEntryCreate(BaseModel):
    level: str
    message: str
    labels: Optional[Dict[str, str]] = None

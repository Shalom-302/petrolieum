# app/plugins/advanced_scheduler/schemas.py

from pydantic import BaseModel, Field
from typing import Dict, Any

class JobCreateSchema(BaseModel):
    name: str
    cron_expr: str
    task_name: str  # references existing Celery/APS function
    args: Dict[str, Any] = Field(default_factory=dict)

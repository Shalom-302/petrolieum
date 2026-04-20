# app/plugins/advanced_audit/main.py

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import Any
from .models import AuditLog
from .schemas import AuditLogCreate, AuditLogUpdate, AuditLogOut
from app.crud_base import create_crud_router
from app.core.security import get_current_user
from app.casbin_setup import get_casbin_enforcer
from app.core.db import get_db

# Instantiate CRUD router for the 'post' resource
get_router = create_crud_router(
    model=AuditLog,
    schema_create=AuditLogCreate,
    schema_update=AuditLogUpdate,
    schema_out=AuditLogOut,
    resource_name="audit_logs",
    exclude_routes=[]  # Exclude routes dynamically, e.g., ["create", "list", "get"]
)


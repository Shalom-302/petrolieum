"""
Admin routes for agencies management using CRUD base.
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from uuid import UUID
import logging

from app.models.test import  Test
from app.schemas.test import (
    TestCreate,
    TestUpdate,
    TestInDB
)

from app.crud_base import create_crud_router

logger = logging.getLogger(__name__)

# Instantiate CRUD router for test sites
test_site_router = create_crud_router(
    model=Test,
    schema_create=TestCreate,
    schema_update=TestUpdate,
    schema_out=TestInDB,
    resource_name="tests",
    exclude_routes=[]
)



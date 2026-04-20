"""
Default test schema
"""
from typing import Optional
from pydantic import BaseModel
from uuid import UUID

# Base Agency Site Schema
class TestBase(BaseModel):
    name: str
    description: Optional[str] = None

class TestCreate(TestBase):
    pass


class TestUpdate(TestBase):
    pass


class TestInDB(TestBase):
    id: UUID
    pass

    class Config:
        from_attributes = True


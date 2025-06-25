from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class GroupBase(BaseModel):
    group_name: str
    group_description: Optional[str] = None


class GroupCreate(GroupBase):
    pass


class GroupUpdate(BaseModel):
    group_name: Optional[str] = None
    group_description: Optional[str] = None


class GroupResponse(GroupBase):
    group_uuid: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

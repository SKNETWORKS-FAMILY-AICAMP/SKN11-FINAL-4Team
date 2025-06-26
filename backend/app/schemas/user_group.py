from pydantic import BaseModel
from typing import Optional


class UserGroupCreate(BaseModel):
    user_uuid: str
    group_uuid: str


class UserGroupResponse(BaseModel):
    user_uuid: str
    group_uuid: str

    class Config:
        from_attributes = True

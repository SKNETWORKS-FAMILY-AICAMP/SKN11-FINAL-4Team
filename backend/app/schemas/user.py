from pydantic import BaseModel, EmailStr
from typing import List, Optional
from datetime import datetime


# User 스키마
class UserBase(BaseModel):
    provider_id: str
    provider: str
    user_name: str
    email: EmailStr


class UserCreate(UserBase):
    pass


class UserUpdate(BaseModel):
    user_name: Optional[str] = None
    email: Optional[EmailStr] = None


class User(UserBase):
    user_id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# Group 스키마
class GroupBase(BaseModel):
    group_name: str
    group_description: Optional[str] = None


class GroupCreate(GroupBase):
    pass


class GroupUpdate(BaseModel):
    group_name: Optional[str] = None
    group_description: Optional[str] = None


class Group(GroupBase):
    group_id: int
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class GroupWithUsers(Group):
    users: List[User] = []

    class Config:
        from_attributes = True


# HFToken 스키마
class HFTokenManageBase(BaseModel):
    group_id: int
    hf_token_value: str
    hf_token_nickname: str
    hf_user_name: str


class HFTokenManageCreate(HFTokenManageBase):
    pass


class HFTokenManageUpdate(BaseModel):
    hf_token_value: Optional[str] = None
    hf_token_nickname: Optional[str] = None
    hf_user_name: Optional[str] = None


class HFTokenManage(HFTokenManageBase):
    hf_manage_id: str
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


# SystemLog 스키마
class SystemLogBase(BaseModel):
    user_id: str
    log_type: int
    log_content: str


class SystemLogCreate(SystemLogBase):
    pass


class SystemLog(SystemLogBase):
    log_id: str
    created_at: Optional[str] = None

    class Config:
        from_attributes = True

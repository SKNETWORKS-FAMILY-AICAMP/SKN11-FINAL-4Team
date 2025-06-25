from pydantic import BaseModel, EmailStr
from typing import Optional
from datetime import datetime


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


class UserResponse(UserBase):
    user_uuid: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class HFTokenBase(BaseModel):
    hf_token_value: str
    hf_token_nickname: str
    hf_user_name: str


class HFTokenCreate(HFTokenBase):
    group_uuid: Optional[str] = None


class HFTokenUpdate(BaseModel):
    group_uuid: Optional[str] = None
    hf_token_value: Optional[str] = None
    hf_token_nickname: Optional[str] = None
    hf_user_name: Optional[str] = None


class HFTokenResponse(HFTokenBase):
    hf_manage_uuid: str
    group_uuid: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

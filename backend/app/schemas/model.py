from pydantic import BaseModel
from typing import Optional
from datetime import datetime


class ModelBase(BaseModel):
    group_uuid: str
    mbti_id: int
    model_name: str
    model_description: Optional[str] = None
    model_personality: str
    model_speaks: str
    model_repo: str
    image_url: Optional[str] = None
    model_status: int = 0
    model_data_url: Optional[str] = None


class ModelCreate(ModelBase):
    pass


class ModelUpdate(BaseModel):
    model_name: Optional[str] = None
    model_description: Optional[str] = None
    model_personality: Optional[str] = None
    model_speaks: Optional[str] = None
    model_repo: Optional[str] = None
    image_url: Optional[str] = None
    model_status: Optional[int] = None
    model_data_url: Optional[str] = None


class ModelResponse(ModelBase):
    model_uuid: str
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True

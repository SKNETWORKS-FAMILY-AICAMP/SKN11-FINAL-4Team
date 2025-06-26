from pydantic import BaseModel
from typing import Optional


class MBTIResponse(BaseModel):
    mbti_id: int
    mbti_name: str
    mbti_chara: str
    mbti_speaks: str
    mbti_data_url: str

    class Config:
        from_attributes = True


class MBTICreate(BaseModel):
    mbti_name: str
    mbti_chara: str
    mbti_speaks: str
    mbti_data_url: str


class MBTIUpdate(BaseModel):
    mbti_name: Optional[str] = None
    mbti_chara: Optional[str] = None
    mbti_speaks: Optional[str] = None
    mbti_data_url: Optional[str] = None

from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime


class BoardBase(BaseModel):
    group_uuid: str
    model_uuid: str
    board_topic: str
    board_description: Optional[str] = None
    board_platform: int
    board_hash_tag: Optional[List[str]] = None
    reservation_at: Optional[datetime] = None
    board_status: int
    image_url: Optional[List[str]] = None


class BoardCreate(BoardBase):
    pass


class BoardUpdate(BaseModel):
    board_topic: Optional[str] = None
    board_description: Optional[str] = None
    board_platform: Optional[int] = None
    board_hash_tag: Optional[List[str]] = None
    reservation_at: Optional[datetime] = None
    board_status: Optional[int] = None
    image_url: Optional[List[str]] = None


class BoardResponse(BoardBase):
    board_uuid: str
    created_at: datetime
    updated_at: datetime
    pulished_at: Optional[datetime] = None

    class Config:
        from_attributes = True

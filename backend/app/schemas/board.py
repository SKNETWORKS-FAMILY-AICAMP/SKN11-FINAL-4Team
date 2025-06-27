from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.schemas.base import BaseSchema, TimestampSchema


# Board 스키마
class BoardBase(BaseModel):
    influencer_id: str
    user_id: str
    group_id: int
    board_topic: str
    board_description: Optional[str] = None
    board_platform: int
    board_hash_tag: Optional[str] = None
    board_status: int = 0
    image_url: str
    reservation_at: Optional[datetime] = None
    pulished_at: Optional[datetime] = None


class BoardCreate(BoardBase):
    pass


class BoardUpdate(BaseModel):
    board_topic: Optional[str] = None
    board_description: Optional[str] = None
    board_platform: Optional[int] = None
    board_hash_tag: Optional[str] = None
    board_status: Optional[int] = None
    image_url: Optional[str] = None
    reservation_at: Optional[datetime] = None
    pulished_at: Optional[datetime] = None


class Board(BoardBase, TimestampSchema):
    board_id: str


class BoardWithInfluencer(Board):
    influencer_name: Optional[str] = None

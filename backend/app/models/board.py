from sqlalchemy import Column, String, DateTime, Text, Integer, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class Board(Base):
    __tablename__ = "BOARD"

    board_uuid = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    group_uuid = Column(String(36), ForeignKey("GROUP.group_uuid"), nullable=False)
    model_uuid = Column(String(36), ForeignKey("ML.model_uuid"), nullable=False)
    board_topic = Column(String(100), nullable=False)
    board_description = Column(Text, nullable=True)
    board_platform = Column(Integer, nullable=False)
    board_hash_tag = Column(JSON, nullable=True)
    reservation_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
    board_status = Column(Integer, nullable=False)
    pulished_at = Column(DateTime, nullable=True)
    image_url = Column(JSON, nullable=True)

    # Relationships
    group = relationship("Group", back_populates="boards")
    model = relationship("ML", back_populates="boards")

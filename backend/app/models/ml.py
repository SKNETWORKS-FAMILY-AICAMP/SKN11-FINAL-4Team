from sqlalchemy import Column, String, DateTime, Text, Integer, ForeignKey, Boolean
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class ML(Base):
    __tablename__ = "ML"

    model_uuid = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    group_uuid = Column(String(36), ForeignKey("GROUP.group_uuid"), nullable=False)
    mbti_id = Column(Integer, ForeignKey("MODEL_MBTI.mbti_id"), nullable=False)
    model_name = Column(String(100), nullable=False, unique=True)
    model_description = Column(Text, nullable=True)
    model_personality = Column(String(50), nullable=False)
    model_speaks = Column(String(50), nullable=False)
    model_repo = Column(String(255), nullable=False)
    image_url = Column(String(255), nullable=True)
    model_status = Column(Integer, nullable=False, default=0)  # 0: 학습 중, 1: 사용가능
    model_data_url = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )

    # Relationships
    group = relationship("Group", back_populates="models")
    mbti = relationship("ModelMBTI", back_populates="models")
    boards = relationship("Board", back_populates="model")
    apis = relationship("MLAPI", back_populates="model")

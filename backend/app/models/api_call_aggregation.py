from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class APICallAggregation(Base):
    __tablename__ = "API_CALL_AGGREGATION"

    api_call_uuid = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    api_uuid = Column(String(36), ForeignKey("ML_API.api_uuid"), nullable=False)
    model_uuid = Column(String(36), ForeignKey("ML.model_uuid"), nullable=False)
    group_uuid = Column(String(36), ForeignKey("GROUP.group_uuid"), nullable=False)
    daily_call_count = Column(Integer, nullable=False, comment="일일 API 호출 횟수")
    created_at = Column(
        DateTime, nullable=False, server_default=func.now(), comment="집계 데이터 생성일"
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="집계 데이터 수정일",
    )

    # Relationships
    api = relationship("MLAPI")
    model = relationship("ML")
    group = relationship("Group")

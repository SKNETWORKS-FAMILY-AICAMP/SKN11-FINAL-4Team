from sqlalchemy import Column, String, DateTime, Text, Integer, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class MLAPI(Base):
    __tablename__ = "ML_API"

    api_uuid = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    model_uuid = Column(
        String(36), ForeignKey("ML.model_uuid", ondelete="CASCADE"), nullable=False
    )
    group_uuid = Column(String(36), ForeignKey("GROUP.group_uuid"), nullable=False)
    api_value = Column(String(255), nullable=False, comment="API 키 값")
    created_at = Column(
        DateTime, nullable=False, server_default=func.now(), comment="API 생성일"
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="API 수정일",
    )

    # Relationships
    model = relationship("ML", back_populates="apis")
    group = relationship("Group")

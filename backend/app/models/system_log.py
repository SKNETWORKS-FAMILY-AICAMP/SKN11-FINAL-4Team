from sqlalchemy import Column, String, DateTime, Integer, ForeignKey, JSON
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class SystemLog(Base):
    __tablename__ = "SYSTEM_LOG"

    log_uuid = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_uuid = Column(String(36), ForeignKey("USER.user_uuid"), nullable=False)
    log_type = Column(Integer, nullable=False, comment="로그 유형")
    log_content = Column(JSON, nullable=False, comment="로그 내용")
    created_date = Column(
        DateTime, nullable=False, server_default=func.now(), comment="로그 생성일시"
    )

    # Relationships
    user = relationship("User")

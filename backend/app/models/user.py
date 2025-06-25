from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.sql import func
from app.database import Base
import uuid


class User(Base):
    __tablename__ = "USER"

    user_uuid = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    provider_id = Column(
        String(20), nullable=False, comment="소셜 로그인 제공자별 사용자 ID"
    )
    provider = Column(String(20), nullable=False, comment="소셜 로그인 제공자 구분")
    user_name = Column(String(20), nullable=False, comment="사용자 이름")
    email = Column(String(50), nullable=False, comment="사용자 이메일")
    created_at = Column(
        DateTime, nullable=False, server_default=func.now(), comment="사용자 등록일시"
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="사용자 정보 수정일시",
    )

from sqlalchemy import Column, String, DateTime, Text, Integer, ForeignKey
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class HFTokenManage(Base):
    __tablename__ = "HF_TOKEN_MANAGE"

    hf_manage_uuid = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    group_uuid = Column(String(36), ForeignKey("GROUP.group_uuid"), nullable=False)
    hf_token_value = Column(Text, nullable=False, comment="허깅페이스 토큰 값")
    hf_token_nickname = Column(String(100), nullable=False, comment="허깅페이스 토큰 별칭")
    hf_user_name = Column(String(50), nullable=False, comment="허깅페이스 사용자명")
    created_at = Column(
        DateTime, nullable=False, server_default=func.now(), comment="토큰 생성일시"
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="토큰 수정일시",
    )

    # Relationships
    group = relationship("Group")

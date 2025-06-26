from sqlalchemy import Column, String, DateTime, Text
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from app.database import Base
import uuid


class Group(Base):
    __tablename__ = "GROUP"

    group_uuid = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    group_name = Column(String(100), nullable=False, comment="그룹 이름")
    group_description = Column(Text, nullable=True, comment="그룹 설명")
    created_at = Column(
        DateTime, nullable=False, server_default=func.now(), comment="그룹 생성일시"
    )
    updated_at = Column(
        DateTime,
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
        comment="그룹 수정일시",
    )

    # Relationships
    models = relationship("ML", back_populates="group", cascade="all, delete-orphan")
    boards = relationship("Board", back_populates="group", cascade="all, delete-orphan")
    apis = relationship("MLAPI", back_populates="group", cascade="all, delete-orphan")
    hf_tokens = relationship(
        "HFTokenManage", back_populates="group", cascade="all, delete-orphan"
    )
    user_groups = relationship(
        "UserGroup", back_populates="group", cascade="all, delete-orphan"
    )

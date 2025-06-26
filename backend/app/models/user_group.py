from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base


class UserGroup(Base):
    __tablename__ = "USER_GROUP"

    user_uuid = Column(String(36), ForeignKey("USER.user_uuid"), primary_key=True)
    group_uuid = Column(String(36), ForeignKey("GROUP.group_uuid"), primary_key=True)

    # Relationships
    user = relationship("User", back_populates="user_groups")
    group = relationship("Group", back_populates="user_groups")

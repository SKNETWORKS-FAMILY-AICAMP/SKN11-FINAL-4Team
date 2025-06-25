from sqlalchemy import Column, Integer, String, Text
from sqlalchemy.orm import relationship
from app.database import Base


class ModelMBTI(Base):
    __tablename__ = "MODEL_MBTI"

    mbti_id = Column(Integer, primary_key=True, autoincrement=True)
    mbti_name = Column(String(100), nullable=False)
    mbti_chara = Column(String(255), nullable=False)
    mbti_speaks = Column(Text, nullable=False)
    mbti_data_url = Column(String(255), nullable=False)

    # Relationships
    models = relationship("ML", back_populates="mbti")

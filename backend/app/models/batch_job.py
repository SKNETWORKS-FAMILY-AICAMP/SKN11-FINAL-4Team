#!/usr/bin/env python3
"""
배치 작업 관리용 데이터베이스 모델
"""

from sqlalchemy import Column, String, Integer, DateTime, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime

from app.database import Base


class BatchJob(Base):
    """OpenAI 배치 작업 관리 테이블"""
    __tablename__ = "batch_jobs"
    
    # 기본 키
    id = Column(String, primary_key=True)  # batch_id를 기본키로 사용
    
    # 작업 정보
    task_id = Column(String, unique=True, nullable=False, index=True)
    influencer_id = Column(String, nullable=False, index=True)
    openai_batch_id = Column(String, unique=True, nullable=False, index=True)
    
    # 상태 정보
    status = Column(String, nullable=False, default="pending")  # pending, processing, completed, failed
    total_qa_pairs = Column(Integer, default=2000)
    generated_qa_pairs = Column(Integer, default=0)
    
    # 결과 정보
    input_file_id = Column(String, nullable=True)
    output_file_id = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)
    
    # S3 업로드 정보
    s3_qa_file_url = Column(String, nullable=True)
    s3_processed_file_url = Column(String, nullable=True)
    
    # 처리 플래그
    is_processed = Column(Boolean, default=False)  # 결과 처리 완료 여부
    is_uploaded_to_s3 = Column(Boolean, default=False)  # S3 업로드 완료 여부
    is_finetuning_started = Column(Boolean, default=False)  # 파인튜닝 시작 여부
    
    # 타임스탬프
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    completed_at = Column(DateTime, nullable=True)
    
    def __repr__(self):
        return f"<BatchJob(task_id='{self.task_id}', status='{self.status}', influencer_id='{self.influencer_id}')>"
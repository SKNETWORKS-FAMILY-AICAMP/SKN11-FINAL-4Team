#!/usr/bin/env python3
"""
배치 작업 관리 서비스
DB 기반으로 배치 작업 상태를 관리합니다.
"""

import os
from typing import List, Optional, Dict
from sqlalchemy.orm import Session
from datetime import datetime

from app.models.batch_job import BatchJob


class BatchJobService:
    """배치 작업 DB 관리 서비스"""
    
    def create_batch_job(
        self, 
        db: Session, 
        task_id: str, 
        influencer_id: str, 
        openai_batch_id: str,
        input_file_id: str = None
    ) -> BatchJob:
        """새 배치 작업 생성"""
        batch_job = BatchJob(
            id=openai_batch_id,  # batch_id를 primary key로 사용
            task_id=task_id,
            influencer_id=influencer_id,
            openai_batch_id=openai_batch_id,
            input_file_id=input_file_id,
            status="pending"
        )
        
        db.add(batch_job)
        db.commit()
        db.refresh(batch_job)
        
        print(f"✅ 배치 작업 DB에 저장: task_id={task_id}, batch_id={openai_batch_id}")
        return batch_job
    
    def get_batch_job_by_task_id(self, db: Session, task_id: str) -> Optional[BatchJob]:
        """Task ID로 배치 작업 조회"""
        return db.query(BatchJob).filter(BatchJob.task_id == task_id).first()
    
    def get_batch_job_by_batch_id(self, db: Session, batch_id: str) -> Optional[BatchJob]:
        """Batch ID로 배치 작업 조회"""
        return db.query(BatchJob).filter(BatchJob.openai_batch_id == batch_id).first()
    
    def get_pending_batch_jobs(self, db: Session) -> List[BatchJob]:
        """대기 중인 배치 작업 목록 조회"""
        return db.query(BatchJob).filter(
            BatchJob.status.in_(["pending", "processing"])
        ).all()
    
    def update_batch_status(
        self, 
        db: Session, 
        batch_id: str, 
        status: str,
        output_file_id: str = None,
        error_message: str = None,
        generated_qa_pairs: int = None
    ) -> Optional[BatchJob]:
        """배치 작업 상태 업데이트"""
        batch_job = self.get_batch_job_by_batch_id(db, batch_id)
        if not batch_job:
            return None
        
        batch_job.status = status
        batch_job.updated_at = datetime.now()
        
        if output_file_id:
            batch_job.output_file_id = output_file_id
        
        if error_message:
            batch_job.error_message = error_message
        
        if generated_qa_pairs is not None:
            batch_job.generated_qa_pairs = generated_qa_pairs
        
        if status == "completed":
            batch_job.completed_at = datetime.now()
        
        db.commit()
        db.refresh(batch_job)
        
        print(f"📊 배치 상태 업데이트: batch_id={batch_id}, status={status}")
        return batch_job
    
    def mark_processed(
        self, 
        db: Session, 
        task_id: str, 
        s3_qa_file_url: str = None,
        s3_processed_file_url: str = None
    ) -> Optional[BatchJob]:
        """결과 처리 완료 표시"""
        batch_job = self.get_batch_job_by_task_id(db, task_id)
        if not batch_job:
            return None
        
        batch_job.is_processed = True
        batch_job.updated_at = datetime.now()
        
        if s3_qa_file_url:
            batch_job.s3_qa_file_url = s3_qa_file_url
        
        if s3_processed_file_url:
            batch_job.s3_processed_file_url = s3_processed_file_url
        
        db.commit()
        db.refresh(batch_job)
        
        print(f"✅ 결과 처리 완료 표시: task_id={task_id}")
        return batch_job
    
    def mark_uploaded_to_s3(self, db: Session, task_id: str) -> Optional[BatchJob]:
        """S3 업로드 완료 표시"""
        batch_job = self.get_batch_job_by_task_id(db, task_id)
        if not batch_job:
            return None
        
        batch_job.is_uploaded_to_s3 = True
        batch_job.updated_at = datetime.now()
        
        db.commit()
        db.refresh(batch_job)
        
        print(f"📤 S3 업로드 완료 표시: task_id={task_id}")
        return batch_job
    
    def mark_finetuning_started(self, db: Session, task_id: str) -> Optional[BatchJob]:
        """파인튜닝 시작 표시"""
        batch_job = self.get_batch_job_by_task_id(db, task_id)
        if not batch_job:
            return None
        
        batch_job.is_finetuning_started = True
        batch_job.updated_at = datetime.now()
        
        db.commit()
        db.refresh(batch_job)
        
        print(f"🧠 파인튜닝 시작 표시: task_id={task_id}")
        return batch_job
    
    def delete_completed_batch_job(self, db: Session, task_id: str) -> bool:
        """완료된 배치 작업 삭제"""
        batch_job = self.get_batch_job_by_task_id(db, task_id)
        if not batch_job:
            return False
        
        # 완전히 처리된 작업만 삭제
        if (batch_job.status == "completed" and 
            batch_job.is_processed and 
            batch_job.is_uploaded_to_s3 and 
            batch_job.is_finetuning_started):
            
            db.delete(batch_job)
            db.commit()
            
            print(f"🗑️ 완료된 배치 작업 삭제: task_id={task_id}")
            return True
        
        return False
    
    def cleanup_old_failed_jobs(self, db: Session, days_old: int = 7) -> int:
        """오래된 실패 작업 정리"""
        from datetime import timedelta
        cutoff_date = datetime.now() - timedelta(days=days_old)
        
        old_failed_jobs = db.query(BatchJob).filter(
            BatchJob.status == "failed",
            BatchJob.updated_at < cutoff_date
        ).all()
        
        count = len(old_failed_jobs)
        for job in old_failed_jobs:
            db.delete(job)
        
        db.commit()
        
        if count > 0:
            print(f"🗑️ {count}개의 오래된 실패 작업 정리 완료")
        
        return count
    
    def get_all_batch_jobs(self, db: Session) -> List[BatchJob]:
        """모든 배치 작업 조회 (관리자용)"""
        return db.query(BatchJob).order_by(BatchJob.created_at.desc()).all()


# 글로벌 배치 작업 서비스 인스턴스
batch_job_service = BatchJobService()


def get_batch_job_service() -> BatchJobService:
    """배치 작업 서비스 의존성 주입"""
    return batch_job_service
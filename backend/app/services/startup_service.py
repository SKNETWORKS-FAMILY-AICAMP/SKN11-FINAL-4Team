#!/usr/bin/env python3
"""
애플리케이션 시작시 실행되는 서비스
QA 데이터가 있지만 파인튜닝이 시작되지 않은 작업들을 자동으로 처리
"""

import asyncio
import logging
from typing import List
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.batch_job_service import get_batch_job_service
from app.services.finetuning_service import get_finetuning_service
from app.models.batch_job import BatchJob

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StartupService:
    """애플리케이션 시작시 실행되는 서비스"""
    
    def __init__(self):
        self.batch_service = get_batch_job_service()
        self.finetuning_service = get_finetuning_service()
    
    async def check_and_restart_finetuning(self) -> int:
        """
        QA 데이터가 업로드되었지만 파인튜닝이 시작되지 않은 작업들을 찾아 자동 시작
        Returns:
            재시작된 파인튜닝 작업 수
        """
        try:
            logger.info("🔍 시작시 파인튜닝 재시작 가능 작업 검색 중...")
            
            # 데이터베이스 세션 획득
            db: Session = next(get_db())
            
            try:
                # QA 완료되었지만 파인튜닝 시작 안된 작업들 찾기
                restart_candidates = db.query(BatchJob).filter(
                    BatchJob.status == "completed",  # QA 생성 완료
                    BatchJob.is_uploaded_to_s3 == True,  # S3 업로드 완료
                    BatchJob.is_finetuning_started == False,  # 파인튜닝 아직 시작 안됨
                    BatchJob.s3_qa_file_url.isnot(None)  # S3 URL 존재
                ).all()
                
                if not restart_candidates:
                    logger.info("✅ 재시작할 파인튜닝 작업이 없습니다")
                    return 0
                
                logger.info(f"🎯 재시작 대상 파인튜닝 작업 {len(restart_candidates)}개 발견")
                
                restarted_count = 0
                
                for batch_job in restart_candidates:
                    try:
                        logger.info(f"🚀 파인튜닝 자동 재시작: task_id={batch_job.task_id}, influencer_id={batch_job.influencer_id}")
                        
                        # 파인튜닝 시작
                        success = await self.finetuning_service.start_finetuning_for_influencer(
                            influencer_id=batch_job.influencer_id,
                            s3_qa_file_url=batch_job.s3_qa_file_url,
                            db=db
                        )
                        
                        if success:
                            # 파인튜닝 시작 표시
                            self.batch_service.mark_finetuning_started(db, batch_job.task_id)
                            restarted_count += 1
                            logger.info(f"✅ 파인튜닝 자동 재시작 완료: task_id={batch_job.task_id}")
                        else:
                            logger.warning(f"⚠️ 파인튜닝 자동 재시작 실패: task_id={batch_job.task_id}")
                    
                    except Exception as e:
                        logger.error(f"❌ 파인튜닝 재시작 중 오류: task_id={batch_job.task_id}, error={str(e)}")
                        continue
                
                if restarted_count > 0:
                    logger.info(f"🎉 총 {restarted_count}개의 파인튜닝 작업 자동 재시작 완료")
                else:
                    logger.warning("⚠️ 재시작 대상이 있었지만 모두 실패했습니다")
                
                return restarted_count
            
            finally:
                db.close()
        
        except Exception as e:
            logger.error(f"❌ 파인튜닝 재시작 검사 중 오류: {str(e)}", exc_info=True)
            return 0
    
    async def cleanup_old_batch_jobs(self) -> int:
        """오래된 배치 작업 정리"""
        try:
            logger.info("🧹 오래된 배치 작업 정리 중...")
            
            db: Session = next(get_db())
            
            try:
                # 7일 이상 된 실패 작업 정리
                cleaned_count = self.batch_service.cleanup_old_failed_jobs(db, days_old=7)
                
                if cleaned_count > 0:
                    logger.info(f"🗑️ {cleaned_count}개의 오래된 실패 작업 정리 완료")
                
                return cleaned_count
            
            finally:
                db.close()
        
        except Exception as e:
            logger.error(f"❌ 배치 작업 정리 중 오류: {str(e)}", exc_info=True)
            return 0
    
    async def run_startup_tasks(self):
        """시작시 실행할 모든 작업들"""
        logger.info("🚀 애플리케이션 시작시 작업 실행 중...")
        
        try:
            # 1. 파인튜닝 재시작 검사
            restarted_count = await self.check_and_restart_finetuning()
            
            # 2. 오래된 배치 작업 정리
            cleaned_count = await self.cleanup_old_batch_jobs()
            
            logger.info(f"✅ 시작시 작업 완료 - 재시작: {restarted_count}개, 정리: {cleaned_count}개")
            
        except Exception as e:
            logger.error(f"❌ 시작시 작업 실행 중 오류: {str(e)}", exc_info=True)


# 글로벌 시작시 서비스 인스턴스
startup_service = StartupService()


def get_startup_service() -> StartupService:
    """시작시 서비스 의존성 주입"""
    return startup_service


async def run_startup_tasks():
    """애플리케이션 시작시 실행할 작업들"""
    service = get_startup_service()
    await service.run_startup_tasks()
#!/usr/bin/env python3
"""
애플리케이션 시작시 실행되는 서비스
QA 데이터가 있지만 파인튜닝이 시작되지 않은 작업들을 자동으로 처리
"""

import asyncio
import logging
import os
from typing import List
from sqlalchemy.orm import Session
from datetime import datetime

from app.database import get_db
# batch_job_service 제거됨 - BatchKey 모델 직접 사용
from app.services.finetuning_service import get_finetuning_service
from app.models.influencer import BatchKey as BatchJob

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class StartupService:
    """애플리케이션 시작시 실행되는 서비스"""
    
    def __init__(self):
# batch_service 제거됨
        self.finetuning_service = get_finetuning_service()
    
    async def check_and_restart_finetuning(self) -> int:
        """
        QA 데이터가 업로드되었지만 파인튜닝이 시작되지 않은 작업들을 찾아 자동 시작
        Returns:
            재시작된 파인튜닝 작업 수
        """
        # 환경변수로 자동 파인튜닝 비활성화 확인
        auto_finetuning_enabled = os.getenv('AUTO_FINETUNING_ENABLED', 'true').lower() == 'true'
        
        if not auto_finetuning_enabled:
            logger.info("🔒 자동 파인튜닝이 비활성화되어 있습니다 (AUTO_FINETUNING_ENABLED=false)")
            return 0
        
        try:
            logger.info("🔍 시작시 서비스 실행...")
            db: Session = next(get_db())
            
            try:
                # 1. 진행 중이던 배치 작업 상태 확인 및 처리
                logger.info("🔍 진행 중이던 배치 작업 상태 확인 중...")
                in_progress_jobs = db.query(BatchJob).filter(
                    BatchJob.status.in_(['batch_submitted', 'batch_processing']),
                    BatchJob.openai_batch_id.isnot(None)
                ).all()

                if in_progress_jobs:
                    logger.info(f"🎯 처리 중이었던 작업 {len(in_progress_jobs)}개 발견")
                    from app.services.batch_monitor import BatchMonitor # 순환 참조 방지를 위해 여기서 import
                    monitor = BatchMonitor()
                    for job in in_progress_jobs:
                        await monitor.check_and_update_single_job(job, db)
                    db.commit()
                else:
                    logger.info("✅ 진행 중이던 배치 작업 없음")

                # 2. S3 업로드 누락 작업 처리
                logger.info("🔍 S3 업로드 누락 작업 검색 중...")
                upload_candidates = db.query(BatchJob).filter(
                    BatchJob.status == "completed",
                    BatchJob.is_uploaded_to_s3 == False,
                    BatchJob.output_file_id.isnot(None)
                ).all()

                if upload_candidates:
                    logger.info(f"🎯 S3 업로드 대상 {len(upload_candidates)}개 발견")
                    from app.services.s3_service import get_s3_service
                    from openai import OpenAI
                    import tempfile

                    s3_service = get_s3_service()
                    openai_client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

                    for job in upload_candidates:
                        tmp_file_path = None
                        try:
                            logger.info(f"⬇️ OpenAI 결과 다운로드 중: output_file_id={job.output_file_id}")
                            file_content = openai_client.files.content(job.output_file_id).read()

                            with tempfile.NamedTemporaryFile(delete=False, mode='wb', suffix=".jsonl") as tmp_file:
                                tmp_file.write(file_content)
                                tmp_file_path = tmp_file.name
                            
                            s3_key = f"influencers/{job.influencer_id}/qa_results/{job.task_id}/generated_qa_results.jsonl"
                            logger.info(f"⬆️ S3 업로드 중: {s3_key}")
                            s3_url = s3_service.upload_file(tmp_file_path, s3_key)

                            if s3_url:
                                job.s3_qa_file_url = s3_url
                                job.is_uploaded_to_s3 = True
                                job.updated_at = datetime.now()
                                logger.info(f"✅ S3 업로드 성공: {s3_url}")
                            else:
                                logger.error(f"❌ S3 업로드 실패: task_id={job.task_id}")

                        except Exception as e:
                            logger.error(f"❌ S3 업로드 처리 중 오류: task_id={job.task_id}, error={e}")
                        finally:
                            if tmp_file_path and os.path.exists(tmp_file_path):
                                os.remove(tmp_file_path)
                    
                    db.commit()
                else:
                    logger.info("✅ S3 업로드 누락 작업 없음")

                # 3. 파인튜닝 재시작 대상 검색
                logger.info("🔍 파인튜닝 재시작 대상 검색...")
                restart_candidates = db.query(BatchJob).filter(
                    BatchJob.status == "completed",
                    BatchJob.is_uploaded_to_s3 == True,
                    BatchJob.is_finetuning_started == False,
                    BatchJob.s3_qa_file_url.isnot(None)
                ).all()
                
                if not restart_candidates:
                    logger.info("✅ 재시작할 파인튜닝 작업이 없습니다")
                    return 0
                
                logger.info(f"🎯 재시작 대상 파인튜닝 작업 {len(restart_candidates)}개 발견")
                
                restarted_count = 0
                
                for batch_job in restart_candidates:
                    try:
                        logger.info(f"🔍 파인튜닝 상태 확인: task_id={batch_job.task_id}, influencer_id={batch_job.influencer_id}")
                        
                        # 인플루언서 정보 조회
                        from app.services.influencers.crud import get_influencer_by_id
                        influencer_data = get_influencer_by_id(db, "system", batch_job.influencer_id)
                        
                        if not influencer_data:
                            logger.warning(f"⚠️ 인플루언서를 찾을 수 없음: {batch_job.influencer_id}")
                            continue
                        
                        # 이미 파인튜닝이 완료되었는지 확인
                        if self.finetuning_service.is_influencer_finetuned(influencer_data, db):
                            logger.info(f"✅ 이미 파인튜닝 완료됨: influencer_id={batch_job.influencer_id}")
                            # 파인튜닝 시작 플래그 업데이트 (중복 시작 방지)
                            batch_job.is_finetuning_started = True
                            db.commit()
                            continue
                        
                        logger.info(f"🚀 파인튜닝 자동 재시작: task_id={batch_job.task_id}, influencer_id={batch_job.influencer_id}")
                        
                        # 파인튜닝 시작
                        success = await self.finetuning_service.start_finetuning_for_influencer(
                            influencer_id=batch_job.influencer_id,
                            s3_qa_file_url=batch_job.s3_qa_file_url,
                            db=db
                        )
                        
                        if success:
                            # 파인튜닝 시작 표시 (BatchKey 모델 직접 사용)
                            batch_job.is_finetuning_started = True
                            batch_job.updated_at = datetime.now()
                            db.commit()
                            
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
                # 7일 이상 된 실패 작업 정리 (BatchKey 모델 직접 사용)
                from datetime import timedelta
                cutoff_date = datetime.now() - timedelta(days=7)
                
                old_failed_jobs = db.query(BatchJob).filter(
                    BatchJob.status == "failed",
                    BatchJob.updated_at < cutoff_date
                ).all()
                
                cleaned_count = len(old_failed_jobs)
                for job in old_failed_jobs:
                    db.delete(job)
                
                db.commit()
                
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
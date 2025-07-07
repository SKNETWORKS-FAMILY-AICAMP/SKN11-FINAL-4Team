#!/usr/bin/env python3
"""
OpenAI 배치 작업 모니터링 서비스
폴링 모드에서 주기적으로 배치 상태를 확인하고 완료된 작업을 처리합니다.
"""

import asyncio
import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.core.config import settings
from app.database import get_db
from app.models.influencer import BatchKey
from app.services.influencers.qa_generator import InfluencerQAGenerator
from app.services.finetuning_service import get_finetuning_service

logger = logging.getLogger(__name__)


class BatchMonitor:
    """OpenAI 배치 작업 모니터링 클래스"""
    
    def __init__(self):
        self.qa_generator = InfluencerQAGenerator()
        self.finetuning_service = get_finetuning_service()
        self.is_running = False
        self.monitor_task: Optional[asyncio.Task] = None
    
    async def start_monitoring(self):
        """모니터링 시작"""
        if settings.OPENAI_MONITORING_MODE != 'polling':
            logger.info("📢 폴링 모드가 아니므로 배치 모니터링을 시작하지 않습니다")
            return
        
        if self.is_running:
            logger.warning("⚠️ 배치 모니터링이 이미 실행 중입니다")
            return
        
        self.is_running = True
        logger.info(f"🔄 배치 모니터링 시작 - 간격: {settings.OPENAI_POLLING_INTERVAL_MINUTES}분")
        
        self.monitor_task = asyncio.create_task(self._monitor_loop())
    
    async def stop_monitoring(self):
        """모니터링 중지"""
        if not self.is_running:
            return
        
        self.is_running = False
        
        if self.monitor_task:
            self.monitor_task.cancel()
            try:
                await self.monitor_task
            except asyncio.CancelledError:
                pass
        
        logger.info("⏹️ 배치 모니터링이 중지되었습니다")
    
    async def _monitor_loop(self):
        """모니터링 루프"""
        while self.is_running:
            try:
                await self._check_batch_status()
                
                # 다음 체크까지 대기
                interval_seconds = settings.OPENAI_POLLING_INTERVAL_MINUTES * 60
                await asyncio.sleep(interval_seconds)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"❌ 배치 모니터링 중 오류 발생: {e}", exc_info=True)
                # 오류 발생 시 30초 후 재시도
                await asyncio.sleep(30)
    
    async def check_and_update_single_job(self, batch_key: BatchKey, db: Session):
        """개별 배치 작업의 현재 상태를 확인하고 DB를 업데이트"""
        try:
            if not batch_key.openai_batch_id:
                logger.warning(f"⚠️ OpenAI 배치 ID가 없음: {batch_key.batch_key_id}")
                return

            # OpenAI 배치 상태 확인
            batch_status = self.qa_generator.check_batch_status(batch_key.openai_batch_id)
            current_status = batch_status.get('status')
            logger.debug(f"📋 배치 {batch_key.batch_key_id} 현재 상태: {current_status}")

            # 상태에 따른 처리
            if current_status == 'completed':
                await self._handle_completed_batch(batch_key, batch_status, db)
            elif current_status == 'failed':
                await self._handle_failed_batch(batch_key, batch_status, db)
            elif current_status in ['validating', 'in_progress']:
                await self._handle_processing_batch(batch_key, db)
            else:
                logger.debug(f"📌 배치 {batch_key.batch_key_id}는 여전히 {current_status} 상태입니다")

        except Exception as e:
            logger.error(f"❌ 배치 {batch_key.batch_key_id} 처리 중 오류: {e}", exc_info=True)

    async def _check_batch_status(self):
        """모든 진행 중인 배치 작업 상태 확인"""
        logger.debug("🔍 배치 상태 확인 시작")
        
        db: Session = next(get_db())
        try:
            # 진행 중인 배치 작업 조회
            pending_batches = db.query(BatchKey).filter(
                BatchKey.status.in_(['pending', 'processing', 'batch_submitted', 'batch_processing'])
            ).all()
            
            if not pending_batches:
                logger.debug("📭 진행 중인 배치 작업이 없습니다")
                return
            
            logger.info(f"📊 {len(pending_batches)}개의 진행 중인 배치 작업 확인 중")
            
            for batch_key in pending_batches:
                await self.check_and_update_single_job(batch_key, db)
                
        finally:
            db.close()
    
    async def _handle_completed_batch(self, batch_key: BatchKey, batch_status: dict, db: Session):
        """완료된 배치 처리"""
        logger.info(f"✅ 배치 완료 감지: {batch_key.batch_key_id}")
        logger.info(f"📊 배치 상세 정보: task_id={batch_key.task_id}, influencer_id={batch_key.influencer_id}, openai_batch_id={batch_key.openai_batch_id}")
        
        try:
            # QA 생성 완료 처리
            logger.info(f"🔄 QA 생성 완료 처리 시작: task_id={batch_key.task_id}")
            success = self.qa_generator.complete_qa_generation(batch_key.task_id, db)
            
            if success:
                # 배치 상태 업데이트
                batch_key.status = 'completed'
                batch_key.completed_at = datetime.now()
                batch_key.is_processed = True
                batch_key.output_file_id = batch_status.get('output_file_id') # output_file_id 저장
                batch_key.is_uploaded_to_s3 = False # S3 업로드 필요 표시
                
                db.commit()
                
                logger.info(f"🎉 배치 {batch_key.batch_key_id} QA 생성 완료 처리됨")
                
                # 파인튜닝 시작 (AUTO_FINETUNING_ENABLED가 true인 경우)
                if settings.AUTO_FINETUNING_ENABLED:
                    logger.info(f"🚀 자동 파인튜닝 시작: batch_key_id={batch_key.batch_key_id}")
                    await self._start_finetuning(batch_key)
                else:
                    logger.info(f"⏸️ 자동 파인튜닝 비활성화됨: AUTO_FINETUNING_ENABLED={settings.AUTO_FINETUNING_ENABLED}")
                
            else:
                logger.error(f"❌ 배치 {batch_key.batch_key_id} QA 생성 완료 처리 실패")
                
        except Exception as e:
            logger.error(f"❌ 완료된 배치 {batch_key.batch_key_id} 처리 중 오류: {e}", exc_info=True)
    
    async def _handle_failed_batch(self, batch_key: BatchKey, batch_status: Dict, db: Session):
        """실패한 배치 처리"""
        logger.error(f"❌ 배치 실패 감지: {batch_key.batch_key_id}")
        
        batch_key.status = 'failed'
        batch_key.error_message = f"OpenAI 배치 작업 실패: {batch_status.get('status', 'Unknown error')}"
        batch_key.completed_at = datetime.now()
        
        db.commit()
        
        logger.error(f"💥 배치 {batch_key.batch_key_id} 실패로 표시됨")
    
    async def _handle_processing_batch(self, batch_key: BatchKey, db: Session):
        """진행 중인 배치 상태 업데이트"""
        if batch_key.status != 'batch_processing':
            batch_key.status = 'batch_processing'
            db.commit()
            logger.debug(f"🔄 배치 {batch_key.batch_key_id} 상태를 processing으로 업데이트")
    
    async def _start_finetuning(self, batch_key: BatchKey):
        """파인튜닝 시작"""
        try:
            if batch_key.is_finetuning_started:
                logger.info(f"ℹ️ 배치 {batch_key.batch_key_id}는 이미 파인튜닝이 시작됨")
                return
            
            logger.info(f"🚀 배치 {batch_key.batch_key_id}에 대한 파인튜닝 시작")
            
            # 파인튜닝 서비스 호출
            result = await self.finetuning_service.start_finetuning_for_influencer(
                batch_key.influencer_id
            )
            
            if result:
                # 파인튜닝 시작 플래그 업데이트
                db: Session = next(get_db())
                try:
                    batch_key.is_finetuning_started = True
                    db.commit()
                    logger.info(f"✅ 배치 {batch_key.batch_key_id} 파인튜닝 시작 완료")
                finally:
                    db.close()
            
        except Exception as e:
            logger.error(f"❌ 배치 {batch_key.batch_key_id} 파인튜닝 시작 실패: {e}", exc_info=True)


# 전역 모니터 인스턴스
batch_monitor = BatchMonitor()


async def start_batch_monitoring():
    """배치 모니터링 시작"""
    await batch_monitor.start_monitoring()


async def stop_batch_monitoring():
    """배치 모니터링 중지"""
    await batch_monitor.stop_monitoring()


def get_batch_monitor() -> BatchMonitor:
    """배치 모니터 의존성 주입"""
    return batch_monitor
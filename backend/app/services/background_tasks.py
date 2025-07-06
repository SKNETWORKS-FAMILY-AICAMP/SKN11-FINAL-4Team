"""
백그라운드 작업 관리 서비스
QA 생성 작업을 백그라운드에서 시작하는 간단한 서비스
"""

import asyncio
import logging
from typing import Dict

from app.services.influencers.qa_generator import InfluencerQAGenerator

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BackgroundTaskManager:
    def __init__(self):
        self.qa_generator = InfluencerQAGenerator()

    async def start_qa_generation_task(self, influencer_id: str):
        """
        인플루언서 QA 생성 백그라운드 작업 시작
        Args:
            influencer_id: 인플루언서 ID
        """
        try:
            logger.info(f"🎯 백그라운드: QA 생성 작업 시작 - influencer_id={influencer_id}")
            
            # 데이터베이스 세션 획득
            from app.database import get_db
            db = next(get_db())
            
            try:
                # QA 생성 작업 시작
                task_id = self.qa_generator.start_qa_generation(influencer_id, db)
                logger.info(f"✅ 백그라운드: QA 생성 작업 시작 완료 - task_id={task_id}")
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"❌ 백그라운드: QA 생성 작업 시작 실패 - influencer_id={influencer_id}, error={str(e)}", exc_info=True)


# 전역 백그라운드 작업 관리자 인스턴스
background_task_manager = BackgroundTaskManager()


def get_background_task_manager() -> BackgroundTaskManager:
    """백그라운드 작업 관리자 의존성 주입"""
    return background_task_manager


async def generate_influencer_qa_background(influencer_id: str):
    """인플루언서 QA 생성 백그라운드 작업 시작 함수"""
    logger.info(f"🚀 백그라운드 함수 호출 - influencer_id={influencer_id}")
    manager = get_background_task_manager()
    await manager.start_qa_generation_task(influencer_id)
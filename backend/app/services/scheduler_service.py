"""
게시글 예약 발행 스케줄러 서비스
"""
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session
from sqlalchemy import select, and_
from app.database import get_db
from app.models.board import Board

logger = logging.getLogger(__name__)


class SchedulerService:
    """게시글 예약 발행 스케줄러 서비스"""
    
    def __init__(self):
        self.scheduler = AsyncIOScheduler()
        self.is_running = False
    
    async def start(self):
        """스케줄러 시작"""
        try:
            logger.info("스케줄러 서비스 시작")
            self.scheduler.start()
            self.is_running = True
            
            # 기존 예약된 게시글 스케줄링
            await self.schedule_existing_posts()
            
            # 주기적으로 예약된 게시글 확인 (5분마다)
            self.scheduler.add_job(
                self.check_scheduled_posts,
                CronTrigger(minute='*/5'),
                id='check_scheduled_posts',
                replace_existing=True
            )
            
            logger.info("스케줄러 서비스 시작 완료")
            
        except Exception as e:
            logger.error(f"스케줄러 시작 실패: {str(e)}")
            raise
    
    async def stop(self):
        """스케줄러 중지"""
        try:
            logger.info("스케줄러 서비스 중지")
            self.scheduler.shutdown()
            self.is_running = False
            logger.info("스케줄러 서비스 중지 완료")
        except Exception as e:
            logger.error(f"스케줄러 중지 실패: {str(e)}")
    
    async def schedule_existing_posts(self):
        """기존 예약된 게시글들을 스케줄링"""
        try:
            db = next(get_db())
            try:
                # 예약 상태(board_status=2)이고 reservation_at이 설정된 게시글 조회
                scheduled_posts = db.query(Board).filter(
                    and_(
                        Board.board_status == 2,  # 예약 상태
                        Board.reservation_at.is_not(None),
                        Board.reservation_at > datetime.now()  # 미래 시간만
                    )
                ).all()
                
                for post in scheduled_posts:
                    await self.schedule_post(post.board_id, post.reservation_at)
                    
                logger.info(f"기존 예약된 게시글 {len(scheduled_posts)}개 스케줄링 완료")
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"기존 예약된 게시글 스케줄링 실패: {str(e)}")
    
    async def schedule_post(self, board_id: int, scheduled_time: datetime):
        """게시글 예약 발행 스케줄링"""
        try:
            job_id = f"publish_post_{board_id}"
            
            # 기존 스케줄이 있으면 제거
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
            
            # 새로운 스케줄 등록
            self.scheduler.add_job(
                self.publish_scheduled_post,
                DateTrigger(run_date=scheduled_time),
                args=[board_id],
                id=job_id,
                replace_existing=True
            )
            
            logger.info(f"게시글 {board_id} 예약 발행 스케줄링 완료: {scheduled_time}")
            
        except Exception as e:
            logger.error(f"게시글 {board_id} 스케줄링 실패: {str(e)}")
    
    async def cancel_scheduled_post(self, board_id: int):
        """게시글 예약 발행 취소"""
        try:
            job_id = f"publish_post_{board_id}"
            
            if self.scheduler.get_job(job_id):
                self.scheduler.remove_job(job_id)
                logger.info(f"게시글 {board_id} 예약 발행 취소 완료")
                return True
            else:
                logger.warning(f"게시글 {board_id} 스케줄이 존재하지 않음")
                return False
                
        except Exception as e:
            logger.error(f"게시글 {board_id} 예약 발행 취소 실패: {str(e)}")
            return False
    
    async def publish_scheduled_post(self, board_id: int):
        """예약된 게시글 발행"""
        try:
            db = next(get_db())
            try:
                # 게시글 조회
                post = db.query(Board).filter(Board.board_id == board_id).first()
                
                if not post:
                    logger.error(f"게시글 {board_id}를 찾을 수 없음")
                    return
                
                # 이미 발행된 게시글인지 확인
                if post.board_status == 3:  # 이미 발행됨
                    logger.warning(f"게시글 {board_id}는 이미 발행됨")
                    return
                
                # 게시글 상태를 발행됨(3)으로 변경
                post.board_status = 3
                post.pulished_at = datetime.now()
                
                db.commit()
                
                logger.info(f"게시글 {board_id} 예약 발행 완료")
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"게시글 {board_id} 예약 발행 실패: {str(e)}")
            # 실패 시 게시글 상태를 임시저장(1)으로 변경
            try:
                db = next(get_db())
                try:
                    post = db.query(Board).filter(Board.board_id == board_id).first()
                    
                    if post:
                        post.board_status = 1  # 임시저장으로 변경
                        db.commit()
                        logger.info(f"게시글 {board_id} 상태를 임시저장으로 변경")
                        
                finally:
                    db.close()
                        
            except Exception as e2:
                logger.error(f"게시글 {board_id} 상태 변경 실패: {str(e2)}")
    
    async def check_scheduled_posts(self):
        """예약된 게시글 상태 확인 (주기적 실행)"""
        try:
            db = next(get_db())
            try:
                # 예약 시간이 지났는데 아직 발행되지 않은 게시글 조회
                overdue_posts = db.query(Board).filter(
                    and_(
                        Board.board_status == 2,  # 예약 상태
                        Board.reservation_at.is_not(None),
                        Board.reservation_at <= datetime.now()  # 시간이 지난 것들
                    )
                ).all()
                
                for post in overdue_posts:
                    logger.warning(f"예약 시간이 지난 게시글 {post.board_id} 발견, 즉시 발행")
                    await self.publish_scheduled_post(post.board_id)
                
                if overdue_posts:
                    logger.info(f"지연된 예약 게시글 {len(overdue_posts)}개 발행 완료")
                    
            finally:
                db.close()
                    
        except Exception as e:
            logger.error(f"예약된 게시글 상태 확인 실패: {str(e)}")
    
    def get_scheduled_jobs(self) -> list:
        """현재 스케줄된 작업 목록 반환"""
        try:
            jobs = []
            for job in self.scheduler.get_jobs():
                if job.id.startswith('publish_post_'):
                    board_id = int(job.id.replace('publish_post_', ''))
                    jobs.append({
                        'board_id': board_id,
                        'scheduled_time': job.next_run_time,
                        'job_id': job.id
                    })
            return jobs
        except Exception as e:
            logger.error(f"스케줄된 작업 목록 조회 실패: {str(e)}")
            return []
    
    def get_scheduler_status(self) -> dict:
        """스케줄러 상태 반환"""
        return {
            'is_running': self.is_running,
            'scheduler_state': self.scheduler.state if self.scheduler else None,
            'job_count': len(self.scheduler.get_jobs()) if self.scheduler else 0
        }


# 전역 스케줄러 인스턴스
scheduler_service = SchedulerService()
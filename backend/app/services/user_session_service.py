"""
사용자 세션 서비스 - 간소화된 Pod 세션 관리

USER 테이블의 Pod 세션 컬럼들을 사용하여 
1 user = 1 RunPod 제한 및 세션 타임아웃 관리

"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from sqlalchemy.orm import selectinload
import logging

from app.models.user import User
from app.services.runpod_service import get_runpod_service
from app.core.config import settings

logger = logging.getLogger(__name__)

def ensure_timezone_aware(dt: Optional[datetime]) -> Optional[datetime]:
    """datetime이 타임존 정보를 갖도록 보장 (UTC 가정)"""
    if dt is None:
        return None
    if dt.tzinfo is None:
        # 타임존 정보가 없으면 UTC로 간주
        return dt.replace(tzinfo=timezone.utc)
    return dt

def safe_datetime_compare(dt1: Optional[datetime], dt2: Optional[datetime]) -> bool:
    """안전한 datetime 비교 (타임존 처리 포함)"""
    if dt1 is None or dt2 is None:
        return False
    return ensure_timezone_aware(dt1) > ensure_timezone_aware(dt2)


class UserSessionService:
    """
    사용자 세션 서비스 - USER 테이블 기반 Pod 세션 관리
    
    USER 테이블의 다음 컬럼들을 관리:
    - current_pod_id: 현재 활성 RunPod ID
    - pod_status: Pod 상태 (none, starting, ready, processing)
    - session_created_at: 세션 생성 시간
    - session_expires_at: 세션 만료 시간 (15분)
    - processing_expires_at: 처리 만료 시간 (10분)
    - total_generations: 총 이미지 생성 횟수
    """
    
    def __init__(self):
        self.runpod_service = get_runpod_service()
        logger.info("UserSessionService initialized")
    
    async def create_session(self, user_id: str, db: AsyncSession, background_tasks=None) -> bool:
        """
        사용자 페이지 진입시 세션 생성
        
        Args:
            user_id: 사용자 ID
            db: 데이터베이스 세션
            background_tasks: FastAPI 백그라운드 태스크
            
        Returns:
            bool: 세션 생성 요청 성공 여부
        """
        try:
            logger.info(f"사용자 {user_id}의 세션 생성 시작")
            
            # Pod 생성이 이미 진행 중인지 확인 (동시 요청 방지)
            if hasattr(self, f'_creating_pod_{user_id}'):
                logger.info(f"사용자 {user_id}의 Pod 생성이 이미 진행 중입니다. 요청을 무시합니다.")
                return True
            
            # 동시 요청 방지를 위해 사용자 레코드에 lock 설정
            logger.info(f"사용자 {user_id}의 데이터베이스 쿼리 실행")
            result = await db.execute(
                select(User).where(User.user_id == user_id).with_for_update()
            )
            user = result.scalar_one_or_none()
            logger.info(f"데이터베이스 쿼리 결과: {user is not None}")
            
            if not user:
                logger.error(f"사용자를 찾을 수 없음: {user_id}")
                return False

            logger.info(f"사용자 발견: {user.user_id}, 현재 Pod 상태: {user.pod_status}")

            # 활성 세션 재확인 (lock된 상태에서)
            if self._has_active_session(user):
                logger.info(f"사용자 {user_id}가 이미 활성 세션을 보유함")
                await self._update_session_activity(user, db)
                return True

            if user.current_pod_id:
                logger.info(f"사용자 {user_id}의 기존 세션 종료")
                await self._terminate_current_session(user, db, background_tasks)

            # 백그라운드에서 실제 Pod 생성 및 상태 업데이트
            logger.info(f"📌 사용자 {user_id}의 Pod 생성 백그라운드 작업 추가 시작")
            
            # WebSocket 환경에서는 asyncio.create_task 사용
            if background_tasks is None:
                logger.info(f"🔄 WebSocket 환경 감지 - asyncio.create_task 사용")
                task = asyncio.create_task(self._create_pod_and_update_db_async(user_id))
                logger.info(f"✅ asyncio 태스크 생성 완료: {task}")
            else:
                logger.info(f"📋 BackgroundTasks 객체 사용: {background_tasks}")
                background_tasks.add_task(self._create_pod_and_update_db_async, user_id)
                logger.info(f"✅ 백그라운드 태스크 추가 완료")

            # 먼저 DB에 starting 상태를 기록하여 즉각적인 피드백 제공
            now = datetime.now(timezone.utc)
            user.pod_status = "starting"
            user.session_created_at = now
            user.session_expires_at = now + timedelta(minutes=15)
            user.current_pod_id = "pending" # 임시 ID
            
            logger.info(f"사용자 {user_id}의 세션 생성 데이터베이스 커밋")
            await db.commit()
            
            logger.info(f"사용자 {user_id}의 세션 생성 작업 시작됨")
            return True

        except Exception as e:
            logger.error(f"사용자 {user_id}의 세션 생성 시작 실패: {e}", exc_info=True)
            try:
                await db.rollback()
            except:
                pass
            return False
    
    async def start_image_generation(self, user_id: str, db: AsyncSession) -> bool:
        """
        이미지 생성 시작 - 10분 타이머 시작
        
        Args:
            user_id: 사용자 ID
            db: 데이터베이스 세션
            
        Returns:
            bool: 시작 성공 여부
        """
        try:
            user = await self._get_user(user_id, db)
            if not user:
                logger.error(f"User not found: {user_id}")
                return False
            
            # 활성 세션 확인
            if not self._has_active_session(user):
                logger.error(f"No active session for user {user_id}")
                return False
            
            # Pod 상태 체크 - running, ready, processing 상태에서만 이미지 생성 가능
            allowed_statuses = ["ready", "running", "processing"]
            if user.pod_status not in allowed_statuses:
                logger.warning(f"Pod not available for image generation. User: {user_id}, status: {user.pod_status}, allowed: {allowed_statuses}")
                return False
            
            logger.info(f"Pod is available for image generation. User: {user_id}, status: {user.pod_status}")
            
            # processing 상태로 변경 및 10분 타이머 시작
            now = datetime.now(timezone.utc)
            processing_expires_at = now + timedelta(minutes=10)
            
            user.pod_status = "processing"
            user.processing_expires_at = processing_expires_at
            user.total_generations += 1
            
            await db.commit()
            
            logger.info(f"Started image generation for user {user_id}, expires: {processing_expires_at}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start image generation for user {user_id}: {e}")
            return False

    def start_image_generation_sync(self, user_id: str, db: Session) -> bool:
        """
        이미지 생성 시작 - 10분 타이머 시작 (동기)
        
        Args:
            user_id: 사용자 ID
            db: 데이터베이스 세션
            
        Returns:
            bool: 시작 성공 여부
        """
        try:
            result = db.execute(select(User).where(User.user_id == user_id))
            user = result.scalar_one_or_none()
            if not user:
                logger.error(f"User not found: {user_id}")
                return False
            
            # 활성 세션 확인
            if not self._has_active_session(user):
                logger.error(f"No active session for user {user_id}")
                return False
            
            # Pod 상태 체크 - running, ready, processing 상태에서만 이미지 생성 가능
            allowed_statuses = ["ready", "running", "processing"]
            if user.pod_status not in allowed_statuses:
                logger.warning(f"Pod not available for image generation. User: {user_id}, status: {user.pod_status}, allowed: {allowed_statuses}")
                return False
            
            logger.info(f"Pod is available for image generation. User: {user_id}, status: {user.pod_status}")
            
            # processing 상태로 변경 및 10분 타이머 시작
            now = datetime.now(timezone.utc)
            processing_expires_at = now + timedelta(minutes=10)
            
            user.pod_status = "processing"
            user.processing_expires_at = processing_expires_at
            user.total_generations += 1
            
            db.commit()
            
            logger.info(f"Started image generation for user {user_id}, expires: {processing_expires_at}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start image generation for user {user_id}: {e}")
            return False
    
    async def complete_image_generation(self, user_id: str, db: AsyncSession) -> bool:
        """
        이미지 생성 완료 - 상태를 ready로 리셋하고 10분 타이머 연장
        
        Args:
            user_id: 사용자 ID
            db: 데이터베이스 세션
            
        Returns:
            bool: 완료 처리 성공 여부
        """
        try:
            user = await self._get_user(user_id, db)
            if not user:
                logger.error(f"User not found: {user_id}")
                return False
            
            # processing 상태인지 확인
            if user.pod_status != "processing":
                logger.warning(f"User {user_id} is not in processing state: {user.pod_status}")
                return False
            
            # ready 상태로 변경, 처리 타이머 제거, 세션 타이머 10분 연장
            now = datetime.now(timezone.utc)
            new_session_expires = now + timedelta(minutes=10)
            
            user.pod_status = "ready"
            user.processing_expires_at = None
            user.session_expires_at = new_session_expires
            
            await db.commit()
            
            logger.info(f"Completed image generation for user {user_id}, session extended to: {new_session_expires}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to complete image generation for user {user_id}: {e}")
            return False
    
    async def get_session_status(self, user_id: str, db: AsyncSession) -> Optional[Dict[str, Any]]:
        """
        세션 상태 조회 (비동기)
        
        Args:
            user_id: 사용자 ID
            db: 데이터베이스 세션
            
        Returns:
            Dict: 세션 상태 정보 또는 None
        """
        try:
            user = await self._get_user(user_id, db)
            if not user:
                return None
            
            now = datetime.now(timezone.utc)
            
            # 세션이 없으면 None 반환
            if not user.current_pod_id or user.pod_status == "none":
                return None
            
            # Failed 상태인 Pod는 재확인 시도 (ComfyUI가 늦게 준비될 수 있음)
            if user.pod_status == "failed" and user.current_pod_id:
                logger.info(f"🔄 Failed 상태 Pod 재확인 시도: {user.current_pod_id}")
                
                # RunPod 상태 및 ComfyUI 응답 재확인
                try:
                    from app.services.runpod_service import get_runpod_service
                    runpod_service = get_runpod_service()
                    
                    # Pod 상태 확인
                    pod_status = await runpod_service.get_pod_status(user.current_pod_id)
                    
                    if pod_status.status == "RUNNING" and pod_status.endpoint_url:
                        # ComfyUI API 응답 확인 (더 강화된 체크)
                        if await runpod_service._check_comfyui_ready(pod_status.endpoint_url):
                            logger.info(f"✅ Failed 상태였던 Pod가 이제 준비됨: {user.current_pod_id}")
                            
                            # 상태를 ready로 업데이트하고 세션 시간 연장 (10분 추가)
                            user.pod_status = "ready"
                            user.session_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
                            user.processing_expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)
                            await db.commit()
                            
                            logger.info(f"🕐 Pod 복구로 인한 세션 시간 10분 연장: {user.current_pod_id}")
                        else:
                            logger.info(f"⚠️ Pod는 실행 중이지만 ComfyUI 아직 응답 없음: {user.current_pod_id}")
                    else:
                        logger.info(f"⚠️ Pod 상태 확인 결과: {pod_status.status}")
                        
                except Exception as recheck_error:
                    logger.warning(f"Failed Pod 재확인 중 오류: {recheck_error}")
                    # 재확인 실패해도 기존 로직 계속 진행
            
            # 만료 상태 확인 (타임존 안전 비교)
            session_expired = safe_datetime_compare(now, user.session_expires_at)
            processing_expired = safe_datetime_compare(now, user.processing_expires_at)
            
            # 만료된 세션은 자동 정리
            if session_expired or processing_expired:
                self._terminate_current_session(user, db)
                return None
            
            return {
                "pod_id": user.current_pod_id,
                "pod_status": user.pod_status,
                "session_created_at": user.session_created_at,
                "session_expires_at": user.session_expires_at,
                "processing_expires_at": user.processing_expires_at,
                "total_generations": user.total_generations,
                "session_remaining_seconds": int((ensure_timezone_aware(user.session_expires_at) - now).total_seconds()) if user.session_expires_at else None,
                "processing_remaining_seconds": int((ensure_timezone_aware(user.processing_expires_at) - now).total_seconds()) if user.processing_expires_at else None
            }
            
        except Exception as e:
            logger.error(f"Failed to get session status for user {user_id}: {e}")
            return None

    def get_session_status_sync(self, user_id: str, db: Session) -> Optional[Dict[str, Any]]:
        """
        세션 상태 조회 (동기)
        
        Args:
            user_id: 사용자 ID
            db: 데이터베이스 세션
            
        Returns:
            Dict: 세션 상태 정보 또는 None
        """
        try:
            result = db.execute(select(User).where(User.user_id == user_id))
            user = result.scalar_one_or_none()
            if not user:
                return None
            
            now = datetime.now(timezone.utc)
            
            # 세션이 없으면 None 반환
            if not user.current_pod_id or user.pod_status == "none":
                return None
            
            # 만료 상태 확인 (타임존 안전 비교)
            session_expired = safe_datetime_compare(now, user.session_expires_at)
            processing_expired = safe_datetime_compare(now, user.processing_expires_at)
            
            # 만료된 세션은 자동 정리
            if session_expired or processing_expired:
                self._terminate_current_session(user, db)
                return None
            
            return {
                "pod_id": user.current_pod_id,
                "pod_status": user.pod_status,
                "session_created_at": user.session_created_at,
                "session_expires_at": user.session_expires_at,
                "processing_expires_at": user.processing_expires_at,
                "total_generations": user.total_generations,
                "session_remaining_seconds": int((ensure_timezone_aware(user.session_expires_at) - now).total_seconds()) if user.session_expires_at else None,
                "processing_remaining_seconds": int((ensure_timezone_aware(user.processing_expires_at) - now).total_seconds()) if user.processing_expires_at else None
            }
            
        except Exception as e:
            logger.error(f"Failed to get session status for user {user_id}: {e}")
            return None
    
    def terminate_session(self, user_id: str, db: Session) -> bool:
        """
        세션 수동 종료
        
        Args:
            user_id: 사용자 ID
            db: 데이터베이스 세션
            
        Returns:
            bool: 종료 성공 여부
        """
        try:
            result = db.execute(select(User).where(User.user_id == user_id))
            user = result.scalar_one_or_none()
            if not user:
                logger.error(f"User not found: {user_id}")
                return False
            
            if user.current_pod_id:
                self._terminate_current_session(user, db)
                logger.info(f"Session terminated for user {user_id}")
                return True
            else:
                logger.info(f"No active session to terminate for user {user_id}")
                return True
                
        except Exception as e:
            logger.error(f"Failed to terminate session for user {user_id}: {e}")
            return False
    
    async def cleanup_expired_sessions(self, db: AsyncSession) -> int:
        """
        만료된 세션들 및 종료된 RunPod 정리 (백그라운드 작업용)
        
        Args:
            db: 비동기 데이터베이스 세션
            
        Returns:
            int: 정리된 세션 수
        """
        try:
            now = datetime.now(timezone.utc)
            # 데이터베이스 비교를 위해 타임존 정보 제거 (UTC 시간 그대로 사용)
            now_naive = now.replace(tzinfo=None)
            
            # 1. 만료된 세션을 가진 사용자들 조회
            result = await db.execute(
                select(User).where(
                    User.current_pod_id.isnot(None),
                    User.pod_status != "none",
                    (User.session_expires_at < now_naive) | (User.processing_expires_at < now_naive)
                )
            )
            
            expired_users = result.scalars().all()
            
            # 2. 활성 Pod을 가진 모든 사용자들 조회 (RunPod 상태 확인용)
            result = await db.execute(
                select(User).where(
                    User.current_pod_id.isnot(None),
                    User.pod_status.in_(["starting", "running", "ready", "processing"])
                )
            )
            
            active_users = result.scalars().all()
            cleaned_count = 0
            
            # 3. 만료된 세션 정리
            for user in expired_users:
                try:
                    await self._terminate_current_session_async(user, db)
                    cleaned_count += 1
                    logger.info(f"🧹 만료된 세션 정리 완료: 사용자 {user.user_id}, Pod {user.current_pod_id}")
                except Exception as e:
                    logger.error(f"Failed to cleanup expired session for user {user.user_id}: {e}")
            
            # 4. RunPod 상태 확인 및 종료된 Pod 정리
            terminated_count = 0
            for user in active_users:
                if user.current_pod_id and user.current_pod_id != "pending":
                    try:
                        old_pod_id = user.current_pod_id
                        await self._check_and_cleanup_terminated_pod(user, db)
                        # Pod이 정리되었는지 확인
                        if user.current_pod_id != old_pod_id:
                            terminated_count += 1
                    except Exception as e:
                        logger.error(f"Failed to check Pod status for user {user.user_id}: {e}")
            
            total_cleaned = cleaned_count + terminated_count
            
            # 변경사항 커밋
            if total_cleaned > 0:
                await db.commit()
                if terminated_count > 0:
                    logger.info(f"🧹 세션 정리 완료: 만료 {cleaned_count}개, 종료된 Pod {terminated_count}개")
                else:
                    logger.info(f"🧹 만료된 세션 {cleaned_count}개 정리 완료")
            
            return total_cleaned
            
        except Exception as e:
            logger.error(f"Failed to cleanup expired sessions: {e}")
            return 0
    
    async def _get_user(self, user_id: str, db: AsyncSession) -> Optional[User]:
        """사용자 조회"""
        try:
            result = await db.execute(select(User).where(User.user_id == user_id))
            return result.scalar_one_or_none()
        except Exception as e:
            logger.error(f"Failed to get user {user_id}: {e}")
            return None
    
    def _has_active_session(self, user: User) -> bool:
        """활성 세션 여부 확인"""
        if not user.current_pod_id or user.pod_status == "none":
            return False
        
        # Pod 생성 중인 경우 활성 세션으로 간주 (중복 생성 방지)
        if hasattr(self, f'_creating_pod_{user.user_id}'):
            logger.info(f"사용자 {user.user_id}의 Pod 생성이 이미 진행 중입니다")
            return True
        
        # failed 상태인 경우 5분간 재시도 방지
        if user.pod_status == "failed":
            if user.session_created_at:
                failed_time = ensure_timezone_aware(user.session_created_at)
                now = datetime.now(timezone.utc)
                if failed_time and (now - failed_time) < timedelta(minutes=5):
                    logger.info(f"사용자 {user.user_id}의 Pod 생성 실패 후 재시도 대기 중 (5분)")
                    return True
            return False
        
        now = datetime.now(timezone.utc)
        
        # 세션 만료 확인 (타임존 안전 비교)
        if safe_datetime_compare(now, user.session_expires_at):
            return False
        
        # 처리 만료 확인 (타임존 안전 비교)
        if safe_datetime_compare(now, user.processing_expires_at):
            return False
        
        return True
    
    async def _update_session_activity(self, user: User, db: Session):
        """세션 활동 시간 업데이트 (필요시)"""
        # 현재는 별도 활동 시간 필드가 없으므로 스킵
        # 필요하다면 나중에 last_activity_at 필드 추가 가능
        pass
    
    async def _terminate_current_session(self, user: User, db: Session, background_tasks=None):
        """현재 세션 종료 (동기 버전)"""
        try:
            if user.current_pod_id and user.current_pod_id != "pending":
                pod_id = user.current_pod_id
                logger.info(f"Terminating RunPod {pod_id} for user {user.user_id}")
                
                if background_tasks:
                    # 백그라운드 태스크가 있으면 비동기로 처리
                    background_tasks.add_task(self.runpod_service.terminate_pod, pod_id)
                else:
                    # 백그라운드 태스크가 없으면 즉시 처리를 위해 별도 스레드로 실행
                    import threading
                    
                    def terminate_pod_sync():
                        try:
                            import asyncio
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            loop.run_until_complete(self.runpod_service.terminate_pod(pod_id))
                            loop.close()
                            logger.info(f"✅ RunPod {pod_id} terminated successfully in background thread")
                        except Exception as e:
                            logger.error(f"❌ Failed to terminate RunPod {pod_id} in background thread: {e}")
                    
                    thread = threading.Thread(target=terminate_pod_sync)
                    thread.daemon = True
                    thread.start()
                    logger.info(f"Started background thread to terminate RunPod {pod_id}")
            
            # 사용자 세션 상태 초기화
            user.current_pod_id = None
            user.pod_status = "none"
            user.session_created_at = None
            user.session_expires_at = None
            user.processing_expires_at = None
            
        except Exception as e:
            logger.error(f"Failed to terminate session for user {user.user_id}: {e}")
    
    async def _terminate_current_session_async(self, user: User, db: AsyncSession):
        """현재 세션 종료 (비동기 버전 - cleanup 전용, 건강성 체크 포함)"""
        try:
            if user.current_pod_id and user.current_pod_id != "pending":
                pod_id = user.current_pod_id
                logger.info(f"🗑️ RunPod {pod_id} 종료 시작 (user: {user.user_id})")
                
                # Pod 건강성 먼저 체크
                try:
                    health_check = await self.runpod_service.check_pod_health(pod_id)
                    logger.info(f"   📊 Pod 건강성 체크: {health_check}")
                    
                    # 리소스 부족 감지 시 강제 종료 보장
                    if health_check.get("needs_restart") or not health_check.get("healthy", False):
                        logger.warning(f"   ⚠️ Pod {pod_id} 건강성 문제 감지 - 강제 종료 필요")
                        
                        # 강제 종료 시도 (여러 번)
                        for attempt in range(3):
                            try:
                                success = await self.runpod_service.terminate_pod(pod_id)
                                if success:
                                    logger.info(f"   ✅ 강제 종료 성공 (시도 {attempt + 1}/3)")
                                    break
                                else:
                                    logger.warning(f"   ⚠️ 강제 종료 실패 (시도 {attempt + 1}/3)")
                                    if attempt < 2:  # 마지막 시도가 아니면 잠시 대기
                                        await asyncio.sleep(2)
                            except Exception as e:
                                logger.error(f"   ❌ 강제 종료 시도 {attempt + 1} 실패: {e}")
                                if attempt < 2:
                                    await asyncio.sleep(2)
                    else:
                        # 정상 Pod는 일반 종료
                        success = await self.runpod_service.terminate_pod(pod_id)
                        if success:
                            logger.info(f"✅ RunPod {pod_id} 정상 종료 완료")
                        else:
                            logger.warning(f"⚠️ RunPod {pod_id} 정상 종료 실패")
                            
                except Exception as health_error:
                    logger.error(f"   ❌ Pod 건강성 체크 실패: {health_error}")
                    # 건강성 체크 실패해도 일반 종료 시도
                    try:
                        success = await self.runpod_service.terminate_pod(pod_id)
                        if success:
                            logger.info(f"✅ RunPod {pod_id} 백업 종료 성공")
                        else:
                            logger.warning(f"⚠️ RunPod {pod_id} 백업 종료 실패")
                    except Exception as e:
                        logger.error(f"❌ 백업 종료도 실패: {e}")
                        # Pod 종료 실패해도 DB는 정리
            
            # 사용자 세션 상태 초기화
            user.current_pod_id = None
            user.pod_status = "none"
            user.session_created_at = None
            user.session_expires_at = None
            user.processing_expires_at = None
            
            logger.info(f"🧹 사용자 {user.user_id} 세션 상태 초기화 완료")
            
        except Exception as e:
            logger.error(f"Failed to terminate session for user {user.user_id}: {e}")
            raise
            
            # 사용자 세션 상태 즉시 초기화
            user.current_pod_id = None
            user.pod_status = "none"
            user.session_created_at = None
            user.session_expires_at = None
            user.processing_expires_at = None
            
            db.commit()
            
        except Exception as e:
            logger.error(f"Failed to terminate session for user {user.user_id}: {e}")
            db.rollback()
            raise

    async def _create_pod_and_update_db(self, user_id: str, db: Session):
        """백그라운드에서 Pod 생성 및 DB 업데이트 (비동기)"""
        try:
            logger.info(f"Background task: Creating RunPod for user {user_id}")
            pod_response = await self.runpod_service.create_pod(request_id=user_id)
            
            if pod_response and pod_response.pod_id:
                logger.info(f"Background task: RunPod created for user {user_id} with pod_id {pod_response.pod_id}")
                user = await self._get_user(user_id, db)
                if user:
                    user.current_pod_id = pod_response.pod_id
                    user.pod_status = pod_response.status.lower() # 'STARTING' -> 'starting'
                    await db.commit()
                    logger.info(f"DB updated for user {user_id} with new pod info.")
            else:
                raise Exception("Pod creation failed or returned no ID")

        except Exception as e:
            logger.error(f"Background task failed for user {user_id}: {e}")
            user = await self._get_user(user_id, db)
            if user:
                user.pod_status = "failed"
                user.current_pod_id = None
                await db.commit()

    async def _create_pod_and_update_db_fixed(self, user_id: str, db: AsyncSession):
        """백그라운드에서 Pod 생성 및 DB 업데이트 (비동기 DB 호환, 건강성 체크 포함)"""
        try:
            logger.info(f"📍 _create_pod_and_update_db_fixed 함수 시작: user {user_id}")
            logger.info(f"🔄 RunPod 서비스로 Pod 생성 요청 중...")
            pod_response = await self.runpod_service.create_pod(request_id=user_id)
            
            if pod_response and pod_response.pod_id:
                logger.info(f"✅ RunPod 생성 성공! user: {user_id}, pod_id: {pod_response.pod_id}")
                logger.info(f"   🌐 Endpoint URL: {pod_response.endpoint_url}")
                logger.info(f"   📊 Status: {pod_response.status}")
                
                # 바로 DB 업데이트 진행 (건강성 체크 및 재시작 로직 제거)
                # 비동기 데이터베이스 세션 사용
                result = await db.execute(select(User).where(User.user_id == user_id))
                user = result.scalar_one_or_none()
                
                if user:
                    user.current_pod_id = pod_response.pod_id
                    user.pod_status = pod_response.status.lower() # 'STARTING' -> 'starting'
                    await db.commit()
                    logger.info(f"DB updated for user {user_id} with pod info: {pod_response.pod_id}")
                    
                    # Pod 준비 상태 확인 시작
                    await self._wait_for_pod_ready_async(user_id, pod_response.pod_id, db)
            else:
                raise Exception("Pod creation failed or returned no ID")

        except Exception as e:
            logger.error(f"Background task failed for user {user_id}: {e}")
            try:
                result = await db.execute(select(User).where(User.user_id == user_id))
                user = result.scalar_one_or_none()
                if user:
                    user.pod_status = "failed"
                    user.current_pod_id = None
                    await db.commit()
            except Exception as db_error:
                logger.error(f"Failed to update DB after error: {db_error}")
        finally:
            # 작업 완료 후 플래그 해제
            if hasattr(self, f'_creating_pod_{user_id}'):
                delattr(self, f'_creating_pod_{user_id}')
                logger.info(f"Pod creation flag cleared for user {user_id}")

    async def _create_pod_and_update_db_async(self, user_id: str):
        """백그라운드에서 Pod 생성 및 DB 업데이트 (비동기)"""
        logger.info(f"🚀 백그라운드 태스크 시작: Pod 생성 for user {user_id}")
        try:
            from app.database import get_async_db
            
            # 중복 생성 방지: 이미 실행 중인 태스크가 있는지 확인
            if hasattr(self, f'_creating_pod_{user_id}'):
                logger.warning(f"⚠️ Pod creation already in progress for user {user_id}")
                return
            
            setattr(self, f'_creating_pod_{user_id}', True)
            logger.info(f"✅ Pod 생성 플래그 설정 완료: user {user_id}")
            
            # 새로운 비동기 데이터베이스 세션 생성
            logger.info(f"📊 데이터베이스 세션 생성 중...")
            async for db in get_async_db():
                try:
                    logger.info(f"🔧 _create_pod_and_update_db_fixed 호출 시작: user {user_id}")
                    await self._create_pod_and_update_db_fixed(user_id, db)
                    logger.info(f"✅ _create_pod_and_update_db_fixed 완료: user {user_id}")
                    break
                except Exception as e:
                    logger.error(f"❌ Error in pod creation for user {user_id}: {e}", exc_info=True)
                    raise
            
            logger.info(f"🎉 Pod creation task completed successfully for user {user_id}")
            
        except Exception as e:
            logger.error(f"💥 Failed to create pod for user {user_id}: {e}", exc_info=True)
        finally:
            # 플래그 해제
            if hasattr(self, f'_creating_pod_{user_id}'):
                delattr(self, f'_creating_pod_{user_id}')
                logger.info(f"🧹 Pod 생성 플래그 해제: user {user_id}")
    
    def _wait_for_pod_ready(self, user_id: str, pod_id: str, db: Session):
        """Pod 준비 완료 대기 (임시로 비활성화)"""
        # TODO: 실제 RunPod 연동 시 백그라운드 태스크로 구현 필요
        logger.info(f"Pod ready check disabled temporarily for user {user_id}, pod {pod_id}")
        pass

    async def _wait_for_pod_ready_async(self, user_id: str, pod_id: str, db: AsyncSession):
        """Pod 준비 완료까지 대기 및 상태 업데이트"""
        try:
            logger.info(f"Waiting for pod {pod_id} to be ready for user {user_id}")
            
            # RunPod 서비스의 wait_for_ready 함수 사용 (10분으로 연장)
            is_ready = await self.runpod_service.wait_for_ready(pod_id, max_wait_time=600)
            
            if is_ready:
                # Pod가 준비되면 상태를 'ready'로 업데이트
                result = await db.execute(select(User).where(User.user_id == user_id))
                user = result.scalar_one_or_none()
                
                if user and user.current_pod_id == pod_id:
                    user.pod_status = "ready"
                    await db.commit()
                    logger.info(f"✅ Pod {pod_id} is ready for user {user_id}")
                    
                    # WebSocket으로 준비 완료 메시지 전송
                    try:
                        from app.websocket import get_ws_manager
                        ws_manager = get_ws_manager()
                        await ws_manager.send_message(user_id, {
                            "type": "pod_ready",
                            "data": {
                                "pod_id": pod_id,
                                "pod_status": "ready",
                                "endpoint_url": f"https://{pod_id}-8188.proxy.runpod.net",
                                "message": "Pod가 준비되었습니다. 이미지 생성이 가능합니다."
                            }
                        })
                        logger.info(f"📨 WebSocket으로 pod_ready 메시지 전송 완료: user {user_id}")
                    except Exception as ws_error:
                        logger.error(f"WebSocket 메시지 전송 실패: {ws_error}")
                else:
                    logger.warning(f"User {user_id} not found or pod_id mismatch during ready update")
            else:
                # Pod 준비 실패
                result = await db.execute(select(User).where(User.user_id == user_id))
                user = result.scalar_one_or_none()
                
                if user and user.current_pod_id == pod_id:
                    # Pod가 실패해도 즉시 삭제하지 않고 'failed' 상태로 표시
                    # 실제 ComfyUI가 나중에 응답할 수 있기 때문
                    user.pod_status = "failed"
                    # current_pod_id는 유지하여 나중에 재확인 가능하도록 함
                    await db.commit()
                    logger.error(f"❌ Pod {pod_id} failed to be ready for user {user_id}")
                    logger.info(f"🔄 Pod ID는 유지하여 나중에 재확인 가능하도록 설정")
                    
                    # WebSocket으로 실패 메시지 전송
                    try:
                        from app.websocket import get_ws_manager
                        ws_manager = get_ws_manager()
                        await ws_manager.send_message(user_id, {
                            "type": "pod_failed",
                            "data": {
                                "pod_id": pod_id,
                                "pod_status": "failed",
                                "message": "Pod 준비에 실패했습니다. 다시 시도해주세요."
                            }
                        })
                        logger.info(f"📨 WebSocket으로 pod_failed 메시지 전송 완료: user {user_id}")
                    except Exception as ws_error:
                        logger.error(f"WebSocket 메시지 전송 실패: {ws_error}")
                    
        except Exception as e:
            logger.error(f"Error waiting for pod ready for user {user_id}: {e}")
            try:
                result = await db.execute(select(User).where(User.user_id == user_id))
                user = result.scalar_one_or_none()
                
                if user and user.current_pod_id == pod_id:
                    user.pod_status = "failed"
                    # current_pod_id는 유지하여 나중에 재확인 가능하도록 함
                    await db.commit()
            except Exception as db_error:
                logger.error(f"Failed to update failed status: {db_error}")
    
    async def _check_and_cleanup_terminated_pod(self, user: User, db: AsyncSession):
        """RunPod 상태를 확인하고 종료된 Pod을 정리"""
        try:
            pod_id = user.current_pod_id
            if not pod_id or pod_id == "pending":
                return
            
            # RunPod API에서 Pod 상태 확인
            from app.services.runpod_service import get_runpod_service
            runpod_service = get_runpod_service()
            
            try:
                pod_info = await runpod_service.get_pod_status(pod_id)
                
                if not pod_info:
                    # Pod 정보를 가져올 수 없는 경우 (삭제되었을 가능성)
                    logger.warning(f"⚠️ Pod {pod_id} 정보를 가져올 수 없음 - 삭제된 것으로 추정")
                    await self._cleanup_terminated_session(user, db, "Pod 정보 없음")
                    return
                
                # RunPodPodResponse 객체에서 상태 추출
                pod_status = pod_info.status.upper() if hasattr(pod_info, 'status') else "UNKNOWN"
                logger.debug(f"🔍 Pod {pod_id} 상태 확인: {pod_status} (사용자: {user.user_id})")
                
                # 종료된 상태들 확인
                terminated_statuses = ["TERMINATED", "STOPPED", "FAILED", "EXITED"]
                
                if pod_status in terminated_statuses:
                    logger.info(f"🛑 종료된 Pod 감지: {pod_id} (상태: {pod_status}, 사용자: {user.user_id})")
                    await self._cleanup_terminated_session(user, db, f"Pod 상태: {pod_status}")
                    
            except Exception as runpod_error:
                # RunPod API 오류 시 더 구체적인 처리
                error_msg = str(runpod_error).lower()
                
                # Pod이 존재하지 않는 경우의 특정 오류 메시지들 
                not_found_indicators = [
                    "not found", "does not exist", "404", 
                    "no pod found", "invalid pod id", "pod does not exist"
                ]
                
                if any(indicator in error_msg for indicator in not_found_indicators):
                    logger.info(f"🛑 삭제된 Pod 감지: {pod_id} (오류: {str(runpod_error)[:100]}...)")
                    await self._cleanup_terminated_session(user, db, f"Pod 삭제됨: {str(runpod_error)[:50]}...")
                else:
                    # 네트워크 오류 등 일시적 문제
                    logger.warning(f"⚠️ RunPod API 일시적 오류로 Pod {pod_id} 상태 확인 실패: {str(runpod_error)[:100]}...")
                    # API 오류인 경우 세션을 정리하지 않음 (일시적 문제일 수 있음)
                
        except Exception as e:
            logger.error(f"Pod 상태 확인 중 오류 (사용자: {user.user_id}): {e}")
    
    async def _cleanup_terminated_session(self, user: User, db: AsyncSession, reason: str):
        """종료된 Pod으로 인한 세션 정리"""
        try:
            old_pod_id = user.current_pod_id
            old_status = user.pod_status
            
            # 세션 상태 초기화
            user.current_pod_id = None
            user.pod_status = "none"
            user.session_created_at = None
            user.session_expires_at = None
            user.processing_expires_at = None
            
            logger.info(f"🧹 종료된 Pod으로 인한 세션 정리 완료")
            logger.info(f"   📋 사용자: {user.user_id}")
            logger.info(f"   🔴 이전 Pod: {old_pod_id} (상태: {old_status})")
            logger.info(f"   📝 종료 원인: {reason}")
            
            # 변경사항은 상위 함수에서 커밋됨
            
        except Exception as e:
            logger.error(f"종료된 세션 정리 중 오류 (사용자: {user.user_id}): {e}")


# 싱글톤 패턴
_user_session_service = None

def get_user_session_service() -> UserSessionService:
    """사용자 세션 서비스 싱글톤 인스턴스 반환"""
    global _user_session_service
    if _user_session_service is None:
        _user_session_service = UserSessionService()
    return _user_session_service
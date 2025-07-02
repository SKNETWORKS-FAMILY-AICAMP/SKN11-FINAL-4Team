"""
백그라운드 작업 관리 서비스
지속적 모니터링과 S3 업로드를 포함한 비동기 작업 처리
"""

import asyncio
import logging
import os
from typing import Dict, Optional
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.influencers.qa_generator import InfluencerQAGenerator, QAGenerationTask, QAGenerationStatus
from app.services.s3_service import get_s3_service
from app.services.finetuning_service import get_finetuning_service
from app.services.notification_service import get_notification_service
from app.services.batch_job_service import get_batch_job_service

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BackgroundTaskManager:
    def __init__(self):
        self.qa_generator = InfluencerQAGenerator()
        self.s3_service = get_s3_service()
        self.finetuning_service = get_finetuning_service()
        self.notification_service = get_notification_service()
        self.batch_service = get_batch_job_service()
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.monitoring_tasks: Dict[str, asyncio.Task] = {}
        self.finetuning_tasks: Dict[str, asyncio.Task] = {}
        
    async def start_qa_generation_task(self, influencer_id: str):
        """
        인플루언서 QA 생성 백그라운드 작업 시작
        Args:
            influencer_id: 인플루언서 ID
        """
        try:
            logger.info(f"QA 생성 작업 시작: influencer_id={influencer_id}")
            
            # 데이터베이스 세션 획득
            db: Session = next(get_db())
            
            try:
                # QA 생성 작업 시작
                task_id = self.qa_generator.start_qa_generation(influencer_id, db)
                
                # 모니터링 방식을 환경변수로 제어
                use_webhook = os.getenv('OPENAI_USE_WEBHOOK', 'true').lower() == 'true'
                
                if use_webhook:
                    # 웹훅 방식 - 주기적 모니터링 비활성화
                    logger.info(f"✅ QA 생성 작업 시작 완료 (웹훅 대기 모드): task_id={task_id}")
                    logger.info(f"🎯 OpenAI 웹훅으로 완료 알림을 받을 예정입니다")
                else:
                    # 폴링 방식 - 주기적 모니터링 활성화
                    logger.info(f"🚀 지속적 모니터링 작업 생성 중 (폴링 모드): task_id={task_id}")
                    monitor_task = asyncio.create_task(
                        self._continuous_monitor_qa_generation_db(task_id)
                    )
                    self.monitoring_tasks[task_id] = monitor_task
                    self.running_tasks[task_id] = monitor_task
                    
                    logger.info(f"✅ QA 생성 작업 및 지속적 모니터링 시작 완료: task_id={task_id}")
                    logger.info(f"📝 현재 실행 중인 모니터링 작업 수: {len(self.monitoring_tasks)}")
                
            finally:
                db.close()
                
        except Exception as e:
            logger.error(f"QA 생성 작업 시작 실패: influencer_id={influencer_id}, error={str(e)}", exc_info=True)
            # 백그라운드 작업에서는 예외를 re-raise하지 않고 로깅만 함
            pass
    
    async def _continuous_monitor_qa_generation(self, task_id: str):
        """
        QA 생성 작업 지속적 모니터링 (S3 업로드 포함)
        Args:
            task_id: 작업 ID
        """
        db: Session = None
        try:
            logger.info(f"지속적 QA 생성 모니터링 시작: task_id={task_id}")
            
            max_wait_time = timedelta(hours=26)  # 최대 26시간 대기 (여유시간 포함)
            start_time = datetime.now()
            check_interval = 420  # 7분마다 상태 확인 (7분 = 420초)
            
            while datetime.now() - start_time < max_wait_time:
                try:
                    # 작업 상태 업데이트
                    logger.info(f"🔄 주기적 상태 확인 중: task_id={task_id} (7분마다)")
                    self.qa_generator.update_task_status(task_id)
                    task = self.qa_generator.get_task_status(task_id)
                    
                    if not task:
                        logger.error(f"작업을 찾을 수 없습니다: task_id={task_id}")
                        break
                    
                    logger.info(f"📊 작업 상태: task_id={task_id}, status={task.status.value}, batch_id={task.batch_id}")
                    
                    if task.status == QAGenerationStatus.BATCH_COMPLETED:
                        # 배치 완료 시 결과 처리 및 S3 업로드
                        logger.info(f"배치 완료 감지, 결과 처리 및 S3 업로드 시작: task_id={task_id}")
                        
                        # 데이터베이스 세션 획득
                        db = next(get_db())
                        
                        success = await self._process_and_upload_results(task_id, db)
                        
                        if success:
                            logger.info(f"QA 생성 및 S3 업로드 완료: task_id={task_id}")
                        else:
                            logger.error(f"QA 생성 결과 처리 또는 S3 업로드 실패: task_id={task_id}")
                        break
                        
                    elif task.status == QAGenerationStatus.FAILED:
                        logger.error(f"QA 생성 작업 실패: task_id={task_id}, error={task.error_message}")
                        break
                        
                    elif task.status == QAGenerationStatus.COMPLETED:
                        logger.info(f"QA 생성 작업 이미 완료됨: task_id={task_id}")
                        break
                    
                    # 지정된 간격만큼 대기
                    logger.info(f"⏰ 다음 확인까지 7분 대기: task_id={task_id}")
                    await asyncio.sleep(check_interval)
                    
                except Exception as e:
                    logger.error(f"모니터링 루프 중 오류: task_id={task_id}, error={str(e)}")
                    await asyncio.sleep(check_interval)  # 오류 발생 시에도 계속 모니터링
            
            # 시간 초과 체크
            if datetime.now() - start_time >= max_wait_time:
                logger.warning(f"모니터링 시간 초과: task_id={task_id}")
                task = self.qa_generator.get_task_status(task_id)
                if task and task.status not in [QAGenerationStatus.COMPLETED, QAGenerationStatus.FAILED]:
                    task.status = QAGenerationStatus.FAILED
                    task.error_message = "모니터링 시간 초과 (26시간)"
                    task.updated_at = datetime.now()
                
        except Exception as e:
            logger.error(f"지속적 모니터링 중 치명적 오류: task_id={task_id}, error={str(e)}")
            
            # 오류 발생 시 작업 상태를 실패로 업데이트
            task = self.qa_generator.get_task_status(task_id)
            if task:
                task.status = QAGenerationStatus.FAILED
                task.error_message = f"모니터링 치명적 오류: {str(e)}"
                task.updated_at = datetime.now()
            
        finally:
            # 리소스 정리
            if db:
                db.close()
            
            # 모니터링 작업 정리
            if task_id in self.monitoring_tasks:
                del self.monitoring_tasks[task_id]
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
                
            logger.info(f"🏁 지속적 모니터링 종료: task_id={task_id}")
            logger.info(f"📝 남은 모니터링 작업 수: {len(self.monitoring_tasks)}")

    async def _continuous_monitor_qa_generation_db(self, task_id: str):
        """
        DB 기반 QA 생성 작업 지속적 모니터링 (폴링 모드)
        Args:
            task_id: 작업 ID
        """
        db: Session = None
        try:
            logger.info(f"🔄 DB 기반 지속적 QA 생성 모니터링 시작: task_id={task_id}")
            
            max_wait_time = timedelta(hours=26)  # 최대 26시간 대기
            start_time = datetime.now()
            check_interval = int(os.getenv('OPENAI_POLLING_INTERVAL', '420'))  # 기본 7분 (420초)
            
            logger.info(f"⏰ 폴링 간격: {check_interval}초 ({check_interval//60}분)")
            
            while datetime.now() - start_time < max_wait_time:
                try:
                    # DB 세션 획득
                    db = next(get_db())
                    
                    # DB에서 배치 작업 상태 조회
                    batch_job = self.batch_service.get_batch_job_by_task_id(db, task_id)
                    if not batch_job:
                        logger.error(f"DB에서 배치 작업을 찾을 수 없습니다: task_id={task_id}")
                        break
                    
                    logger.info(f"🔄 주기적 상태 확인 중 (DB): task_id={task_id}, status={batch_job.status}")
                    
                    # OpenAI에서 실제 배치 상태 확인
                    openai_status = self.qa_generator.check_batch_status(batch_job.openai_batch_id)
                    
                    # DB 상태 업데이트
                    updated_batch = self.batch_service.update_batch_status(
                        db=db,
                        batch_id=batch_job.openai_batch_id,
                        status=openai_status['status'],
                        output_file_id=openai_status.get('output_file_id'),
                        error_message=openai_status.get('error_message')
                    )
                    
                    logger.info(f"📊 DB 상태 업데이트: task_id={task_id}, status={openai_status['status']}")
                    
                    if openai_status['status'] == 'completed':
                        # 배치 완료 시 결과 처리 및 S3 업로드
                        logger.info(f"✅ 배치 완료 감지 (DB), 결과 처리 시작: task_id={task_id}")
                        
                        success = await self._process_and_upload_results_db(task_id, db)
                        
                        if success:
                            logger.info(f"🎉 QA 생성 및 S3 업로드 완료 (DB): task_id={task_id}")
                            # 완료된 작업 정리
                            self.batch_service.delete_completed_batch_job(db, task_id)
                        else:
                            logger.error(f"❌ QA 생성 결과 처리 실패 (DB): task_id={task_id}")
                        break
                        
                    elif openai_status['status'] == 'failed':
                        logger.error(f"❌ 배치 작업 실패 (DB): task_id={task_id}")
                        break
                        
                    elif openai_status['status'] in ['cancelled', 'expired']:
                        logger.warning(f"⚠️ 배치 작업 취소/만료 (DB): task_id={task_id}, status={openai_status['status']}")
                        break
                    
                    # DB 세션 정리
                    db.close()
                    db = None
                    
                    # 지정된 간격만큼 대기
                    logger.info(f"⏰ 다음 확인까지 {check_interval//60}분 대기: task_id={task_id}")
                    await asyncio.sleep(check_interval)
                    
                except Exception as e:
                    logger.error(f"모니터링 루프 중 오류 (DB): task_id={task_id}, error={str(e)}")
                    if db:
                        db.close()
                        db = None
                    await asyncio.sleep(check_interval)  # 오류 발생 시에도 계속 모니터링
            
            # 시간 초과 체크
            if datetime.now() - start_time >= max_wait_time:
                logger.warning(f"⏰ 모니터링 시간 초과 (DB): task_id={task_id}")
                if not db:
                    db = next(get_db())
                self.batch_service.update_batch_status(
                    db=db,
                    batch_id=batch_job.openai_batch_id if batch_job else "",
                    status="failed",
                    error_message="모니터링 시간 초과 (26시간)"
                )
                
        except Exception as e:
            logger.error(f"지속적 모니터링 중 치명적 오류 (DB): task_id={task_id}, error={str(e)}")
            
        finally:
            # 리소스 정리
            if db:
                db.close()
            
            # 모니터링 작업 정리
            if task_id in self.monitoring_tasks:
                del self.monitoring_tasks[task_id]
            if task_id in self.running_tasks:
                del self.running_tasks[task_id]
                
            logger.info(f"🏁 DB 기반 지속적 모니터링 종료: task_id={task_id}")
            logger.info(f"📝 남은 모니터링 작업 수: {len(self.monitoring_tasks)}")

    async def _process_and_upload_results(self, task_id: str, db: Session) -> bool:
        """
        QA 생성 결과 처리 및 S3 업로드
        Args:
            task_id: 작업 ID
            db: 데이터베이스 세션
        Returns:
            성공 여부
        """
        try:
            task = self.qa_generator.get_task_status(task_id)
            if not task:
                logger.error(f"작업을 찾을 수 없습니다: task_id={task_id}")
                return False
                
            task.status = QAGenerationStatus.PROCESSING_RESULTS
            task.updated_at = datetime.now()
            
            # 배치 결과 다운로드
            result_file_path = self.qa_generator.download_batch_results(task.batch_id, task_id)
            if not result_file_path:
                raise Exception("결과 파일 다운로드 실패")
            
            # QA 쌍 처리
            qa_pairs = self.qa_generator.process_qa_results(result_file_path)
            if not qa_pairs:
                raise Exception("QA 쌍 처리 결과가 비어있습니다")
            
            # S3에 업로드
            if self.s3_service.is_available():
                logger.info(f"S3 업로드 시작: task_id={task_id}, QA 쌍 개수={len(qa_pairs)}")
                
                upload_results = self.s3_service.upload_qa_results(
                    influencer_id=task.influencer_id,
                    task_id=task_id,
                    qa_pairs=qa_pairs,
                    raw_results_file=result_file_path
                )
                
                if upload_results.get("processed_qa_url"):
                    logger.info(f"S3 업로드 성공: {upload_results}")
                    
                    # 작업에 S3 URL 정보 추가
                    task.s3_urls = upload_results
                else:
                    logger.warning("S3 업로드 실패, 로컬에만 저장됩니다")
            else:
                logger.warning("S3 서비스를 사용할 수 없어 로컬에만 저장됩니다")
            
            # 로컬에도 저장 (백업용)
            self.qa_generator.save_qa_pairs_to_db(task.influencer_id, qa_pairs, db)
            
            # 임시 파일 정리
            try:
                if os.path.exists(result_file_path):
                    os.remove(result_file_path)
                    logger.info(f"임시 파일 삭제: {result_file_path}")
            except Exception as e:
                logger.warning(f"임시 파일 삭제 실패: {e}")
            
            # 작업 완료
            task.status = QAGenerationStatus.COMPLETED
            task.generated_qa_pairs = len(qa_pairs)
            task.updated_at = datetime.now()
            
            logger.info(f"QA 생성 및 S3 업로드 완료: task_id={task_id}, QA 쌍={len(qa_pairs)}개")
            
            # QA 생성 완료 후 자동으로 파인튜닝 시작
            if task.s3_urls and task.s3_urls.get("processed_qa_url"):
                logger.info(f"QA 생성 완료, 파인튜닝 자동 시작: task_id={task_id}")
                await self._start_finetuning_after_qa(task_id, task.influencer_id, db)
            
            return True
            
        except Exception as e:
            logger.error(f"결과 처리 및 S3 업로드 오류: task_id={task_id}, error={str(e)}")
            
            task = self.qa_generator.get_task_status(task_id)
            if task:
                task.status = QAGenerationStatus.FAILED
                task.error_message = f"결과 처리/S3 업로드 오류: {str(e)}"
                task.updated_at = datetime.now()
            
            return False

    async def _start_finetuning_after_qa(self, qa_task_id: str, influencer_id: str, db: Session):
        """
        QA 생성 완료 후 파인튜닝 자동 시작
        Args:
            qa_task_id: QA 생성 작업 ID
            influencer_id: 인플루언서 ID
            db: 데이터베이스 세션
        """
        try:
            # QA 작업 정보 가져오기
            qa_task = self.qa_generator.get_task_status(qa_task_id)
            if not qa_task or not qa_task.s3_urls:
                logger.error(f"QA 작업 정보가 없거나 S3 URL이 없습니다: {qa_task_id}")
                return
            
            # 인플루언서 정보 가져오기
            from app.services.influencers.crud import get_influencer_by_id
            user_id = "system"  # 시스템 작업
            influencer_data = get_influencer_by_id(db, user_id, influencer_id)
            
            if not influencer_data:
                logger.error(f"인플루언서 정보를 찾을 수 없습니다: {influencer_id}")
                return
            
            # 인플루언서 정보를 딕셔너리로 변환
            influencer_dict = {
                "influencer_name": influencer_data.influencer_name,
                "personality": getattr(influencer_data.mbti, 'mbti_traits', '친근하고 활발한 성격') if influencer_data.mbti else '친근하고 활발한 성격',
                "style_info": getattr(influencer_data.style_preset, 'influencer_speech', '') if influencer_data.style_preset else ''
            }
            
            # 파인튜닝 작업 시작
            ft_task_id = self.finetuning_service.start_finetuning_task(
                influencer_id=influencer_id,
                qa_task_id=qa_task_id,
                s3_qa_url=qa_task.s3_urls["processed_qa_url"],
                influencer_data=influencer_dict
            )
            
            # 파인튜닝 백그라운드 작업 시작
            ft_task = asyncio.create_task(
                self._execute_finetuning_task(ft_task_id, influencer_dict)
            )
            self.finetuning_tasks[ft_task_id] = ft_task
            
            logger.info(f"파인튜닝 작업 시작됨: ft_task_id={ft_task_id}")
            
        except Exception as e:
            logger.error(f"파인튜닝 자동 시작 실패: qa_task_id={qa_task_id}, error={str(e)}")

    async def _execute_finetuning_task(self, ft_task_id: str, influencer_data: Dict):
        """
        파인튜닝 작업 실행
        Args:
            ft_task_id: 파인튜닝 작업 ID
            influencer_data: 인플루언서 정보
        """
        try:
            logger.info(f"파인튜닝 작업 실행 시작: ft_task_id={ft_task_id}")
            
            # 파인튜닝 실행 (동기 함수를 비동기로 실행)
            loop = asyncio.get_event_loop()
            success = await loop.run_in_executor(
                None, 
                self.finetuning_service.execute_finetuning_task,
                ft_task_id, 
                influencer_data
            )
            
            if success:
                logger.info(f"파인튜닝 작업 완료: ft_task_id={ft_task_id}")
                
                # 파인튜닝 완료 후 알림 전송
                await self._send_finetuning_completion_notification(ft_task_id)
            else:
                logger.error(f"파인튜닝 작업 실패: ft_task_id={ft_task_id}")
                
        except Exception as e:
            logger.error(f"파인튜닝 작업 실행 오류: ft_task_id={ft_task_id}, error={str(e)}")
            
            # 실패 상태로 업데이트
            ft_task = self.finetuning_service.get_task_status(ft_task_id)
            if ft_task:
                from app.services.finetuning_service import FineTuningStatus
                ft_task.status = FineTuningStatus.FAILED
                ft_task.error_message = str(e)
                ft_task.updated_at = datetime.now()
        
        finally:
            # 작업 정리
            if ft_task_id in self.finetuning_tasks:
                del self.finetuning_tasks[ft_task_id]

    async def _send_finetuning_completion_notification(self, ft_task_id: str):
        """
        파인튜닝 완료 알림 전송
        Args:
            ft_task_id: 파인튜닝 작업 ID
        """
        try:
            ft_task = self.finetuning_service.get_task_status(ft_task_id)
            if not ft_task:
                logger.error(f"파인튜닝 작업을 찾을 수 없습니다: {ft_task_id}")
                return
            
            # 사용자 정보 가져오기
            db: Session = next(get_db())
            try:
                from app.services.influencers.crud import get_influencer_by_id
                user_id = "system"  # 시스템 작업으로 조회
                influencer_data = get_influencer_by_id(db, user_id, ft_task.influencer_id)
                
                if not influencer_data:
                    logger.error(f"인플루언서 정보를 찾을 수 없습니다: {ft_task.influencer_id}")
                    return
                
                # 실제 사용자 ID는 인플루언서의 user_id 필드에서 가져오기
                actual_user_id = influencer_data.user_id
                
                # TODO: 실제 사용자 이메일 주소 가져오기 (User 테이블에서)
                # 현재는 더미 이메일 사용
                user_email = f"user_{actual_user_id}@example.com"  # 실제 구현 시 User 테이블에서 조회
                
                # 알림 전송
                await self.notification_service.send_finetuning_completion_notification(
                    user_email=user_email,
                    user_id=actual_user_id,
                    influencer_name=influencer_data.influencer_name,
                    model_url=ft_task.hf_model_url or "https://huggingface.co/model"
                )
                
                logger.info(f"파인튜닝 완료 알림 전송 완료: {ft_task_id} -> {actual_user_id}")
                
            finally:
                db.close()
            
        except Exception as e:
            logger.error(f"파인튜닝 완료 알림 전송 실패: {e}")

    async def _process_and_upload_results_db(self, task_id: str, db: Session) -> bool:
        """
        DB 기반 QA 생성 결과 처리 및 S3 업로드 (폴링 모드)
        Args:
            task_id: 작업 ID
            db: 데이터베이스 세션
        Returns:
            처리 성공 여부
        """
        try:
            # DB에서 배치 작업 조회
            batch_job = self.batch_service.get_batch_job_by_task_id(db, task_id)
            if not batch_job:
                logger.error(f"DB에서 배치 작업을 찾을 수 없음: task_id={task_id}")
                return False
            
            if batch_job.is_processed:
                logger.info(f"이미 처리된 작업: task_id={task_id}")
                return True
            
            logger.info(f"🔄 QA 결과 처리 시작 (DB): task_id={task_id}")
            
            # 배치 결과 다운로드
            result_file_path = self.qa_generator.download_batch_results(batch_job.openai_batch_id, task_id)
            if not result_file_path:
                logger.error(f"결과 파일 다운로드 실패: task_id={task_id}")
                return False
            
            # QA 쌍 처리
            qa_pairs = self.qa_generator.process_qa_results(result_file_path)
            if not qa_pairs:
                logger.error(f"QA 쌍 처리 실패: task_id={task_id}")
                return False
            
            logger.info(f"📊 QA 쌍 처리 완료: {len(qa_pairs)}개, task_id={task_id}")
            
            # S3에 QA 결과 업로드
            s3_urls = self.s3_service.upload_qa_results(
                influencer_id=batch_job.influencer_id,
                task_id=task_id,
                qa_pairs=qa_pairs,
                raw_results_file=result_file_path
            )
            
            if s3_urls.get("qa_file_url"):
                logger.info(f"📤 S3 업로드 성공: task_id={task_id}")
                
                # DB에 처리 완료 표시
                self.batch_service.mark_processed(
                    db=db,
                    task_id=task_id,
                    s3_qa_file_url=s3_urls.get("qa_file_url"),
                    s3_processed_file_url=s3_urls.get("processed_file_url")
                )
                self.batch_service.mark_uploaded_to_s3(db, task_id)
                
                # 파인튜닝 시작
                logger.info(f"🧠 파인튜닝 시작: task_id={task_id}")
                finetuning_task_id = await self.finetuning_service.start_finetuning_from_s3(
                    influencer_id=batch_job.influencer_id,
                    qa_task_id=task_id,
                    s3_qa_file_url=s3_urls["qa_file_url"]
                )
                
                if finetuning_task_id:
                    self.batch_service.mark_finetuning_started(db, task_id)
                    logger.info(f"🎯 파인튜닝 작업 시작됨: finetuning_task_id={finetuning_task_id}")
                else:
                    logger.error(f"파인튜닝 시작 실패: task_id={task_id}")
                
                return True
            else:
                logger.error(f"S3 업로드 실패: task_id={task_id}")
                return False
                
        except Exception as e:
            logger.error(f"결과 처리 중 오류 (DB): task_id={task_id}, error={str(e)}")
            import traceback
            logger.error(f"상세 오류: {traceback.format_exc()}")
            return False

    def get_qa_task_status(self, task_id: str) -> Optional[QAGenerationTask]:
        """
        QA 생성 작업 상태 조회 (환경변수에 따라 메모리 또는 DB에서 조회)
        Args:
            task_id: 작업 ID
        Returns:
            작업 상태 정보
        """
        use_webhook = os.getenv('OPENAI_USE_WEBHOOK', 'true').lower() == 'true'
        
        if use_webhook:
            # 웹훅 모드: 메모리에서 조회
            logger.debug(f"웹훅 모드 - 메모리에서 작업 상태 조회: task_id={task_id}")
            task = self.qa_generator.get_task_status(task_id)
            if task:
                logger.debug(f"웹훅 모드 - 작업 찾음: task_id={task_id}, status={task.status.value}")
            else:
                logger.warning(f"웹훅 모드 - 작업을 찾을 수 없음: task_id={task_id}")
            return task
        else:
            # 폴링 모드: DB에서 조회하여 QAGenerationTask 객체로 변환
            logger.debug(f"폴링 모드 - DB에서 작업 상태 조회: task_id={task_id}")
            db = next(get_db())
            try:
                batch_job = self.batch_service.get_batch_job_by_task_id(db, task_id)
                if batch_job:
                    # DB 데이터를 QAGenerationTask로 변환
                    task = QAGenerationTask(
                        task_id=batch_job.task_id,
                        influencer_id=batch_job.influencer_id,
                        status=QAGenerationStatus(batch_job.status),
                        batch_id=batch_job.openai_batch_id,
                        total_qa_pairs=batch_job.total_qa_pairs,
                        generated_qa_pairs=batch_job.generated_qa_pairs,
                        error_message=batch_job.error_message,
                        s3_urls={
                            "qa_file_url": batch_job.s3_qa_file_url,
                            "processed_file_url": batch_job.s3_processed_file_url
                        } if batch_job.s3_qa_file_url else None,
                        created_at=batch_job.created_at,
                        updated_at=batch_job.updated_at
                    )
                    logger.debug(f"폴링 모드 - DB에서 작업 찾음: task_id={task_id}, status={task.status.value}")
                    return task
                else:
                    logger.warning(f"폴링 모드 - DB에서 작업을 찾을 수 없음: task_id={task_id}")
                    return None
            finally:
                db.close()
    
    def get_all_qa_tasks(self) -> Dict[str, QAGenerationTask]:
        """
        모든 QA 생성 작업 상태 조회 (환경변수에 따라 메모리 또는 DB에서 조회)
        Returns:
            모든 작업 상태 정보
        """
        use_webhook = os.getenv('OPENAI_USE_WEBHOOK', 'true').lower() == 'true'
        
        if use_webhook:
            # 웹훅 모드: 메모리에서 조회
            return self.qa_generator.tasks
        else:
            # 폴링 모드: DB에서 조회하여 QAGenerationTask 객체들로 변환
            db = next(get_db())
            try:
                batch_jobs = self.batch_service.get_all_batch_jobs(db)
                tasks = {}
                
                for batch_job in batch_jobs:
                    task = QAGenerationTask(
                        task_id=batch_job.task_id,
                        influencer_id=batch_job.influencer_id,
                        status=QAGenerationStatus(batch_job.status),
                        batch_id=batch_job.openai_batch_id,
                        total_qa_pairs=batch_job.total_qa_pairs,
                        generated_qa_pairs=batch_job.generated_qa_pairs,
                        error_message=batch_job.error_message,
                        s3_urls={
                            "qa_file_url": batch_job.s3_qa_file_url,
                            "processed_file_url": batch_job.s3_processed_file_url
                        } if batch_job.s3_qa_file_url else None,
                        created_at=batch_job.created_at,
                        updated_at=batch_job.updated_at
                    )
                    tasks[batch_job.task_id] = task
                
                return tasks
            finally:
                db.close()
    
    def is_task_running(self, task_id: str) -> bool:
        """
        작업이 실행 중인지 확인
        Args:
            task_id: 작업 ID
        Returns:
            실행 중 여부
        """
        return task_id in self.running_tasks and not self.running_tasks[task_id].done()
    
    def cancel_task(self, task_id: str) -> bool:
        """
        작업 취소
        Args:
            task_id: 작업 ID
        Returns:
            취소 성공 여부
        """
        if task_id in self.running_tasks:
            task = self.running_tasks[task_id]
            if not task.done():
                task.cancel()
                logger.info(f"작업 취소됨: task_id={task_id}")
                return True
        return False
    
    def get_running_tasks_count(self) -> int:
        """
        실행 중인 작업 수 조회
        Returns:
            실행 중인 작업 수
        """
        return len([task for task in self.running_tasks.values() if not task.done()])
    
    def cleanup_completed_tasks(self):
        """
        완료된 작업들을 정리
        """
        completed_task_ids = [
            task_id for task_id, task in self.running_tasks.items() 
            if task.done()
        ]
        
        for task_id in completed_task_ids:
            del self.running_tasks[task_id]
            logger.info(f"완료된 작업 정리: task_id={task_id}")


# 전역 백그라운드 작업 매니저 인스턴스
background_task_manager = BackgroundTaskManager()


# 백그라운드 작업 함수들 (FastAPI Background Tasks에서 사용)
async def generate_influencer_qa_background(influencer_id: str):
    """
    인플루언서 QA 생성 백그라운드 작업 함수
    FastAPI Background Tasks에서 호출됨
    Args:
        influencer_id: 인플루언서 ID
    """
    try:
        await background_task_manager.start_qa_generation_task(influencer_id)
    except Exception as e:
        logger.error(f"백그라운드 QA 생성 작업 실패: influencer_id={influencer_id}, error={str(e)}", exc_info=True)


def get_background_task_manager() -> BackgroundTaskManager:
    """
    백그라운드 작업 매니저 의존성 주입용 함수
    Returns:
        BackgroundTaskManager 인스턴스
    """
    return background_task_manager
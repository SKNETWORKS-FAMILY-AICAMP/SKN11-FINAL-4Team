"""
파인튜닝 서비스
S3에서 QA 데이터를 가져와 EXAONE 모델 파인튜닝 수행
"""

import os
import json
import logging
import tempfile
import shutil
from typing import Optional, Dict, List
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from app.services.s3_service import get_s3_service
from app.services.vllm_client import get_vllm_client, vllm_health_check
from app.core.encryption import decrypt_sensitive_data
from app.models.influencer import AIInfluencer
from app.utils.finetuning_utils import (
    create_system_message, 
    convert_qa_data_for_finetuning,
    validate_qa_data,
    format_model_name_for_korean
)

logger = logging.getLogger(__name__)


# vLLM 서버의 FineTuningStatus import
try:
    import sys
    import os
    
    # vLLM 경로 추가
    vllm_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), '..', 'vllm')
    sys.path.insert(0, vllm_path)
    
    from app.models import FineTuningStatus
    logger.info("✅ vLLM FineTuningStatus import 성공")

except ImportError as e:
    logger.warning(f"⚠️ vLLM FineTuningStatus import 실패, 로컬 버전 사용: {e}")
    
    # 폴백: 로컬 버전
    class FineTuningStatus(Enum):
        PENDING = "pending"
        PREPARING_DATA = "preparing_data"
        TRAINING = "training"
        UPLOADING = "uploading"
        COMPLETED = "completed"
        FAILED = "failed"


@dataclass
class FineTuningTask:
    task_id: str
    influencer_id: str
    qa_task_id: str
    status: FineTuningStatus
    s3_qa_url: str
    model_name: Optional[str] = None
    hf_repo_id: Optional[str] = None
    hf_model_url: Optional[str] = None
    error_message: Optional[str] = None
    training_epochs: int = 5
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()


class InfluencerFineTuningService:
    def __init__(self):
        """파인튜닝 서비스 초기화"""
        self.s3_service = get_s3_service()
        self.tasks: Dict[str, FineTuningTask] = {}
        
        # 기본 모델 설정
        self.base_model = os.getenv('FINETUNING_BASE_MODEL', 'LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct')
    
    def _convert_korean_to_english(self, korean_name: str) -> str:
        """한글 이름을 영문으로 변환 (공통 유틸리티 사용)"""
        return format_model_name_for_korean(korean_name)
    
    def _get_hf_info_from_influencer(self, influencer_data, db) -> tuple[str, str]:
        """
        인플루언서의 그룹 ID를 통해 허깅페이스 토큰과 사용자명 정보 가져오기
        Args:
            influencer_data: 인플루언서 데이터
            db: 데이터베이스 세션
        Returns:
            (hf_token, hf_username) 튜플
        """
        logger.debug(f"_get_hf_info_from_influencer 호출됨. influencer_data 타입: {type(influencer_data)}")
        if isinstance(influencer_data, dict):
            logger.debug(f"influencer_data (dict): {influencer_data}")
        else:
            logger.debug(f"influencer_data (object): {influencer_data.__dict__ if hasattr(influencer_data, '__dict__') else influencer_data}")

        try:
            # 인플루언서의 그룹 ID 추출
            group_id = None
            if hasattr(influencer_data, 'group_id'):
                group_id = influencer_data.group_id
            elif isinstance(influencer_data, dict):
                group_id = influencer_data.get('group_id')
            
            logger.debug(f"추출된 group_id: {group_id}")

            if not group_id:
                raise Exception("인플루언서의 그룹 ID를 찾을 수 없습니다")
            
            # 해당 그룹의 허깅페이스 토큰 조회 (최신 생성순으로 정렬)
            from app.models.user import HFTokenManage
            hf_token_manage = db.query(HFTokenManage).filter(
                HFTokenManage.group_id == group_id
            ).order_by(HFTokenManage.created_at.desc()).first()
            
            if hf_token_manage:
                logger.debug(f"HFTokenManage 객체 발견. 닉네임: {hf_token_manage.hf_token_nickname}, 사용자명: {hf_token_manage.hf_user_name}")
                # 암호화된 토큰 복호화
                try:
                    decrypted_token = decrypt_sensitive_data(hf_token_manage.hf_token_value)
                    logger.info(f"그룹 {group_id}의 허깅페이스 토큰 조회 성공: {hf_token_manage.hf_token_nickname}")
                    return decrypted_token, hf_token_manage.hf_user_name
                except Exception as decrypt_e:
                    logger.error(f"허깅페이스 토큰 복호화 실패: {decrypt_e}", exc_info=True)
                    raise Exception(f"허깅페이스 토큰 복호화 실패: {decrypt_e}")
            else:
                logger.warning(f"그룹 {group_id}에 등록된 허깅페이스 토큰을 찾을 수 없습니다.")
                # 그룹에 토큰이 없는 경우 
                raise Exception(f"그룹 {group_id}에 등록된 허깅페이스 토큰이 없습니다. 관리자에게 문의하여 토큰을 등록해주세요.")
            
        except Exception as e:
            logger.error(f"허깅페이스 정보 가져오기 실패: {e}", exc_info=True)
            raise
    
    
    def download_qa_data_from_s3(self, s3_url: str) -> Optional[List[Dict]]:
        """
        S3에서 QA 데이터 다운로드
        Args:
            s3_url: S3 QA 데이터 URL
        Returns:
            QA 데이터 리스트
        """
        try:
            # S3 URL에서 키 추출
            if 'amazonaws.com/' in s3_url:
                s3_key = s3_url.split('amazonaws.com/')[-1]
            else:
                logger.error(f"잘못된 S3 URL 형식: {s3_url}")
                return None
            
            # S3에서 파일 내용 가져오기
            if not self.s3_service.is_available():
                logger.error("S3 서비스를 사용할 수 없습니다")
                return None
            
            response = self.s3_service.s3_client.get_object(
                Bucket=self.s3_service.bucket_name,
                Key=s3_key
            )
            
            content = response['Body'].read().decode('utf-8')
            qa_pairs = []
            
            for line in content.splitlines():
                if not line.strip(): # 빈 줄 건너뛰기
                    continue
                
                try:
                    data = json.loads(line)
                    
                    # Case 1: Top-level object contains 'qa_pairs' list
                    if isinstance(data, dict) and 'qa_pairs' in data and isinstance(data['qa_pairs'], list):
                        for item in data['qa_pairs']:
                            if isinstance(item, dict) and 'question' in item and 'answer' in item:
                                qa_pairs.append({"question": item['question'], "answer": item['answer']})
                            else:
                                logger.warning(f"S3 QA 데이터: 'qa_pairs' 내부에 유효하지 않은 QA 쌍 발견: {item}")
                    
                    # Case 2: Single QA pair as a top-level object
                    elif isinstance(data, dict) and 'question' in data and 'answer' in data:
                        qa_pairs.append({"question": data['question'], "answer": data['answer']})
                    
                    # Case 3: OpenAI batch result format
                    elif ('response' in data and isinstance(data['response'], dict) and
                          'body' in data['response'] and isinstance(data['response']['body'], dict) and
                          'choices' in data['response']['body'] and isinstance(data['response']['body']['choices'], list) and
                          len(data['response']['body']['choices']) > 0 and
                          'message' in data['response']['body']['choices'][0] and isinstance(data['response']['body']['choices'][0]['message'], dict) and
                          'content' in data['response']['body']['choices'][0]['message']):
                        
                        message_content = data['response']['body']['choices'][0]['message']['content']
                        if 'Q:' in message_content and 'A:' in message_content:
                            parts = message_content.split('A:', 1)
                            if len(parts) == 2:
                                question = parts[0].replace('Q:', '').strip()
                                answer = parts[1].strip()
                                qa_pairs.append({"question": question, "answer": answer})
                            else:
                                logger.warning(f"S3 QA 데이터: OpenAI 형식에서 Q:A: 파싱 실패: {message_content}")
                        else:
                            # Q: 또는 A: 키워드가 없는 경우, custom_id에서 질문을 추출하고 응답을 답변으로 사용
                            logger.info(f"S3 QA 데이터: 키워드 없는 형식 처리 시작 - 데이터 구조: {list(data.keys())}")
                            
                            if 'custom_id' in data:
                                custom_id = data['custom_id']
                                logger.info(f"S3 QA 데이터: custom_id 확인: {custom_id}")
                                
                                # custom_id가 질문을 포함하고 있는지 확인하고 파싱
                                # 일반적으로 custom_id에 질문이나 질문 식별자가 포함되어 있을 수 있음
                                
                                # 1. request 필드가 있는 경우 우선 처리
                                if 'request' in data and 'body' in data['request']:
                                    request_body = data['request']['body']
                                    logger.info(f"S3 QA 데이터: request body 구조: {list(request_body.keys()) if isinstance(request_body, dict) else 'not dict'}")
                                    
                                    if 'messages' in request_body and isinstance(request_body['messages'], list):
                                        # 사용자 메시지에서 질문 추출
                                        user_message = None
                                        for msg in request_body['messages']:
                                            if msg.get('role') == 'user':
                                                user_message = msg.get('content', '')
                                                break
                                        
                                        if user_message:
                                            # 질문을 추출하고 답변으로 message_content 사용
                                            qa_pairs.append({"question": user_message, "answer": message_content})
                                            logger.info(f"S3 QA 데이터: request에서 QA 쌍 추출 성공 - Q: {user_message[:50]}...")
                                        else:
                                            logger.warning(f"S3 QA 데이터: 요청에서 사용자 메시지를 찾을 수 없음")
                                    else:
                                        logger.warning(f"S3 QA 데이터: 요청에 messages 필드가 없음")
                                else:
                                    # 2. request 필드가 없는 경우, custom_id를 질문으로 사용하거나 기본 질문 생성
                                    # custom_id에서 의미 있는 질문을 추출하거나, 범용 질문을 생성
                                    
                                    # custom_id가 "qa_" 로 시작하는 경우 등 패턴 확인
                                    if custom_id.startswith('qa_') and len(custom_id) > 3:
                                        # custom_id에서 질문 부분 추출 시도
                                        potential_question = custom_id[3:].replace('_', ' ')
                                        if len(potential_question) > 5:  # 최소 길이 체크
                                            qa_pairs.append({"question": potential_question, "answer": message_content})
                                            logger.info(f"S3 QA 데이터: custom_id에서 QA 쌍 추출 성공 - Q: {potential_question[:50]}...")
                                        else:
                                            # 범용 질문 생성
                                            default_question = "이에 대해 답변해 주세요."
                                            qa_pairs.append({"question": default_question, "answer": message_content})
                                            logger.info(f"S3 QA 데이터: 기본 질문으로 QA 쌍 생성 - A: {message_content[:50]}...")
                                    else:
                                        # 범용 질문 생성
                                        default_question = "이에 대해 답변해 주세요."
                                        qa_pairs.append({"question": default_question, "answer": message_content})
                                        logger.info(f"S3 QA 데이터: 기본 질문으로 QA 쌍 생성 - A: {message_content[:50]}...")
                            else:
                                logger.warning(f"S3 QA 데이터: OpenAI 형식에서 Q: 또는 A: 키워드 없음: {message_content}")
                    
                    # Case 4: Top-level list of QA pairs (less common for JSONL, but possible)
                    elif isinstance(data, list):
                        for item in data:
                            if isinstance(item, dict) and 'question' in item and 'answer' in item:
                                qa_pairs.append({"question": item['question'], "answer": item['answer']})
                            else:
                                logger.warning(f"S3 QA 데이터: 리스트 내부에 유효하지 않은 QA 쌍 발견: {item}")
                    
                    else:
                        logger.warning(f"S3 QA 데이터: 알 수 없는 JSON 형식 발견 (줄 건너뛰기): {line.strip()}")
                        
                except json.JSONDecodeError as e:
                    logger.warning(f"S3 QA 데이터: JSON 파싱 오류 (줄 건너뛰기): {e} - 줄 내용: {line.strip()}")
                    continue
            
            if not qa_pairs:
                logger.error("S3에서 유효한 QA 데이터를 추출하지 못했습니다.")
                return None
            
            logger.info(f"S3에서 QA 데이터 다운로드 및 파싱 완료: {len(qa_pairs)}개")
            return qa_pairs
                
        except Exception as e:
            logger.error(f"S3에서 QA 데이터 다운로드 실패: {e}", exc_info=True)
            return None
    
    async def prepare_finetuning_data(self, qa_data: List[Dict], influencer_data: AIInfluencer) -> tuple[List[Dict], str]:
        """
        파인튜닝용 데이터 준비
        Args:
            qa_data: QA 데이터
            influencer_data: AIInfluencer 객체
        Returns:
            (파인튜닝용 데이터, 시스템 메시지) 튜플
        """
        try:
            # 인플루언서 정보 추출
            influencer_name = influencer_data.influencer_name
            personality = getattr(influencer_data, 'influencer_personality', '친근하고 활발한 성격')
            style_info = getattr(influencer_data, 'influencer_description', '')
            
            # 시스템 메시지 생성 (vLLM 서버 사용)
            system_message = await create_system_message(influencer_name, personality, style_info)

            # QA 데이터 변환 (vLLM 서버 사용)
            finetuning_data = await convert_qa_data_for_finetuning(
                qa_data, influencer_name, personality, style_info
            )
            
            logger.info(f"파인튜닝 데이터 준비 완료: {len(finetuning_data)}개 항목")
            return finetuning_data, system_message
            
        except Exception as e:
            logger.error(f"파인튜닝 데이터 준비 실패: {e}")
            raise
    
    async def run_finetuning(self, qa_data: List[Dict], system_message: str, hf_repo_id: str, hf_token: str, epochs: int = 5) -> Optional[str]:
        """
        파인튜닝 실행 (VLLM 서버 우선, 로컬 폴백)
        Args:
            qa_data: 훈련 데이터 (QA 쌍 리스트)
            system_message: 시스템 메시지
            hf_repo_id: Hugging Face Repository ID
            hf_token: 허깅페이스 토큰
            epochs: 훈련 에포크 수
        Returns:
            HF 모델 URL (성공 시), None (실패 시)
        """
        try:
            logger.info(f"파인튜닝 시작: {hf_repo_id}")

            # VLLM 서버 상태 확인
            if not await vllm_health_check():
                logger.error("VLLM 서버가 비활성화되었거나 연결할 수 없습니다.")
                return None

            try:
                logger.info(f"🚀 VLLM 서버에서 파인튜닝 실행: {hf_repo_id}")
                
                # 인플루언서 정보 추출 (QA 데이터에서)
                influencer_name = hf_repo_id.split('/')[-1].replace('-finetuned', '')
                personality = "친근하고 활발한 성격"  # 기본값
                
                # 이미 변환된 데이터인지 확인
                is_already_converted = (qa_data and isinstance(qa_data[0], dict) and "messages" in qa_data[0])
                
                vllm_client = await get_vllm_client()
                result = await vllm_client.start_finetuning(
                    influencer_id=influencer_name,
                    influencer_name=influencer_name,
                    personality=personality,
                    qa_data=qa_data,
                    hf_repo_id=hf_repo_id,
                    hf_token=hf_token,
                    training_epochs=epochs,
                    style_info="",
                    is_converted=is_already_converted
                )
                
                task_id = result.get("task_id")
                if task_id:
                    # 파인튜닝 완료까지 대기 (폴링)
                    return await self._wait_for_vllm_finetuning(task_id, vllm_client)
                else:
                    raise Exception("VLLM 파인튜닝 작업 시작 실패")
                    
            except Exception as e:
                logger.error(f"VLLM 파인튜닝 실행 중 오류: {e}")
                return None

        except Exception as e:
            logger.error(f"파인튜닝 실행 실패: {e}")
            return None
    
    async def _wait_for_vllm_finetuning(self, task_id: str, vllm_client, timeout: int = 3600) -> Optional[str]:
        """VLLM 파인튜닝 완료 대기"""
        import asyncio
        
        start_time = datetime.now()
        
        while True:
            try:
                status = await vllm_client.get_finetuning_status(task_id)
                current_status = status.get("status")
                
                logger.info(f"VLLM 파인튜닝 상태: {current_status}")
                
                if current_status == "completed":
                    hf_model_url = status.get("hf_model_url")
                    logger.info(f"✅ VLLM 파인튜닝 완료: {hf_model_url}")
                    return hf_model_url
                    
                elif current_status == "failed":
                    error_msg = status.get("error_message", "알 수 없는 오류")
                    logger.error(f"❌ VLLM 파인튜닝 실패: {error_msg}")
                    return None
                
                # 타임아웃 확인
                elapsed = (datetime.now() - start_time).total_seconds()
                if elapsed > timeout:
                    logger.error(f"⏰ VLLM 파인튜닝 타임아웃: {timeout}초")
                    return None
                
                # 10초 대기
                await asyncio.sleep(10)
                
            except Exception as e:
                logger.error(f"VLLM 파인튜닝 상태 확인 실패: {e}")
                return None
    
    
    def start_finetuning_task(self, influencer_id: str, qa_task_id: str, 
                            s3_qa_url: str, influencer_data: AIInfluencer, db=None) -> str:
        """
        파인튜닝 작업 시작
        Args:
            influencer_id: 인플루언서 ID
            qa_task_id: QA 생성 작업 ID
            s3_qa_url: S3 QA 데이터 URL
            influencer_data: 인플루언서 정보 (딕셔너리 또는 모델 인스턴스)
            db: 데이터베이스 세션
        Returns:
            파인튜닝 작업 ID
        """
        import time
        
        # 작업 ID 생성
        task_id = f"ft_{influencer_id}_{int(time.time())}"
        
        # 인플루언서 이름 처리
        influencer_name = getattr(influencer_data, 'influencer_name', 'influencer')
        
        # 허깅페이스 토큰 정보 가져오기
        try:
            if db:
                _, hf_username = self._get_hf_info_from_influencer(influencer_data, db)
            else:
                hf_username = 'skn-team'
        except Exception as e:
            logger.warning(f"허깅페이스 사용자명 조회 실패, 기본값 사용: {e}")
            hf_username = 'skn-team'
        
        # 한글 이름을 영문으로 변환
        english_name = self._convert_korean_to_english(influencer_name)
        
        # 인플루언서 모델 repo 경로 생성 (허깅페이스 사용자명/영문이름-finetuned)
        model_repo = getattr(influencer_data, 'influencer_model_repo', '')
        
        if model_repo:
            # 기존 repo 경로가 있으면 사용
            hf_repo_id = model_repo
            safe_name = model_repo.split('/')[-1] if '/' in model_repo else model_repo
        else:
            # 새로운 repo 경로 생성
            safe_name = f"{english_name}-finetuned"
            hf_repo_id = f"{hf_username}/{safe_name}"
        
        logger.info(f"파인튜닝 리포지토리 설정: {hf_repo_id} (원본: {influencer_name} → 영문: {english_name})")
        
        # 작업 생성
        task = FineTuningTask(
            task_id=task_id,
            influencer_id=influencer_id,
            qa_task_id=qa_task_id,
            status=FineTuningStatus.PENDING,
            s3_qa_url=s3_qa_url,
            model_name=safe_name,
            hf_repo_id=hf_repo_id
        )
        
        self.tasks[task_id] = task
        logger.info(f"파인튜닝 작업 생성: {task_id}")
        
        return task_id
    
    async def execute_finetuning_task(self, task_id: str, influencer_data: AIInfluencer, hf_token: str, db=None) -> bool:
        """
        파인튜닝 작업 실행
        Args:
            task_id: 작업 ID
            influencer_data: 인플루언서 정보
            db: 데이터베이스 세션
        Returns:
            성공 여부
        """
        task = self.tasks.get(task_id)
        if not task:
            logger.error(f"파인튜닝 작업을 찾을 수 없습니다: {task_id}")
            return False
        
        try:
            # 1. 데이터 준비 단계
            task.status = FineTuningStatus.PREPARING_DATA
            task.updated_at = datetime.now()
            
            # S3에서 QA 데이터 다운로드
            qa_data = self.download_qa_data_from_s3(task.s3_qa_url)
            if not qa_data:
                raise Exception("S3에서 QA 데이터 다운로드 실패")
            
            # 파인튜닝용 데이터 준비
            finetuning_qa_data, system_message = await self.prepare_finetuning_data(qa_data, influencer_data)
            
            # 2. 파인튜닝 실행 단계
            task.status = FineTuningStatus.TRAINING
            task.updated_at = datetime.now()
            
            hf_model_url = await self.run_finetuning(
                qa_data=finetuning_qa_data,
                system_message=system_message,
                hf_repo_id=task.hf_repo_id,
                hf_token=hf_token,
                epochs=task.training_epochs
            )
            
            if hf_model_url:
                # 3. 업로드 완료
                task.status = FineTuningStatus.UPLOADING
                task.hf_model_url = hf_model_url
                task.updated_at = datetime.now()
                
                # 4. 완료
                task.status = FineTuningStatus.COMPLETED
                task.updated_at = datetime.now()
                
                logger.info(f"파인튜닝 작업 완료: {task_id} → {task.hf_model_url}")
                return True
            else:
                raise Exception(f"파인튜닝 실행 실패: 모델 URL을 반환하지 못했습니다.")
            
        except Exception as e:
            task.status = FineTuningStatus.FAILED
            task.error_message = str(e)
            task.updated_at = datetime.now()
            logger.error(f"파인튜닝 작업 실패: {task_id}, {e}")
            return False
    
    def get_task_status(self, task_id: str) -> Optional[FineTuningTask]:
        """파인튜닝 작업 상태 조회"""
        return self.tasks.get(task_id)
    
    def get_all_tasks(self) -> Dict[str, FineTuningTask]:
        """모든 파인튜닝 작업 조회"""
        return self.tasks
    
    def get_tasks_by_influencer(self, influencer_id: str) -> List[FineTuningTask]:
        """특정 인플루언서의 파인튜닝 작업 조회"""
        return [
            task for task in self.tasks.values() 
            if task.influencer_id == influencer_id
        ]
    
    def is_influencer_finetuned(self, influencer_data, db=None) -> bool:
        """
        인플루언서가 파인튜닝되었는지 확인
        Args:
            influencer_data: 인플루언서 데이터 (딕셔너리 또는 모델 인스턴스)
            db: 데이터베이스 세션
        Returns:
            파인튜닝 완료 여부
        """
        try:
            # 인플루언서 ID 추출
            if isinstance(influencer_data, dict):
                influencer_id = influencer_data.get('influencer_id')
                model_repo = influencer_data.get('influencer_model_repo', '')
            else:
                influencer_id = getattr(influencer_data, 'influencer_id', None)
                model_repo = getattr(influencer_data, 'influencer_model_repo', '')
            
            if not influencer_id:
                return False
            
            # 1. 모델 repo가 설정되어 있는지 확인
            if model_repo and model_repo.strip():
                logger.info(f"인플루언서 {influencer_id}에 모델 repo가 설정됨: {model_repo}")
                return True
            
            # 2. 완료된 파인튜닝 작업이 있는지 확인
            completed_tasks = [
                task for task in self.tasks.values() 
                if (task.influencer_id == influencer_id and 
                    task.status == FineTuningStatus.COMPLETED)
            ]
            
            if completed_tasks:
                logger.info(f"인플루언서 {influencer_id}에 완료된 파인튜닝 작업 발견: {len(completed_tasks)}개")
                return True
            
            # 3. 데이터베이스에서 완료된 파인튜닝 기록 확인
            if db:
                from app.models.influencer import BatchKey as BatchJob
                completed_finetuning = db.query(BatchJob).filter(
                    BatchJob.influencer_id == influencer_id,
                    BatchJob.is_finetuning_started == True,
                    BatchJob.status == "completed"
                ).first()
                
                if completed_finetuning:
                    logger.info(f"인플루언서 {influencer_id}에 데이터베이스에서 완료된 파인튜닝 발견")
                    return True
            
            logger.info(f"인플루언서 {influencer_id}는 아직 파인튜닝되지 않음")
            return False
            
        except Exception as e:
            logger.error(f"파인튜닝 상태 확인 중 오류: {e}")
            return False
    
    async def start_finetuning_for_influencer(self, influencer_id: str, s3_qa_file_url: str, db) -> bool:
        """
        인플루언서를 위한 파인튜닝 시작 (startup service용)
        Args:
            influencer_id: 인플루언서 ID  
            s3_qa_file_url: S3 QA 파일 URL
            db: 데이터베이스 세션
        Returns:
            성공 여부
        """
        try:
            # 인플루언서 정보 가져오기
            from app.services.influencers.crud import get_influencer_by_id
            
            user_id = "system"  # 시스템 작업으로 처리
            influencer_data = get_influencer_by_id(db, user_id, influencer_id)
            
            if not influencer_data:
                logger.error(f"인플루언서를 찾을 수 없습니다: {influencer_id}")
                return False
            
            # 허깅페이스 토큰 정보 가져오기
            hf_token, hf_username = self._get_hf_info_from_influencer(influencer_data, db)

            # 파인튜닝 작업 시작 (모델 인스턴스 직접 사용)
            task_id = self.start_finetuning_task(
                influencer_id=influencer_id,
                qa_task_id=f"startup_restart_{influencer_id}",
                s3_qa_url=s3_qa_file_url,
                influencer_data=influencer_data,  # 모델 인스턴스 직접 전달
                db=db
            )
            
            # 파인튜닝 실행
            success = await self.execute_finetuning_task(task_id, influencer_data, hf_token, db)
            
            if success:
                logger.info(f"✅ 인플루언서 파인튜닝 자동 시작 성공: {influencer_id}")
            else:
                logger.error(f"❌ 인플루언서 파인튜닝 자동 시작 실패: {influencer_id}")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ 인플루언서 파인튜닝 시작 중 오류: {influencer_id}, {str(e)}")
            return False


# 전역 파인튜닝 서비스 인스턴스
finetuning_service = InfluencerFineTuningService()


def get_finetuning_service() -> InfluencerFineTuningService:
    """파인튜닝 서비스 의존성 주입용 함수"""
    return finetuning_service
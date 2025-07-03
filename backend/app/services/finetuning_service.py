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
from app.core.encryption import decrypt_sensitive_data
from app.models.influencer import AIInfluencer

logger = logging.getLogger(__name__)


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
        """
        한글 이름을 영문으로 변환
        Args:
            korean_name: 한글 이름
        Returns:
            영문 변환된 이름
        """
        # 한글을 로마자로 변환하는 간단한 매핑
        korean_to_roman = {
            'ㄱ': 'g', 'ㄴ': 'n', 'ㄷ': 'd', 'ㄹ': 'r', 'ㅁ': 'm', 'ㅂ': 'b', 'ㅅ': 's',
            'ㅇ': '', 'ㅈ': 'j', 'ㅊ': 'ch', 'ㅋ': 'k', 'ㅌ': 't', 'ㅍ': 'p', 'ㅎ': 'h',
            'ㅏ': 'a', 'ㅑ': 'ya', 'ㅓ': 'eo', 'ㅕ': 'yeo', 'ㅗ': 'o', 'ㅛ': 'yo', 'ㅜ': 'u',
            'ㅠ': 'yu', 'ㅡ': 'eu', 'ㅣ': 'i', 'ㅐ': 'ae', 'ㅒ': 'yae', 'ㅔ': 'e', 'ㅖ': 'ye',
            'ㅘ': 'wa', 'ㅙ': 'wae', 'ㅚ': 'oe', 'ㅝ': 'wo', 'ㅞ': 'we', 'ㅟ': 'wi', 'ㅢ': 'ui'
        }
        
        # 간단한 한글 단어 매핑 (일반적인 이름들)
        name_mapping = {
            '루시우': 'lucio',
            '아나': 'ana', 
            '메르시': 'mercy',
            '트레이서': 'tracer',
            '위도우메이커': 'widowmaker',
            '솔져': 'soldier',
            '라인하르트': 'reinhardt',
            '디바': 'dva',
            '윈스턴': 'winston',
            '겐지': 'genji',
            '한조': 'hanzo',
            '맥크리': 'mccree',
            '파라': 'pharah',
            '리퍼': 'reaper',
            '토르비욘': 'torbjorn',
            '바스티온': 'bastion',
            '시메트라': 'symmetra',
            '젠야타': 'zenyatta'
        }
        
        # 직접 매핑이 있는 경우 사용
        if korean_name in name_mapping:
            return name_mapping[korean_name]
        
        # 간단한 변환: 영문자와 숫자만 남기고 나머지는 제거
        result = ""
        for char in korean_name:
            if char.isalnum():
                if 'a' <= char <= 'z' or 'A' <= char <= 'Z' or '0' <= char <= '9':
                    result += char.lower()
                else:
                    # 한글인 경우 간단히 처리
                    result += 'ko'
            elif char in ['-', '_']:
                result += char
        
        # 결과가 비어있거나 너무 짧으면 기본값 사용
        if not result or len(result) < 2:
            result = f"influencer_{hash(korean_name) % 10000}"
        
        return result
    
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
    
    def convert_qa_data_for_finetuning(self, qa_data: List[Dict], influencer_name: str, 
                                     personality: str, style_info: str = "") -> List[Dict]:
        """
        QA 데이터를 파인튜닝용 형식으로 변환
        Args:
            qa_data: S3에서 가져온 QA 쌍 데이터
            influencer_name: 인플루언서 이름
            personality: 성격 정보
            style_info: 스타일 정보
        Returns:
            파인튜닝용 데이터
        """
        finetuning_data = []
        
        # 시스템 메시지 생성
        system_message = self._create_system_message(influencer_name, personality, style_info)
        
        for qa_pair in qa_data:
            question = qa_pair.get('question', '').strip()
            answer = qa_pair.get('answer', '').strip()
            
            if not question:
                logger.error(f"QA 쌍에서 'question' 필드를 찾을 수 없거나 비어 있습니다: {qa_pair}")
            if not answer:
                logger.error(f"QA 쌍에서 'answer' 필드를 찾을 수 없거나 비어 있습니다: {qa_pair}")

            if question and answer:
                # EXAONE 모델용 채팅 형식으로 변환
                formatted_data = {
                    "messages": [
                        {"role": "system", "content": system_message},
                        {"role": "user", "content": question},
                        {"role": "assistant", "content": answer}
                    ]
                }
                finetuning_data.append(formatted_data)
        
        logger.info(f"QA 데이터 변환 완료: {len(qa_data)}개 → {len(finetuning_data)}개")
        return finetuning_data
    
    def _create_system_message(self, influencer_name: str, personality: str, style_info: str = "") -> str:
        """
        인플루언서용 시스템 메시지 생성
        Args:
            influencer_name: 인플루언서 이름
            personality: 성격 정보
            style_info: 스타일 정보
        Returns:
            시스템 메시지
        """
        system_msg = f"""당신은 {influencer_name}입니다.

성격과 특징:
{personality}

"""
        
        if style_info:
            system_msg += f"""스타일 정보:
{style_info}

"""
        
        system_msg += f"""이 캐릭터의 성격과 말투를 완벽하게 재현하여 답변해주세요.
- 항상 캐릭터의 개성이 드러나도록 답변하세요
- 일관된 말투와 어조를 유지하세요
- 캐릭터의 특징적인 표현이나 어미를 사용하세요
- 자연스럽고 매력적인 대화를 이끌어가세요"""
        
        return system_msg
    
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
    
    def prepare_finetuning_data(self, qa_data: List[Dict], influencer_data: AIInfluencer) -> tuple[List[Dict], str]:
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
            
            # 시스템 메시지 생성
            system_message = self._create_system_message(influencer_name, personality, style_info)

            # QA 데이터 변환
            finetuning_data = self.convert_qa_data_for_finetuning(
                qa_data, influencer_name, personality, style_info
            )
            
            logger.info(f"파인튜닝 데이터 준비 완료: {len(finetuning_data)}개 항목")
            return finetuning_data, system_message
            
        except Exception as e:
            logger.error(f"파인튜닝 데이터 준비 실패: {e}")
            raise
    
    def run_finetuning(self, qa_data: List[Dict], system_message: str, hf_repo_id: str, hf_token: str, epochs: int = 5) -> Optional[str]:
        """
        파인튜닝 실행
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

            # 현재 디렉토리를 pipeline 폴더로 변경
            original_dir = os.getcwd()
            pipeline_dir = os.path.join(os.path.dirname(__file__), '../../pipeline')
            pipeline_dir = os.path.abspath(pipeline_dir)

            try:
                os.chdir(pipeline_dir)

                # fine_custom.py 임포트 및 실행
                import sys
                if pipeline_dir not in sys.path:
                    sys.path.insert(0, pipeline_dir)
                
                # fine_custom 모듈 실행
                import fine_custom
                hf_model_url = fine_custom.main(
                    qa_data=qa_data,
                    system_message=system_message,
                    hf_token=hf_token,
                    hf_repo_id=hf_repo_id,
                    training_epochs=epochs
                )

                if hf_model_url:
                    logger.info(f"파인튜닝 완료: {hf_model_url}")
                    return hf_model_url
                else:
                    raise Exception("파인튜닝 실행 실패 또는 모델 URL 반환 실패")

            finally:
                # 원래 디렉토리로 복원
                os.chdir(original_dir)

        except Exception as e:
            logger.error(f"파인튜닝 실행 실패: {e}")
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
    
    def execute_finetuning_task(self, task_id: str, influencer_data: AIInfluencer, hf_token: str, db=None) -> bool:
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
            finetuning_qa_data, system_message = self.prepare_finetuning_data(qa_data, influencer_data)
            
            # 2. 파인튜닝 실행 단계
            task.status = FineTuningStatus.TRAINING
            task.updated_at = datetime.now()
            
            hf_model_url = self.run_finetuning(
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
            
            # 파인튜닝 실행 (백그라운드에서)
            import asyncio
            from functools import partial
            
            # 동기 함수를 비동기로 실행
            loop = asyncio.get_event_loop()
            execute_task = partial(self.execute_finetuning_task, task_id, influencer_data, hf_token, db)
            success = await loop.run_in_executor(None, execute_task)
            
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
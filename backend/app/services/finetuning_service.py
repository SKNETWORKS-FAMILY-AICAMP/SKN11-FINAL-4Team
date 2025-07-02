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
        
        # 환경변수에서 설정 가져오기
        self.hf_token = os.getenv('HF_TOKEN')
        self.base_model = os.getenv('FINETUNING_BASE_MODEL', 'LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct')
        
        if not self.hf_token:
            logger.warning("HF_TOKEN 환경변수가 설정되지 않았습니다. Hugging Face 업로드가 불가능합니다.")
    
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
            
            # 임시 파일에 다운로드
            with tempfile.NamedTemporaryFile(mode='w+', suffix='.json', delete=False) as temp_file:
                temp_path = temp_file.name
            
            try:
                # S3에서 파일 내용 가져오기
                if not self.s3_service.is_available():
                    logger.error("S3 서비스를 사용할 수 없습니다")
                    return None
                
                response = self.s3_service.s3_client.get_object(
                    Bucket=self.s3_service.bucket_name,
                    Key=s3_key
                )
                
                # JSON 데이터 파싱
                content = response['Body'].read().decode('utf-8')
                data = json.loads(content)
                
                # QA 쌍 추출
                if isinstance(data, dict) and 'qa_pairs' in data:
                    qa_pairs = data['qa_pairs']
                elif isinstance(data, list):
                    qa_pairs = data
                else:
                    logger.error("예상하지 못한 데이터 형식입니다")
                    return None
                
                logger.info(f"S3에서 QA 데이터 다운로드 완료: {len(qa_pairs)}개")
                return qa_pairs
                
            finally:
                # 임시 파일 정리
                if os.path.exists(temp_path):
                    os.unlink(temp_path)
                    
        except Exception as e:
            logger.error(f"S3에서 QA 데이터 다운로드 실패: {e}")
            return None
    
    def prepare_finetuning_data(self, qa_data: List[Dict], influencer_data: Dict, 
                              output_file: str) -> bool:
        """
        파인튜닝용 데이터 파일 준비
        Args:
            qa_data: QA 데이터
            influencer_data: 인플루언서 정보
            output_file: 출력 파일 경로
        Returns:
            성공 여부
        """
        try:
            # 인플루언서 정보 추출
            influencer_name = influencer_data.get('influencer_name', '인플루언서')
            personality = influencer_data.get('personality', '친근하고 활발한 성격')
            style_info = influencer_data.get('style_info', '')
            
            # QA 데이터 변환
            finetuning_data = self.convert_qa_data_for_finetuning(
                qa_data, influencer_name, personality, style_info
            )
            
            # 파일로 저장
            output_data = {
                "data": [
                    {
                        "question": item["messages"][1]["content"],
                        "answer": item["messages"][2]["content"]
                    }
                    for item in finetuning_data
                ]
            }
            
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(output_data, f, ensure_ascii=False, indent=2)
            
            logger.info(f"파인튜닝 데이터 파일 생성: {output_file} ({len(finetuning_data)}개 항목)")
            return True
            
        except Exception as e:
            logger.error(f"파인튜닝 데이터 준비 실패: {e}")
            return False
    
    def run_finetuning(self, data_file: str, model_name: str, epochs: int = 5) -> tuple[bool, str]:
        """
        파인튜닝 실행
        Args:
            data_file: 훈련 데이터 파일 경로
            model_name: 모델 이름 (HF repo ID로 사용)
            epochs: 훈련 에포크 수
        Returns:
            (성공 여부, HF 모델 URL)
        """
        try:
            logger.info(f"파인튜닝 시작: {data_file} → {model_name}")
            
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
                
                # 환경변수 설정
                os.environ['HF_REPO_ID'] = model_name
                if self.hf_token:
                    os.environ['HF_TOKEN'] = self.hf_token
                
                # 데이터 파일을 pipeline 디렉토리로 복사
                target_data_file = os.path.join(pipeline_dir, 'new_qa.json')
                shutil.copy2(data_file, target_data_file)
                
                try:
                    # fine_custom 모듈 실행
                    import fine_custom
                    fine_custom.main()
                    
                    # 성공 시 HF URL 생성
                    hf_url = f"https://huggingface.co/{model_name}"
                    logger.info(f"파인튜닝 완료: {hf_url}")
                    return True, hf_url
                    
                except Exception as e:
                    logger.error(f"파인튜닝 실행 중 오류: {e}")
                    return False, str(e)
                
                finally:
                    # 임시 파일 정리
                    if os.path.exists(target_data_file):
                        os.remove(target_data_file)
                
            finally:
                # 원래 디렉토리로 복원
                os.chdir(original_dir)
                
        except Exception as e:
            logger.error(f"파인튜닝 실행 실패: {e}")
            return False, str(e)
    
    def start_finetuning_task(self, influencer_id: str, qa_task_id: str, 
                            s3_qa_url: str, influencer_data: Dict) -> str:
        """
        파인튜닝 작업 시작
        Args:
            influencer_id: 인플루언서 ID
            qa_task_id: QA 생성 작업 ID
            s3_qa_url: S3 QA 데이터 URL
            influencer_data: 인플루언서 정보
        Returns:
            파인튜닝 작업 ID
        """
        import time
        
        # 작업 ID 생성
        task_id = f"ft_{influencer_id}_{int(time.time())}"
        
        # HF repo ID 생성
        influencer_name = influencer_data.get('influencer_name', 'influencer')
        # 안전한 repo 이름 생성 (특수문자 제거)
        safe_name = ''.join(c for c in influencer_name if c.isalnum() or c in '-_').lower()
        hf_repo_id = f"skn-team/{safe_name}-finetuned"
        
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
    
    def execute_finetuning_task(self, task_id: str, influencer_data: Dict) -> bool:
        """
        파인튜닝 작업 실행
        Args:
            task_id: 작업 ID
            influencer_data: 인플루언서 정보
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
            
            # 임시 파일 생성
            temp_data_file = tempfile.NamedTemporaryFile(
                mode='w', suffix='.json', delete=False
            ).name
            
            try:
                # 파인튜닝용 데이터 준비
                if not self.prepare_finetuning_data(qa_data, influencer_data, temp_data_file):
                    raise Exception("파인튜닝 데이터 준비 실패")
                
                # 2. 파인튜닝 실행 단계
                task.status = FineTuningStatus.TRAINING
                task.updated_at = datetime.now()
                
                success, result = self.run_finetuning(
                    temp_data_file, 
                    task.hf_repo_id, 
                    task.training_epochs
                )
                
                if success:
                    # 3. 업로드 완료
                    task.status = FineTuningStatus.UPLOADING
                    task.hf_model_url = result
                    task.updated_at = datetime.now()
                    
                    # 4. 완료
                    task.status = FineTuningStatus.COMPLETED
                    task.updated_at = datetime.now()
                    
                    logger.info(f"파인튜닝 작업 완료: {task_id} → {task.hf_model_url}")
                    return True
                else:
                    raise Exception(f"파인튜닝 실행 실패: {result}")
                
            finally:
                # 임시 파일 정리
                if os.path.exists(temp_data_file):
                    os.unlink(temp_data_file)
            
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
            
            # 인플루언서 데이터를 딕셔너리로 변환
            influencer_dict = {
                'influencer_name': influencer_data.influencer_name,
                'personality': getattr(influencer_data, 'influencer_personality', '친근하고 활발한 성격'),
                'style_info': getattr(influencer_data, 'influencer_description', '')
            }
            
            # 파인튜닝 작업 시작
            task_id = self.start_finetuning_task(
                influencer_id=influencer_id,
                qa_task_id=f"startup_restart_{influencer_id}",
                s3_qa_url=s3_qa_file_url,
                influencer_data=influencer_dict
            )
            
            # 파인튜닝 실행 (백그라운드에서)
            import asyncio
            from functools import partial
            
            # 동기 함수를 비동기로 실행
            loop = asyncio.get_event_loop()
            execute_task = partial(self.execute_finetuning_task, task_id, influencer_dict)
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
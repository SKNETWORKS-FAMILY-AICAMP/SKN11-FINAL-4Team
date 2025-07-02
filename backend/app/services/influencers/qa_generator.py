#!/usr/bin/env python3
"""
인플루언서 전용 QA 생성 서비스
speech_generator와 generate_qa 로직을 활용하여 인플루언서별 2000쌍의 QA 생성
"""

import json
import os
import time
import random
from typing import List, Dict, Optional
from openai import OpenAI
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.influencers.crud import get_influencer_by_id
from pipeline.speech_generator import CharacterProfile, Gender, SpeechGenerator


class QAGenerationStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"  
    BATCH_SUBMITTED = "batch_submitted"
    BATCH_PROCESSING = "batch_processing"
    BATCH_COMPLETED = "batch_completed"
    PROCESSING_RESULTS = "processing_results"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class QAGenerationTask:
    task_id: str
    influencer_id: str
    status: QAGenerationStatus
    batch_id: Optional[str] = None
    total_qa_pairs: int = 2000
    generated_qa_pairs: int = 0
    error_message: Optional[str] = None
    s3_urls: Optional[Dict] = None
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()


class InfluencerQAGenerator:
    def __init__(self, api_key: Optional[str] = None):
        """
        인플루언서용 QA 생성기
        Args:
            api_key: OpenAI API 키
        """
        self.client = OpenAI(api_key=api_key or os.getenv('OPENAI_API_KEY'))
        self.speech_generator = SpeechGenerator(api_key)
        self.tasks: Dict[str, QAGenerationTask] = {}
        
    def influencer_to_character_profile(self, influencer_data: dict, style_preset: dict = None, mbti: dict = None) -> CharacterProfile:
        """
        인플루언서 데이터를 CharacterProfile로 변환
        Args:
            influencer_data: DB에서 가져온 인플루언서 데이터
            style_preset: 스타일 프리셋 데이터
            mbti: MBTI 데이터
        Returns:
            CharacterProfile 객체
        """
        # 성별 매핑 (influencer_gender: 1=남성, 2=여성, 3=중성)
        gender_map = {
            1: Gender.MALE,
            2: Gender.FEMALE, 
            3: Gender.NON_BINARY
        }
        
        # 나이대 매핑 (influencer_age_group: 1=10대, 2=20대, 3=30대, 4=40대, 5=50대+)
        age_group_map = {
            1: 15,  # 10대
            2: 25,  # 20대  
            3: 35,  # 30대
            4: 45,  # 40대
            5: 55   # 50대+
        }
        
        # 기본값 설정
        name = influencer_data.get('influencer_name', '인플루언서')
        description = influencer_data.get('influencer_description', '')
        
        # 스타일 프리셋에서 정보 추출
        if style_preset:
            gender = gender_map.get(style_preset.get('influencer_gender', 3), Gender.NON_BINARY)
            age = age_group_map.get(style_preset.get('influencer_age_group', 2), 25)
            personality = style_preset.get('influencer_personality', '친근하고 활발한 성격')
            
            # 설명에 스타일 정보 추가
            if not description:
                hairstyle = style_preset.get('influencer_hairstyle', '')
                style = style_preset.get('influencer_style', '')
                speech = style_preset.get('influencer_speech', '')
                description = f"헤어스타일: {hairstyle}, 스타일: {style}, 말투: {speech}"
        else:
            gender = Gender.NON_BINARY
            age = 25
            personality = '친근하고 활발한 성격'
            
        # MBTI 정보 추출
        if mbti:
            mbti_type = mbti.get('mbti_name', 'ENFP')
            # 성격에 MBTI 특성 추가
            mbti_traits = mbti.get('mbti_traits', '')
            if mbti_traits:
                personality += f" ({mbti_traits})"
        else:
            mbti_type = 'ENFP'  # 기본값
            
        return CharacterProfile(
            name=name,
            description=description,
            age=age,
            gender=gender,
            personality=personality,
            mbti=mbti_type
        )
    
    def create_qa_batch_requests(self, character: CharacterProfile, num_requests: int = 2000) -> List[Dict]:
        """
        인플루언서 캐릭터를 위한 QA 생성 배치 요청 생성
        Args:
            character: 캐릭터 프로필
            num_requests: 생성할 QA 개수
        Returns:
            배치 요청 리스트
        """
        # 다양한 질문 주제들
        question_topics = [
            "일상생활과 취미",
            "패션과 뷰티",
            "여행과 맛집",
            "연애와 관계",
            "직업과 커리어", 
            "건강과 운동",
            "문화와 엔터테인먼트",
            "소셜미디어와 트렌드",
            "자기계발과 성장",
            "가족과 친구들",
            "쇼핑과 소비",
            "음식과 요리",
            "스트레스와 힐링",
            "미래와 꿈",
            "추억과 경험"
        ]
        
        requests = []
        
        # 캐릭터 프롬프트 생성
        character_prompt = self.speech_generator.create_character_prompt(character)
        
        for i in range(num_requests):
            topic = random.choice(question_topics)
            
            request = {
                "custom_id": f"influencer_qa_{character.name}_{i+1}",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": "gpt-4o-mini",
                    "messages": [
                        {
                            "role": "system",
                            "content": character_prompt
                        },
                        {
                            "role": "user",
                            "content": f"'{topic}' 주제에 대한 자연스러운 질문을 하나 만들고, 당신의 캐릭터와 말투로 답변해주세요. 형식: Q: [질문] A: [답변]"
                        }
                    ],
                    "max_tokens": 300,
                    "temperature": 0.8
                }
            }
            requests.append(request)
        
        return requests
    
    def save_batch_file(self, requests: List[Dict], task_id: str) -> str:
        """배치 요청을 JSONL 파일로 저장"""
        filename = f"influencer_qa_batch_{task_id}.jsonl"
        filepath = os.path.join("/tmp", filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            for request in requests:
                f.write(json.dumps(request, ensure_ascii=False) + '\n')
        
        return filepath
    
    def submit_batch_job(self, batch_file_path: str, task_id: str) -> str:
        """OpenAI 배치 작업 제출"""
        print(f"배치 파일 업로드 중: {batch_file_path}")
        
        # 파일 업로드
        with open(batch_file_path, 'rb') as f:
            batch_input_file = self.client.files.create(
                file=f,
                purpose="batch"
            )
        
        print(f"파일 업로드 완료: {batch_input_file.id}")
        
        # 배치 작업 생성
        batch = self.client.batches.create(
            input_file_id=batch_input_file.id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
            metadata={
                "description": f"Influencer QA pairs generation - Task ID: {task_id}",
                "task_id": task_id
            }
        )
        
        print(f"배치 작업 생성 완료: {batch.id}")
        return batch.id
    
    def check_batch_status(self, batch_id: str) -> Dict:
        """배치 작업 상태 확인"""
        batch = self.client.batches.retrieve(batch_id)
        return {
            "id": batch.id,
            "status": batch.status,
            "request_counts": batch.request_counts.__dict__ if batch.request_counts else None,
            "created_at": batch.created_at,
            "completed_at": batch.completed_at,
            "output_file_id": batch.output_file_id if hasattr(batch, 'output_file_id') else None,
            "error_file_id": batch.error_file_id if hasattr(batch, 'error_file_id') else None
        }
    
    def download_batch_results(self, batch_id: str, task_id: str) -> Optional[str]:
        """배치 결과 다운로드"""
        batch = self.client.batches.retrieve(batch_id)
        
        if batch.status != "completed":
            print(f"배치 작업이 아직 완료되지 않았습니다. 현재 상태: {batch.status}")
            return None
        
        if not batch.output_file_id:
            print("출력 파일 ID가 없습니다.")
            return None
        
        # 결과 파일 다운로드
        result_file_name = f"influencer_qa_results_{task_id}.jsonl"
        result_file_path = os.path.join("/tmp", result_file_name)
        
        file_response = self.client.files.content(batch.output_file_id)
        
        with open(result_file_path, 'wb') as f:
            f.write(file_response.content)
        
        print(f"결과 파일 다운로드 완료: {result_file_path}")
        return result_file_path
    
    def process_qa_results(self, result_file_path: str) -> List[Dict]:
        """결과 파일에서 QA 쌍 추출"""
        qa_pairs = []
        
        with open(result_file_path, 'r', encoding='utf-8') as f:
            for line in f:
                result = json.loads(line)
                
                if result.get('response', {}).get('status_code') == 200:
                    content = result['response']['body']['choices'][0]['message']['content']
                    
                    # Q: A: 형식으로 파싱
                    if 'Q:' in content and 'A:' in content:
                        try:
                            parts = content.split('A:', 1)
                            if len(parts) == 2:
                                question = parts[0].replace('Q:', '').strip()
                                answer = parts[1].strip()
                                
                                qa_pairs.append({
                                    "question": question,
                                    "answer": answer,
                                    "custom_id": result.get('custom_id')
                                })
                        except Exception as e:
                            print(f"QA 파싱 오류: {e}")
                            continue
        
        return qa_pairs
    
    def save_qa_pairs_to_db(self, influencer_id: str, qa_pairs: List[Dict], db: Session):
        """생성된 QA 쌍을 데이터베이스에 저장"""
        # TODO: QA 쌍을 저장할 테이블이 필요 (예: influencer_qa_pairs)
        # 현재는 JSON 파일로 임시 저장
        filename = f"influencer_{influencer_id}_qa_pairs.json"
        filepath = os.path.join("/tmp", filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(qa_pairs, f, ensure_ascii=False, indent=2)
        
        print(f"QA 쌍 {len(qa_pairs)}개가 {filepath}에 저장되었습니다.")
    
    def start_qa_generation(self, influencer_id: str, db: Session) -> str:
        """
        인플루언서를 위한 QA 생성 시작
        Args:
            influencer_id: 인플루언서 ID
            db: 데이터베이스 세션
        Returns:
            작업 ID
        """
        # 작업 ID 생성
        task_id = f"qa_{influencer_id}_{int(time.time())}"
        
        # 작업 상태 초기화
        task = QAGenerationTask(
            task_id=task_id,
            influencer_id=influencer_id,
            status=QAGenerationStatus.PENDING
        )
        self.tasks[task_id] = task
        
        try:
            # 인플루언서 데이터 가져오기
            user_id = "system"  # 시스템 작업으로 처리
            influencer_data = get_influencer_by_id(db, user_id, influencer_id)
            
            if not influencer_data:
                raise Exception(f"인플루언서를 찾을 수 없습니다: {influencer_id}")
            
            # 인플루언서 → 캐릭터 프로필 변환
            character = self.influencer_to_character_profile(
                influencer_data.__dict__,
                influencer_data.style_preset.__dict__ if influencer_data.style_preset else None,
                influencer_data.mbti.__dict__ if influencer_data.mbti else None
            )
            
            # 배치 요청 생성
            task.status = QAGenerationStatus.PROCESSING
            requests = self.create_qa_batch_requests(character, 2000)
            
            # 배치 파일 저장
            batch_file_path = self.save_batch_file(requests, task_id)
            
            # 배치 작업 제출
            batch_id = self.submit_batch_job(batch_file_path, task_id)
            
            # 작업 상태 업데이트
            task.batch_id = batch_id
            task.status = QAGenerationStatus.BATCH_SUBMITTED
            task.updated_at = datetime.now()
            
            print(f"QA 생성 작업 시작됨 - Task ID: {task_id}, Batch ID: {batch_id}")
            return task_id
            
        except Exception as e:
            task.status = QAGenerationStatus.FAILED
            task.error_message = str(e)
            task.updated_at = datetime.now()
            print(f"QA 생성 작업 실패: {e}")
            import traceback
            print(f"상세 에러 정보: {traceback.format_exc()}")
            # QA 생성 작업에서는 예외를 re-raise하지 않음
            return task_id
    
    def get_task_status(self, task_id: str) -> Optional[QAGenerationTask]:
        """작업 상태 조회"""
        return self.tasks.get(task_id)
    
    def update_task_status(self, task_id: str):
        """작업 상태 업데이트 (배치 상태 확인)"""
        task = self.tasks.get(task_id)
        if not task or not task.batch_id:
            return
        
        try:
            batch_status = self.check_batch_status(task.batch_id)
            
            if batch_status['status'] == 'completed':
                task.status = QAGenerationStatus.BATCH_COMPLETED
            elif batch_status['status'] == 'failed':
                task.status = QAGenerationStatus.FAILED
                task.error_message = "배치 작업 실패"
            elif batch_status['status'] in ['validating', 'in_progress']:
                task.status = QAGenerationStatus.BATCH_PROCESSING
            
            task.updated_at = datetime.now()
            
        except Exception as e:
            task.status = QAGenerationStatus.FAILED
            task.error_message = f"상태 확인 오류: {str(e)}"
            task.updated_at = datetime.now()
    
    def complete_qa_generation(self, task_id: str, db: Session) -> bool:
        """QA 생성 완료 처리"""
        task = self.tasks.get(task_id)
        if not task or task.status != QAGenerationStatus.BATCH_COMPLETED:
            return False
        
        try:
            task.status = QAGenerationStatus.PROCESSING_RESULTS
            
            # 배치 결과 다운로드
            result_file_path = self.download_batch_results(task.batch_id, task_id)
            if not result_file_path:
                raise Exception("결과 파일 다운로드 실패")
            
            # QA 쌍 처리
            qa_pairs = self.process_qa_results(result_file_path)
            
            # DB에 저장
            self.save_qa_pairs_to_db(task.influencer_id, qa_pairs, db)
            
            # 작업 완료
            task.status = QAGenerationStatus.COMPLETED
            task.generated_qa_pairs = len(qa_pairs)
            task.updated_at = datetime.now()
            
            print(f"QA 생성 완료 - Task ID: {task_id}, QA 쌍: {len(qa_pairs)}개")
            return True
            
        except Exception as e:
            task.status = QAGenerationStatus.FAILED
            task.error_message = f"결과 처리 오류: {str(e)}"
            task.updated_at = datetime.now()
            print(f"QA 생성 완료 처리 실패: {e}")
            return False
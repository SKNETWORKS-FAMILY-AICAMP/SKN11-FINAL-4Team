#!/usr/bin/env python3
"""
인플루언서 전용 QA 생성 서비스
speech_generator와 generate_qa 로직을 활용하여 인플루언서별 2000쌍의 QA 생성
"""

import json
import os
import time
import random
import tempfile
import logging
import requests
from typing import List, Dict, Optional
from openai import OpenAI
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.influencers.crud import get_influencer_by_id
from app.models.influencer import BatchKey
from app.core.config import settings
# Backend 내부 모델 사용
from app.models.vllm_models import Gender, VLLMCharacterProfile

# 하위 호환성을 위한 별칭
CharacterProfile = VLLMCharacterProfile

class SpeechGenerator:
    """vLLM 서버 대신 HTTP API 클라이언트 사용"""
    def __init__(self, *args, **kwargs):
        pass
    
    def generate_character_random_tones_sync(self, *args, **kwargs):
        raise RuntimeError("이 메서드는 더 이상 사용되지 않습니다. vLLM 서버 API를 사용하세요.")


class QAGenerationStatus(Enum):
    PENDING = "pending"
    PROCESSING = "processing"  
    BATCH_SUBMITTED = "batch_submitted"
    BATCH_PROCESSING = "batch_processing"
    BATCH_COMPLETED = "batch_completed"
    PROCESSING_RESULTS = "processing_results"
    COMPLETED = "completed"
    FINALIZED = "finalized"
    FAILED = "failed"


class InfluencerQAGenerator:
    def __init__(self, api_key: Optional[str] = None):
        """
        인플루언서용 QA 생성기
        Args:
            api_key: OpenAI API 키
        """
        self.client = OpenAI(api_key=api_key or os.getenv('OPENAI_API_KEY'))
        self.speech_generator = SpeechGenerator(api_key)
        
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
            gender = gender_map.get(style_preset.get('influencer_gender'), Gender.NON_BINARY)
            age_group = style_preset.get('influencer_age_group')
            age_range = f"{age_group_map.get(age_group, 25)}대" if age_group else "알 수 없음"
            personality = style_preset.get('influencer_personality', '친근하고 활발한 성격')
            
            # 설명에 스타일 정보 추가
            if not description:
                hairstyle = style_preset.get('influencer_hairstyle', '')
                style = style_preset.get('influencer_style', '')
                speech = style_preset.get('influencer_speech', '')
                description = f"헤어스타일: {hairstyle}, 스타일: {style}, 말투: {speech}"
        else:
            gender = Gender.NON_BINARY
            age_range = "알 수 없음"
            personality = '친근하고 활발한 성격'
            
        # MBTI 정보 추출
        if mbti:
            mbti_type = mbti.get('mbti_name')
            if not mbti_type:
                mbti_type = "알 수 없음"
            # 성격에 MBTI 특성 추가
            mbti_traits = mbti.get('mbti_traits', '')
            if mbti_traits:
                personality += f" ({mbti_traits})"
        else:
            mbti_type = None
            
        return CharacterProfile(
            name=name,
            description=description,
            age_range=age_range,
            gender=gender,
            personality=personality,
            mbti=mbti_type
        )
    
    def create_qa_batch_requests(self, character: CharacterProfile, num_requests: int = None, system_prompt: str = None) -> List[Dict]:
        """
        인플루언서 캐릭터를 위한 QA 생성 배치 요청 생성
        VLLM 서버의 /generate_qa 엔드포인트를 사용하여 QA 생성
        Args:
            character: 캐릭터 프로필
            num_requests: 생성할 QA 개수 (None이면 환경변수 QA_GENERATION_COUNT 사용)
        Returns:
            배치 요청 리스트
        """
        if num_requests is None:
            num_requests = settings.QA_GENERATION_COUNT
        
        # VLLM 서버 URL 설정
        vllm_server_url = getattr(settings, 'VLLM_SERVER_URL', 'http://localhost:8001')
        
        batch_requests = []
        
        # VLLM 서버에 요청할 캐릭터 프로필 데이터 준비
        character_data = {
            "name": character.name,
            "description": character.description,
            "age_range": character.age_range,
            "gender": character.gender.value if character.gender else "없음",
            "personality": character.personality,
            "mbti": character.mbti
        }
        
        # 1단계: VLLM 서버에서 질문 생성
        questions = []
        try:
            response = requests.post(
                f"{vllm_server_url}/speech/generate_questions_batch",
                json={
                    "characters": [character_data] * num_requests,
                    "num_questions_per_character": 1
                },
                timeout=60
            )
            
            if response.status_code == 200:
                question_data = response.json()
                results = question_data.get('results', [])
                
                for result in results:
                    questions.extend(result.get('questions', []))
                
                print(f"VLLM 서버 질문 생성 성공: {len(questions)}개")
            else:
                print(f"VLLM 서버 질문 생성 실패: {response.status_code} - {response.text}")
                
        except Exception as e:
            print(f"VLLM 서버 질문 생성 오류: {e}")
        
        # 2단계: 생성된 질문들에 대해 말투 생성
        if questions:
            try:
                tone_requests = []
                # 질문들을 배치로 나누어서 요청
                batch_size = min(10, len(questions))  # 한 번에 최대 10개씩
                for i in range(0, len(questions), batch_size):
                    batch_questions = questions[i:i+batch_size]
                    tone_requests.append({
                        "character": character_data,
                        "questions": batch_questions,
                        "num_tone_variations": 3
                    })
                
                response = requests.post(
                    f"{vllm_server_url}/speech/generate_tones_batch",
                    json={"requests": tone_requests},
                    timeout=120
                )
                
                if response.status_code == 200:
                    tone_data = response.json()
                    results = tone_data.get('results', [])
                    
                    print(f"VLLM 서버 말투 생성 성공: {len(results)}개 결과")
                    
                    # 각 결과를 배치 요청으로 변환
                    for i, tone_result in enumerate(results):
                        responses = tone_result.get('responses', {})
                        
                        for question, tone_responses in responses.items():
                            for tone_name, tone_response_list in tone_responses.items():
                                if tone_response_list and len(tone_response_list) > 0:
                                    tone_response = tone_response_list[0]
                                    
                                    # 시스템 프롬프트 사용 (있는 경우)
                                    system_content = system_prompt if system_prompt else "QA 쌍을 생성하는 역할입니다."
                                    
                                    request = {
                                        "custom_id": f"influencer_qa_{character.name}_{len(batch_requests)+1}_{tone_name}",
                                        "method": "POST",
                                        "url": "/v1/chat/completions",
                                        "body": {
                                            "model": "gpt-4o-mini",
                                            "messages": [
                                                {
                                                    "role": "system",
                                                    "content": system_content
                                                },
                                                {
                                                    "role": "user",
                                                    "content": f"Q: {question} A: {tone_response.get('text', '')}"
                                                }
                                            ],
                                            "max_tokens": 300,
                                            "temperature": 0.8
                                        }
                                    }
                                    batch_requests.append(request)
                                    
                                    # 요청수 제한
                                    if len(batch_requests) >= num_requests:
                                        break
                            
                            if len(batch_requests) >= num_requests:
                                break
                        
                        if len(batch_requests) >= num_requests:
                            break
                
                else:
                    print(f"VLLM 서버 말투 생성 실패: {response.status_code} - {response.text}")
                    
            except Exception as e:
                print(f"VLLM 서버 말투 생성 오류: {e}")
        
        # VLLM 서버에서 생성된 QA가 부족하면 기본 QA로 채움
        remaining_requests = num_requests - len(batch_requests)
        for i in range(remaining_requests):
            # 시스템 프롬프트 사용 (있는 경우)
            fallback_system_content = system_prompt if system_prompt else f"당신은 {character.name}라는 캐릭터입니다. 성격: {character.personality}"
            
            request = {
                "custom_id": f"influencer_qa_{character.name}_{i+1}_fallback",
                "method": "POST",
                "url": "/v1/chat/completions",
                "body": {
                    "model": "gpt-4o-mini",
                    "messages": [
                        {
                            "role": "system",
                            "content": fallback_system_content
                        },
                        {
                            "role": "user",
                            "content": "일상적인 질문 하나와 그에 대한 답변을 생성해주세요. 형식: Q: [질문] A: [답변]"
                        }
                    ],
                    "max_tokens": 300,
                    "temperature": 0.8
                }
            }
            batch_requests.append(request)
        
        return batch_requests[:num_requests]  # 요청한 개수만큼만 반환
    
    def save_batch_file(self, requests: List[Dict], task_id: str) -> str:
        """배치 요청을 JSONL 파일로 저장"""
        filename = f"influencer_qa_batch_{task_id}.jsonl"
        # OS에 맞는 임시 디렉토리 사용
        temp_dir = tempfile.gettempdir()
        filepath = os.path.join(temp_dir, filename)
        
        # 디렉토리가 존재하는지 확인하고 생성
        os.makedirs(temp_dir, exist_ok=True)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            for request in requests:
                f.write(json.dumps(request, ensure_ascii=False) + '\n')
        
        print(f"배치 파일 저장 완료: {filepath}")
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
        
        # 모니터링 방식 확인
        use_webhook = settings.OPENAI_MONITORING_MODE == 'webhook'
        
        batch_create_params = {
            "input_file_id": batch_input_file.id,
            "endpoint": "/v1/chat/completions",
            "completion_window": "24h",
            "metadata": {
                "description": f"Influencer QA pairs generation - Task ID: {task_id}",
                "task_id": task_id
            }
        }
        
        # 웹훅 모드일 때만 웹훅 URL 추가
        if use_webhook:
            batch_create_params["metadata"]["webhook_url"] = settings.OPENAI_WEBHOOK_URL
            print(f"🎯 웹훅 모드로 배치 작업 생성 중... (URL: {settings.OPENAI_WEBHOOK_URL})")
        else:
            print(f"🔄 폴링 모드로 배치 작업 생성 중... (간격: {settings.OPENAI_POLLING_INTERVAL_MINUTES}분)")
        
        # 배치 작업 생성
        batch = self.client.batches.create(**batch_create_params)
        
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
        temp_dir = tempfile.gettempdir()
        result_file_path = os.path.join(temp_dir, result_file_name)
        
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
        temp_dir = tempfile.gettempdir()
        filepath = os.path.join(temp_dir, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(qa_pairs, f, ensure_ascii=False, indent=2)
        
        print(f"QA 쌍 {len(qa_pairs)}개가 {filepath}에 저장되었습니다.")
    
    def start_qa_generation(self, influencer_id: str, db: Session, user_id: str = None) -> str:
        """
        인플루언서를 위한 QA 생성 시작
        Args:
            influencer_id: 인플루언서 ID
            db: 데이터베이스 세션
            user_id: 사용자 ID (권한 확인용)
        Returns:
            작업 ID
        """
        # 작업 ID 생성
        task_id = f"qa_{influencer_id}_{int(time.time())}"
        print(f"🎨 QA Generator: 작업 시작 - task_id={task_id}, influencer_id={influencer_id}")

        # BatchKey 모델을 사용하여 DB에 작업 기록
        import uuid
        batch_key_entry = BatchKey(
            batch_key_id=str(uuid.uuid4()),
            batch_key=task_id,  # batch_key 필드에 task_id 값 설정
            task_id=task_id,
            influencer_id=influencer_id,
            status=QAGenerationStatus.PENDING.value,
            total_qa_pairs=settings.QA_GENERATION_COUNT
        )
        db.add(batch_key_entry)
        
        try:
            db.commit()
            db.refresh(batch_key_entry)

            # 인플루언서 데이터 가져오기 (사용자 권한 확인)
            if user_id:
                # 사용자 권한으로 인플루언서 조회
                influencer_data = get_influencer_by_id(db, user_id, influencer_id)
            else:
                # 백그라운드 작업의 경우 직접 조회 (권한 우회)
                from app.models.influencer import AIInfluencer
                influencer_data = db.query(AIInfluencer).filter(AIInfluencer.influencer_id == influencer_id).first()
            
            if not influencer_data:
                raise Exception(f"인플루언서를 찾을 수 없습니다: {influencer_id}")

            # 상태 업데이트: PROCESSING
            batch_key_entry.status = QAGenerationStatus.PROCESSING.value
            db.commit()
            
            # 인플루언서 → 캐릭터 프로필 변환
            character = self.influencer_to_character_profile(
                influencer_data.__dict__,
                influencer_data.style_preset.__dict__ if influencer_data.style_preset else None,
                influencer_data.mbti.__dict__ if influencer_data.mbti else None
            )
            
            # 저장된 시스템 프롬프트 가져오기
            system_prompt = getattr(influencer_data, 'system_prompt', None)
            if system_prompt:
                print(f"✅ 저장된 시스템 프롬프트 사용: {system_prompt[:100]}...")
            else:
                print("⚠️ 저장된 시스템 프롬프트가 없어 기본 프롬프트 사용")
            
            # 배치 요청 생성 (시스템 프롬프트 포함)
            batch_requests = self.create_qa_batch_requests(character, system_prompt=system_prompt)
            
            # 배치 파일 저장
            batch_file_path = self.save_batch_file(batch_requests, task_id)
            
            # 배치 작업 제출
            batch_id = self.submit_batch_job(batch_file_path, task_id)
            
            # DB에 배치 정보 업데이트
            batch_key_entry.openai_batch_id = batch_id
            batch_key_entry.input_file_id = batch_file_path
            batch_key_entry.status = QAGenerationStatus.BATCH_SUBMITTED.value
            db.commit()
            
            print(f"✅ 배치 작업 DB에 저장 및 상태 업데이트: task_id={task_id}, batch_id={batch_id}")
            
            print(f"🎉 QA Generator: 작업 완료 - Task ID: {task_id}, Batch ID: {batch_id}, QA 개수: {settings.QA_GENERATION_COUNT}")
            return task_id
            
        except Exception as e:
            error_msg = str(e)
            print(f"❌ QA Generator: 작업 실패 - {error_msg}")
            import traceback
            print(f"🔍 QA Generator: 상세 에러 정보 - {traceback.format_exc()}")
            
            # DB에 오류 상태 업데이트
            db.rollback() # 오류 발생 시 롤백
            batch_key_entry.status = QAGenerationStatus.FAILED.value
            batch_key_entry.error_message = error_msg
            db.commit()
            
            return task_id
    
    def complete_qa_generation(self, task_id: str, db: Session) -> bool:
        """QA 생성 완료 처리 - 폴링/웹훅 모드 모두 지원"""
        logger = logging.getLogger(__name__)
        logger.info(f"🔄 QA 생성 완료 처리 시작: task_id={task_id}")
        
        try:
            # BatchKey에서 배치 정보 조회
            batch_key = db.query(BatchKey).filter(BatchKey.task_id == task_id).first()
            if not batch_key:
                logger.error(f"❌ BatchKey를 찾을 수 없음: task_id={task_id}")
                return False
            
            if not batch_key.openai_batch_id:
                logger.error(f"❌ OpenAI 배치 ID가 없음: task_id={task_id}")
                return False
            
            logger.info(f"📦 배치 정보 확인: batch_id={batch_key.openai_batch_id}, influencer_id={batch_key.influencer_id}")
            
            # 배치 결과 다운로드
            result_file_path = self.download_batch_results(batch_key.openai_batch_id, task_id)
            if not result_file_path:
                raise Exception("결과 파일 다운로드 실패")
            
            logger.info(f"📥 배치 결과 다운로드 완료: {result_file_path}")
            
            # QA 쌍 처리
            qa_pairs = self.process_qa_results(result_file_path)
            logger.info(f"🔍 QA 쌍 처리 완료: {len(qa_pairs)}개")
            
            # DB에 저장
            self.save_qa_pairs_to_db(batch_key.influencer_id, qa_pairs, db)
            logger.info(f"💾 QA 쌍 DB 저장 완료")
            
            # BatchKey 상태 업데이트
            batch_key.status = QAGenerationStatus.COMPLETED.value
            batch_key.generated_qa_pairs = len(qa_pairs)
            batch_key.completed_at = datetime.now()
            db.commit()
            logger.info(f"🧠 BatchKey 상태 업데이트 완료 (DB)")
            
            logger.info(f"✅ QA 생성 완료 - Task ID: {task_id}, QA 쌍: {len(qa_pairs)}개")
            return True
            
        except Exception as e:
            logger.error(f"❌ QA 생성 완료 처리 실패: task_id={task_id}, error={e}", exc_info=True)
            
            # DB에 오류 상태 업데이트
            if batch_key:
                db.rollback() # 오류 발생 시 롤백
                batch_key.status = QAGenerationStatus.FAILED.value
                batch_key.error_message = f"결과 처리 오류: {str(e)}"
                db.commit()
            
            return False
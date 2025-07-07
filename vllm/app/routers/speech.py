from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import uuid
import asyncio
import os
import json
import tempfile
import logging

from vllm.pipeline.speech_generator import SpeechGenerator, CharacterProfile, Gender

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory storage for tasks (for simplicity, replace with a proper DB in production)
tone_generation_tasks: Dict[str, Dict[str, Any]] = {}

class VLLMCharacterProfile(BaseModel):
    """vLLM용 캐릭터 프로필 - 어투 생성 전용"""
    name: str
    description: Optional[str] = ""
    age_range: Optional[str] = "알 수 없음"
    gender: Optional[str] = "NON_BINARY" # MALE, FEMALE, NON_BINARY
    personality: Optional[str] = "친근하고 활발한 성격"
    mbti: Optional[str] = None

class ToneGenerationRequest(BaseModel):
    """어투 생성 요청"""
    character: VLLMCharacterProfile
    num_tones: int = 3  # 생성할 어투 개수 (기본 3개)

class ToneGenerationResponse(BaseModel):
    """어투 생성 응답"""
    question: str
    responses: Dict[str, List[Dict[str, Any]]]  # 톤별 응답들

@router.post("/generate_qa", response_model=ToneGenerationResponse)
async def generate_character_qa(request: VLLMCharacterProfile):
    """
    캐릭터 기반 어투 생성 (기존 엔드포인트와 호환성 유지)
    3가지 다른 어투로 질문에 대한 답변을 생성합니다.
    """
    try:
        # OpenAI API 키 확인
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise HTTPException(status_code=500, detail="OpenAI API 키가 설정되지 않았습니다.")
        
        # CharacterProfile 객체 생성
        character_profile = CharacterProfile(
            name=request.name,
            description=request.description,
            age_range=request.age_range,
            gender=Gender[request.gender.upper()] if request.gender else Gender.NON_BINARY,
            personality=request.personality,
            mbti=request.mbti
        )
        
        # SpeechGenerator 인스턴스 생성
        speech_generator = SpeechGenerator(api_key=api_key)
        
        # 캐릭터에 맞는 질문 생성
        question = speech_generator.generate_question_for_character(character_profile)
        
        # 3가지 다른 어투로 답변 생성
        responses = {}
        for i in range(3):
            tone_name = f"tone_{i+1}"
            
            # 시스템 프롬프트 생성
            system_prompt = speech_generator.generate_system_prompt_with_gpt(
                character_profile, 
                tone_instruction_seed=f"variation_{i+1}"
            )
            
            # 답변 생성 (실제 구현에서는 speech_generator의 메서드 사용)
            try:
                # 임시: 기본 답변 생성
                answer = f"{request.name}의 {i+1}번째 어투로 답변합니다: {question}"
                
                # 어투 정보 생성
                tone_info = {
                    "description": f"어투 {i+1}",
                    "hashtags": f"#어투{i+1} #캐릭터"
                }
                
                responses[tone_name] = [{
                    "text": answer,
                    "tone_info": tone_info,
                    "system_prompt": system_prompt
                }]
                
            except Exception as e:
                logger.error(f"어투 {i+1} 생성 실패: {e}")
                # 기본 응답 제공
                responses[tone_name] = [{
                    "text": f"안녕하세요! 저는 {request.name}입니다.",
                    "tone_info": {"description": f"기본 어투 {i+1}", "hashtags": f"#기본{i+1}"},
                    "system_prompt": f"당신은 {request.name}라는 캐릭터입니다."
                }]
        
        return ToneGenerationResponse(
            question=question,
            responses=responses
        )
        
    except Exception as e:
        logger.error(f"어투 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=f"어투 생성 중 오류가 발생했습니다: {str(e)}")

@router.post("/generate_tone")
async def generate_tone_variations(request: ToneGenerationRequest):
    """
    캐릭터 기반 어투 변형 생성 (새로운 전용 엔드포인트)
    지정된 개수만큼 다양한 어투를 생성합니다.
    """
    try:
        task_id = str(uuid.uuid4())
        
        # 태스크 정보 저장
        tone_generation_tasks[task_id] = {
            "status": "pending",
            "character": request.character.dict(),
            "num_tones": request.num_tones,
            "created_at": datetime.now().isoformat(),
            "result": None,
            "error": None
        }
        
        logger.info(f"어투 생성 작업 시작: {task_id}")
        
        # 실제 어투 생성 로직 (동기적으로 처리)
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise HTTPException(status_code=500, detail="OpenAI API 키가 설정되지 않았습니다.")
        
        character_profile = CharacterProfile(
            name=request.character.name,
            description=request.character.description,
            age_range=request.character.age_range,
            gender=Gender[request.character.gender.upper()] if request.character.gender else Gender.NON_BINARY,
            personality=request.character.personality,
            mbti=request.character.mbti
        )
        
        speech_generator = SpeechGenerator(api_key=api_key)
        question = speech_generator.generate_question_for_character(character_profile)
        
        # 지정된 개수만큼 어투 생성
        responses = {}
        for i in range(request.num_tones):
            tone_name = f"tone_{i+1}"
            system_prompt = speech_generator.generate_system_prompt_with_gpt(
                character_profile, 
                tone_instruction_seed=f"variation_{i+1}"
            )
            
            responses[tone_name] = [{
                "text": f"{request.character.name}의 {i+1}번째 어투입니다.",
                "tone_info": {
                    "description": f"어투 변형 {i+1}",
                    "hashtags": f"#어투{i+1} #변형"
                },
                "system_prompt": system_prompt
            }]
        
        result = {
            "question": question,
            "responses": responses
        }
        
        # 결과 저장
        tone_generation_tasks[task_id]["status"] = "completed"
        tone_generation_tasks[task_id]["result"] = result
        tone_generation_tasks[task_id]["completed_at"] = datetime.now().isoformat()
        
        return {
            "task_id": task_id,
            "status": "completed",
            "result": result
        }
        
    except Exception as e:
        logger.error(f"어투 생성 실패: {e}")
        if task_id in tone_generation_tasks:
            tone_generation_tasks[task_id]["status"] = "failed"
            tone_generation_tasks[task_id]["error"] = str(e)
        raise HTTPException(status_code=500, detail=f"어투 생성 실패: {str(e)}")

@router.get("/tone_status/{task_id}")
async def get_tone_generation_status(task_id: str):
    """어투 생성 작업 상태 조회"""
    task = tone_generation_tasks.get(task_id)
    if not task:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
    return task

# Import datetime for timestamp operations
from datetime import datetime
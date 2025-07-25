from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Union
import uuid
import asyncio
import os
import json
import tempfile
import logging
from datetime import datetime

from pipeline.speech_generator import SpeechGenerator, CharacterProfile, Gender
from app.utils.langchain_tone_generator import get_langchain_tone_generator

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory storage for tasks (for simplicity, replace with a proper DB in production)
tone_generation_tasks: Dict[str, Dict[str, Any]] = {}

# ===== Helper Functions =====

def get_api_key() -> str:
    """OpenAI API 키를 가져오고 검증합니다."""
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise HTTPException(status_code=500, detail="OpenAI API 키가 설정되지 않았습니다.")
    return api_key

def extract_character_data(request: Dict[str, Any]) -> Dict[str, Any]:
    """요청에서 캐릭터 데이터를 추출합니다."""
    if 'character' in request:
        return request['character']
    return request

def create_character_profile(character_data: Dict[str, Any]) -> CharacterProfile:
    """캐릭터 데이터로부터 CharacterProfile 객체를 생성합니다."""
    return CharacterProfile(
        name=character_data.get('name', '캐릭터'),
        description=character_data.get('description', ''),
        age_range=character_data.get('age_range', '알 수 없음'),
        gender=Gender[character_data.get('gender', 'NON_BINARY').upper()] if character_data.get('gender') else Gender.NON_BINARY,
        personality=character_data.get('personality', '친근하고 활발한 성격'),
        mbti=character_data.get('mbti')
    )

def create_error_response(tone_num: int) -> List[Dict[str, Any]]:
    """에러 발생 시 기본 응답을 생성합니다."""
    return [{
        "text": f"죄송합니다. 말투{tone_num} 응답 생성에 실패했습니다.",
        "hashtags": f"#오류 #말투{tone_num}",
        "description": f"생성 실패한 말투{tone_num}"
    }]

async def measure_execution_time(coroutine):
    """코루틴의 실행 시간을 측정합니다."""
    start_time = asyncio.get_event_loop().time()
    result = await coroutine
    end_time = asyncio.get_event_loop().time()
    return result, end_time - start_time

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

class FastToneGenerationResponse(BaseModel):
    """고속 어투 생성 응답"""
    question: str
    responses: Dict[str, List[Dict[str, Any]]]  # 톤별 응답들
    generation_time_seconds: float
    method: str = "parallel_processing"

@router.post("/generate_qa_fast", response_model=FastToneGenerationResponse)
async def generate_character_qa_fast(request: Dict[str, Any]):
    """
    🚀 고속 어투 생성 (병렬 처리)
    pipeline의 speech_generator와 동일한 로직으로 3가지 다른 어투 생성
    LangChain 병렬 처리로 기존 순차 처리 대비 3-5배 빠른 속도
    """
    try:
        # 캐릭터 데이터 추출 및 프로필 생성
        character_data = extract_character_data(request)
        character_profile = create_character_profile(character_data)
        
        logger.info(f"🚀 고속 어투 생성 시작: {character_profile.name}")
        
        # API 키 확인 및 생성기 초기화
        api_key = get_api_key()
        speech_generator = SpeechGenerator(api_key=api_key)
        tone_generator = get_langchain_tone_generator(api_key=api_key)
        
        # 질문 생성
        question = await speech_generator.generate_question_for_character(character_profile)
        logger.info(f"📝 생성된 질문: {question}")
        
        # 시간 측정 시작
        start_time = asyncio.get_event_loop().time()
        
        # 한 번의 요청으로 3개의 서로 다른 system prompt 생성
        try:
            system_prompts = await speech_generator.create_three_distinct_system_prompts(character_profile)
            logger.info("✅ 단일 요청으로 3개 시스템 프롬프트 생성 성공")
            logger.info(system_prompts)
        
            
                
        except Exception as e:
            logger.warning(f"단일 요청 시스템 프롬프트 생성 실패, 병렬 방식으로 폴백: {e}")
            # 폴백: 기존 병렬 방식
            tone_tasks = [
                speech_generator.create_character_prompt_for_random_tone(character_profile, i + 1)
                for i in range(3)
            ]
            system_prompts = await asyncio.gather(*tone_tasks)
            
            # 폴백으로 생성된 시스템 프롬프트도 로깅
            logger.info("📌 병렬 방식으로 생성된 시스템 프롬프트:")
        for i, prompt in enumerate(system_prompts, 1):
            logger.info(f"\n🎭 시스템 프롬프트 {i} (길이: {len(prompt)}자):\n{prompt[:300]}..." if len(prompt) > 300 else f"\n🎭 시스템 프롬프트 {i} (길이: {len(prompt)}자):\n{prompt}")
        
        # 단일 요청으로 3가지 어투 생성 (더 차별화된 결과)
        try:
            responses = await tone_generator.generate_3_tones_single_request(
                character_data=character_data,
                question=question,
                system_prompts=system_prompts
            )
        except Exception as e:
            logger.warning(f"단일 요청 방식 실패, 병렬 방식으로 폴백: {e}")
            # 폴백: 기존 병렬 처리 방식
            response_tasks = [
                tone_generator._generate_single_tone_with_summary(
                    character_data=character_data,
                    question=question,
                    system_prompt=system_prompt,
                    tone_num=i+1
                )
                for i, system_prompt in enumerate(system_prompts)
            ]
            tone_results = await asyncio.gather(*response_tasks, return_exceptions=True)
            
            # 결과 정리
            responses = {}
            print('tone_results',tone_results)
            for i, result in enumerate(tone_results):
                tone_name = f"말투{i+1}"
                if isinstance(result, Exception):
                    logger.error(f"말투 {i+1} 생성 실패: {result}")
                    responses[tone_name] = create_error_response(i+1)
                else:
                    # system_prompt 추가
                    result['system_prompt'] = system_prompts[i]
                    responses[tone_name] = [result]
        
        # 생성 시간 계산
        generation_time = asyncio.get_event_loop().time() - start_time
        logger.info(f"✅ 고속 어투 생성 완료: {generation_time:.2f}초")
        
        return FastToneGenerationResponse(
            question=question,
            responses=responses,
            generation_time_seconds=generation_time
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 고속 어투 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=f"고속 어투 생성 중 오류가 발생했습니다: {str(e)}")

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
            "character": request.character.model_dump(),
            "num_tones": request.num_tones,
            "created_at": datetime.now().isoformat(),
            "result": None,
            "error": None
        }
        
        logger.info(f"어투 생성 작업 시작: {task_id}")
        
        # API 키 확인 및 캐릭터 프로필 생성
        api_key = get_api_key()
        character_profile = create_character_profile(request.character.model_dump())
        
        speech_generator = SpeechGenerator(api_key=api_key)
        question = await speech_generator.generate_question_for_character(character_profile)
        
        # 지정된 개수만큼 어투 생성
        tones_result = await speech_generator.generate_character_tones_for_question(character_profile, question, request.num_tones)
        
        if not tones_result or len(tones_result) == 0:
            raise Exception("어투 생성에 실패했습니다.")
        
        # 결과 변환
        responses = {}
        for i, (tone_key, tone_list) in enumerate(tones_result.items()):
            tone_name = f"tone_{i+1}"
            if tone_list and len(tone_list) > 0:
                tone_data = tone_list[0]
                responses[tone_name] = [{
                    "text": tone_data["text"],
                    "tone_info": {
                        "description": tone_data.get("description", f"어투 변형 {i+1}"),
                        "hashtags": tone_data.get("hashtags", f"#어투{i+1} #변형")
                    },
                    "system_prompt": await speech_generator.generate_system_prompt_with_gpt(character_profile, f"variation_{i+1}")
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

from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel
from typing import List, Dict, Any, Optional, Union
import uuid
import asyncio
import os
import json
import tempfile
import logging

from pipeline.speech_generator import SpeechGenerator, CharacterProfile, Gender
from app.utils.langchain_tone_generator import get_langchain_tone_generator

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

class FastToneGenerationResponse(BaseModel):
    """고속 어투 생성 응답"""
    question: str
    responses: Dict[str, List[Dict[str, Any]]]  # 톤별 응답들
    generation_time_seconds: float
    method: str = "parallel_processing"

@router.post("/generate_qa", response_model=ToneGenerationResponse)
async def generate_character_qa(request: Dict[str, Any]):
    """
    캐릭터 기반 어투 생성 (기존 엔드포인트와 호환성 유지)
    3가지 다른 어투로 질문에 대한 답변을 생성합니다.
    """
    try:
        # OpenAI API 키 확인
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise HTTPException(status_code=500, detail="OpenAI API 키가 설정되지 않았습니다.")
        
        # 요청 형식 판단 및 character 데이터 추출
        if 'character' in request:
            # 새로운 형식: {"character": {...}}
            character_data = request['character']
        else:
            # 기존 형식: {...} (직접 character 데이터)
            character_data = request
            
        # CharacterProfile 객체 생성
        character_profile = CharacterProfile(
            name=character_data.get('name', '캐릭터'),
            description=character_data.get('description', ''),
            age_range=character_data.get('age_range', '알 수 없음'),
            gender=Gender[character_data.get('gender', 'NON_BINARY').upper()] if character_data.get('gender') else Gender.NON_BINARY,
            personality=character_data.get('personality', '친근한 성격'),
            mbti=character_data.get('mbti')
        )
        
        # SpeechGenerator 인스턴스 생성
        speech_generator = SpeechGenerator(api_key=api_key)
        
        # 캐릭터에 맞는 질문 생성
        question = await speech_generator.generate_question_for_character(character_profile)
        
        # 3가지 다른 어투로 답변 생성
        responses = {}
        for i in range(3):
            tone_name = f"tone_{i+1}"
            
            # 시스템 프롬프트 생성
            system_prompt = await speech_generator.generate_system_prompt_with_gpt(
                character_profile, 
                tone_instruction_seed=f"variation_{i+1}"
            )
            
            # SpeechGenerator를 통한 어투 생성
            try:
                tones_result = await speech_generator.generate_character_tones_for_question(character_profile, question, 1)
                
                if tones_result and len(tones_result) > 0:
                    first_tone_key = list(tones_result.keys())[0]
                    tone_data = tones_result[first_tone_key][0]
                    
                    responses[tone_name] = [{
                        "text": tone_data["text"],
                        "tone_info": {
                            "description": tone_data.get("description", f"어투 {i+1}"),
                            "hashtags": tone_data.get("hashtags", f"#어투{i+1} #캐릭터")
                        },
                        "system_prompt": system_prompt
                    }]
                else:
                    raise Exception("SpeechGenerator에서 어투 생성 실패")
                
            except Exception as e:
                logger.error(f"어투 {i+1} 생성 실패: {e}")
                # 기본 어투 생성 금지 - 예외 발생
                raise HTTPException(status_code=500, detail=f"어투 {i+1} 생성에 실패했습니다: {str(e)}")
        
        return ToneGenerationResponse(
            question=question,
            responses=responses
        )
        
    except Exception as e:
        logger.error(f"어투 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=f"어투 생성 중 오류가 발생했습니다: {str(e)}")

@router.post("/generate_qa_fast", response_model=FastToneGenerationResponse)
async def generate_character_qa_fast(request: Dict[str, Any]):
    try:
        
        if 'character' in request:
            character_data = request['character']
        else:
            character_data = request
        
        logger.info(f"🚀 고속 어투 생성 시작: {character_data.get('name', 'Unknown')}")
        
        # OpenAI API 키 확인
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            raise HTTPException(status_code=500, detail="OpenAI API 키가 설정되지 않았습니다.")
        
        # CharacterProfile 객체 생성 (speech_generator와 동일)
        character_profile = CharacterProfile(
            name=character_data.get('name', '캐릭터'),
            description=character_data.get('description', ''),
            age_range=character_data.get('age_range', '알 수 없음'),
            gender=Gender[character_data.get('gender', 'NON_BINARY').upper()] if character_data.get('gender') else Gender.NON_BINARY,
            personality=character_data.get('personality', '친근한 성격'),
            mbti=character_data.get('mbti')
        )
        
        speech_generator = SpeechGenerator(api_key=api_key)
        question = await speech_generator.generate_question_for_character(character_profile)
        logger.info(f"📝 생성된 질문: {question}")
        
        start_time = asyncio.get_event_loop().time()
        
        tone_tasks = []
        for i in range(3):
            tone_variation = i + 1
            # 각 어투별로 독립적인 system promp t 생성 (speech_generator와 동일)
            system_prompt_task = speech_generator.create_character_prompt_for_random_tone(
                character_profile, 
                tone_variation
            )
            tone_tasks.append(system_prompt_task)
        
        # 3개의 system prompt를 병렬로 생성
        system_prompts = await asyncio.gather(*tone_tasks)
        print(system_prompts)
        # 고속 어투 생성기로 병렬 처리
        tone_generator = get_langchain_tone_generator(api_key=api_key)
        
        # 병렬 응답 생성을 위한 준비
        response_tasks = []
        for i, system_prompt in enumerate(system_prompts):
            # LangChain으로 병렬 응답 생성
            tone_name = f"말투{i+1}"
            response_tasks.append(
                tone_generator._generate_single_tone_with_summary(
                    character_data=character_data,
                    question=question,
                    system_prompt=system_prompt,
                    tone_num=i+1
                )
            )
        
        # 모든 응답을 병렬로 생성
        tone_results = await asyncio.gather(*response_tasks, return_exceptions=True)
        
        # 결과 정리 (speech_generator의 출력 형식과 동일하게)
        responses = {}
        for i, result in enumerate(tone_results):
            tone_name = f"말투{i+1}"
            
            if isinstance(result, Exception):
                logger.error(f"말투 {i+1} 생성 실패: {result}")
                # 실패 시 기본 응답
                responses[tone_name] = [{
                    "text": f"죄송합니다. 말투{i+1} 응답 생성에 실패했습니다.",
                    "hashtags": f"#오류 #말투{i+1}",
                    "description": f"생성 실패한 말투{i+1}"
                }]
            else:
                # 성공 시 speech_generator와 동일한 형식으로 응답
                responses[tone_name] = [result]
        
        # 생성 시간 계산
        end_time = asyncio.get_event_loop().time()
        generation_time = end_time - start_time
        
        logger.info(f"✅ 고속 어투 생성 완료: {generation_time:.2f}초")
        
        return FastToneGenerationResponse(
            question=question,
            responses=responses,
            generation_time_seconds=generation_time
        )
        
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

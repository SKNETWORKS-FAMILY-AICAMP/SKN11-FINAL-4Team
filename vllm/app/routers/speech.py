from fastapi import APIRouter, HTTPException, Depends
import logging
import asyncio
import uuid
from datetime import datetime
from typing import Dict, Any

from app.models import (
    VLLMCharacterProfile, VLLMQAGenerationResponse, VLLMBatchQARequest, VLLMBatchQAResponse,
    VLLMQuestionRequest, VLLMQuestionResponse, VLLMBatchQuestionRequest, VLLMBatchQuestionResponse,
    VLLMToneRequest, VLLMToneResponse, VLLMBatchToneRequest, VLLMBatchToneResponse
)
from app.core import get_speech_generator
from pipeline.speech_generator import SpeechGenerator, CharacterProfile, Gender

logger = logging.getLogger(__name__)

router = APIRouter()

# QA 생성 작업 상태를 저장할 전역 변수
qa_generation_tasks: Dict[str, Dict[str, Any]] = {}

@router.get("/health")
async def health_check(speech_generator: SpeechGenerator = Depends(get_speech_generator)):
    """
    Speech Generator의 상태를 확인합니다.
    이 엔드포인트를 호출하면 SpeechGenerator가 초기화되었는지 확인할 수 있습니다.
    """
    logger.info("🩺 Speech Generator health check successful.")
    return {"status": "ok", "message": "Speech Generator is available."}


@router.post("/generate_qa", response_model=VLLMQAGenerationResponse)
async def generate_qa_for_character_vllm_endpoint(
    character_profile: VLLMCharacterProfile,
    speech_generator: SpeechGenerator = Depends(get_speech_generator)
):
    logger.info(f"🔍 /generate_qa endpoint called. speech_generator id: {id(speech_generator)}")
    """
    캐릭터 프로필에 대한 질문과 3가지 톤 변형 응답을 생성합니다.
    """
    try:
        # Pydantic 모델을 dataclass로 변환
        vllm_char_profile = CharacterProfile(
            name=character_profile.name,
            description=character_profile.description,
            age_range=character_profile.age_range,
            gender=Gender(character_profile.gender), # Enum 변환 추가
            personality=character_profile.personality,
            mbti=character_profile.mbti
        )

        question, responses_data = speech_generator.generate_character_random_tones_sync(vllm_char_profile)

        # 응답 구조 정리
        if question in responses_data:
            actual_responses = responses_data[question]
        else:
            if responses_data:
                actual_responses = list(responses_data.values())[0]
            else:
                actual_responses = {}

        return VLLMQAGenerationResponse(
            question=question,
            responses=actual_responses
        )

    except Exception as e:
        logger.error(f"❌ Speech Generator 오류: {e}")
        raise HTTPException(status_code=500, detail=f"Speech Generator 오류: {str(e)}")

@router.post("/generate_qa_batch", response_model=VLLMBatchQAResponse)
async def generate_qa_batch_for_characters(
    batch_request: VLLMBatchQARequest,
    speech_generator: SpeechGenerator = Depends(get_speech_generator)
):
    """
    여러 캠릭터 프로필에 대한 질문과 응답을 배치로 생성합니다.
    """
    results = []
    errors = []
    success_count = 0
    
    for character_profile in batch_request.characters:
        for _ in range(batch_request.num_qa_per_character):
            try:
                # Pydantic 모델을 dataclass로 변환
                vllm_char_profile = CharacterProfile(
                    name=character_profile.name,
                    description=character_profile.description,
                    age_range=character_profile.age_range,
                    gender=Gender(character_profile.gender), # Enum 변환 추가
                    personality=character_profile.personality,
                    mbti=character_profile.mbti
                )
                
                question, responses_data = speech_generator.generate_character_random_tones_sync(vllm_char_profile)
                
                # 응답 구조 정리
                if question in responses_data:
                    actual_responses = responses_data[question]
                else:
                    if responses_data:
                        actual_responses = list(responses_data.values())[0]
                    else:
                        actual_responses = {}
                
                qa_response = VLLMQAGenerationResponse(
                    question=question,
                    responses=actual_responses
                )
                results.append(qa_response)
                success_count += 1
                
            except Exception as e:
                error_msg = f"{character_profile.name} QA 생성 실패: {str(e)}"
                logger.error(f"❌ {error_msg}")
                errors.append(error_msg)
    
    return VLLMBatchQAResponse(
        results=results,
        total_processed=len(batch_request.characters) * batch_request.num_qa_per_character,
        success_count=success_count,
        error_count=len(errors),
        errors=errors
    )

@router.post("/generate_questions", response_model=VLLMQuestionResponse)
async def generate_questions_only(
    request: VLLMQuestionRequest,
    speech_generator: SpeechGenerator = Depends(get_speech_generator)
):
    """
    캐릭터 프로필에 대한 질문만 생성합니다.
    """
    try:
        # Pydantic 모델을 dataclass로 변환
        character_profile = CharacterProfile(
            name=request.character.name,
            description=request.character.description,
            age_range=request.character.age_range,
            gender=Gender(request.character.gender), # Enum 변환 추가
            personality=request.character.personality,
            mbti=request.character.mbti
        )
        
        questions = []
        for _ in range(request.num_questions):
            question = speech_generator.generate_question_for_character(character_profile)
            questions.append(question)
        
        return VLLMQuestionResponse(
            questions=questions,
            character_name=character_profile.name
        )
        
    except Exception as e:
        logger.error(f"❌ 질문 생성 오류: {e}")
        raise HTTPException(status_code=500, detail=f"질문 생성 오류: {str(e)}")

@router.post("/generate_questions_batch", response_model=VLLMBatchQuestionResponse)
async def generate_questions_batch(
    batch_request: VLLMBatchQuestionRequest,
    speech_generator: SpeechGenerator = Depends(get_speech_generator)
):
    """
    여러 캠릭터 프로필에 대한 질문만 배치로 생성합니다.
    """
    results = []
    errors = []
    success_count = 0
    
    for character_profile in batch_request.characters:
        try:
            # Pydantic 모델을 dataclass로 변환
            char_profile = CharacterProfile(
                name=character_profile.name,
                description=character_profile.description,
                age_range=character_profile.age_range,
                gender=character_profile.gender,
                personality=character_profile.personality,
                mbti=character_profile.mbti
            )
            
            questions = []
            for _ in range(batch_request.num_questions_per_character):
                question = speech_generator.generate_question_for_character(char_profile)
                questions.append(question)
            
            question_response = VLLMQuestionResponse(
                questions=questions,
                character_name=char_profile.name
            )
            results.append(question_response)
            success_count += 1
            
        except Exception as e:
            error_msg = f"{character_profile.name} 질문 생성 실패: {str(e)}"
            logger.error(f"❌ {error_msg}")
            errors.append(error_msg)
    
    return VLLMBatchQuestionResponse(
        results=results,
        total_processed=len(batch_request.characters),
        success_count=success_count,
        error_count=len(errors),
        errors=errors
    )

@router.post("/generate_tones", response_model=VLLMToneResponse)
async def generate_tones_only(
    request: VLLMToneRequest,
    speech_generator: SpeechGenerator = Depends(get_speech_generator)
):
    """
    주어진 질문들에 대한 말투 변형 응답만 생성합니다.
    """
    try:
        # Pydantic 모델을 dataclass로 변환
        character_profile = CharacterProfile(
            name=request.character.name,
            description=request.character.description,
            age_range=request.character.age_range,
            gender=Gender(request.character.gender), # Enum 변환 추가
            personality=request.character.personality,
            mbti=request.character.mbti
        )
        
        all_responses = {}
        
        for question in request.questions:
            # 말투 변형 생성
            responses_data = speech_generator.generate_character_tones_for_question(
                character_profile, 
                question, 
                num_variations=request.num_tone_variations
            )
            all_responses[question] = responses_data
        
        return VLLMToneResponse(
            responses=all_responses,
            character_name=character_profile.name
        )
        
    except Exception as e:
        logger.error(f"❌ 말투 생성 오류: {e}")
        raise HTTPException(status_code=500, detail=f"말투 생성 오류: {str(e)}")

@router.post("/generate_tones_batch", response_model=VLLMBatchToneResponse)
async def generate_tones_batch(
    batch_request: VLLMBatchToneRequest,
    speech_generator: SpeechGenerator = Depends(get_speech_generator)
):
    """
    여러 말투 요청을 배치로 처리합니다.
    """
    results = []
    errors = []
    success_count = 0
    
    for tone_request in batch_request.requests:
        try:
            # Pydantic 모델을 dataclass로 변환
            character_profile = CharacterProfile(
                name=tone_request.character.name,
                description=tone_request.character.description,
                age_range=tone_request.character.age_range,
                gender=tone_request.character.gender,
                personality=tone_request.character.personality,
                mbti=tone_request.character.mbti
            )
            
            all_responses = {}
            
            for question in tone_request.questions:
                # 말투 변형 생성
                responses_data = speech_generator.generate_character_tones_for_question(
                    character_profile, 
                    question, 
                    num_variations=tone_request.num_tone_variations
                )
                all_responses[question] = responses_data
            
            tone_response = VLLMToneResponse(
                responses=all_responses,
                character_name=character_profile.name
            )
            results.append(tone_response)
            success_count += 1
            
        except Exception as e:
            error_msg = f"{tone_request.character.name} 말투 생성 실패: {str(e)}"
            logger.error(f"❌ {error_msg}")
            errors.append(error_msg)
    
    return VLLMBatchToneResponse(
        results=results,
        total_processed=len(batch_request.requests),
        success_count=success_count,
        error_count=len(errors),
        errors=errors
    )

@router.post("/start_qa_generation", response_model=Dict[str, str])
async def start_qa_generation(
    request: VLLMBatchQARequest,
    speech_generator: SpeechGenerator = Depends(get_speech_generator)
):
    """
    QA 생성 작업을 비동기로 시작합니다.
    작업 ID를 즉시 반환하고 백그라운드에서 QA를 생성합니다.
    """
    try:
        # 작업 ID 생성
        task_id = str(uuid.uuid4())
        
        # 작업 정보 초기화
        qa_generation_tasks[task_id] = {
            "status": "pending",
            "total_requests": len(request.characters) * request.num_qa_per_character,
            "completed": 0,
            "results": [],
            "errors": [],
            "started_at": datetime.now(),
            "completed_at": None,
            "character_data": request.characters,
            "num_qa_per_character": request.num_qa_per_character
        }
        
        # 백그라운드에서 QA 생성 작업 시작
        asyncio.create_task(generate_qa_background(task_id, request, speech_generator))
        
        logger.info(f"QA 생성 작업 시작: task_id={task_id}, total_requests={qa_generation_tasks[task_id]['total_requests']}")
        
        return {
            "task_id": task_id,
            "status": "started",
            "message": "QA 생성 작업이 시작되었습니다."
        }
        
    except Exception as e:
        logger.error(f"QA 생성 작업 시작 실패: {e}")
        raise HTTPException(status_code=500, detail=f"QA 생성 작업 시작 실패: {str(e)}")

@router.get("/qa_generation_status/{task_id}", response_model=Dict[str, Any])
async def get_qa_generation_status(task_id: str):
    """
    QA 생성 작업의 상태를 조회합니다.
    """
    if task_id not in qa_generation_tasks:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
    
    task_info = qa_generation_tasks[task_id]
    
    # 진행률 계산
    progress = 0
    if task_info["total_requests"] > 0:
        progress = (task_info["completed"] / task_info["total_requests"]) * 100
    
    return {
        "task_id": task_id,
        "status": task_info["status"],
        "progress": round(progress, 2),
        "total_requests": task_info["total_requests"],
        "completed": task_info["completed"],
        "errors": len(task_info["errors"]),
        "started_at": task_info["started_at"].isoformat(),
        "completed_at": task_info["completed_at"].isoformat() if task_info["completed_at"] else None,
        "estimated_time_remaining": calculate_estimated_time(task_info)
    }

@router.get("/qa_generation_results/{task_id}", response_model=Dict[str, Any])
async def get_qa_generation_results(task_id: str):
    """
    완료된 QA 생성 작업의 결과를 조회합니다.
    """
    if task_id not in qa_generation_tasks:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
    
    task_info = qa_generation_tasks[task_id]
    
    if task_info["status"] != "completed":
        raise HTTPException(status_code=400, detail="작업이 아직 완료되지 않았습니다.")
    
    return {
        "task_id": task_id,
        "status": task_info["status"],
        "results": task_info["results"],
        "errors": task_info["errors"],
        "total_processed": task_info["total_requests"],
        "success_count": len(task_info["results"]),
        "error_count": len(task_info["errors"]),
        "started_at": task_info["started_at"].isoformat(),
        "completed_at": task_info["completed_at"].isoformat()
    }

async def generate_qa_background(task_id: str, request: VLLMBatchQARequest, speech_generator: SpeechGenerator):
    """
    백그라운드에서 QA를 생성하는 함수
    """
    try:
        task_info = qa_generation_tasks[task_id]
        task_info["status"] = "processing"
        
        logger.info(f"백그라운드 QA 생성 시작: task_id={task_id}")
        
        for character_profile in request.characters:
            for _ in range(request.num_qa_per_character):
                try:
                    # Pydantic 모델을 dataclass로 변환
                    vllm_char_profile = CharacterProfile(
                        name=character_profile.name,
                        description=character_profile.description,
                        age_range=character_profile.age_range,
                        gender=Gender(character_profile.gender),
                        personality=character_profile.personality,
                        mbti=character_profile.mbti
                    )
                    
                    # QA 생성
                    question, responses_data = speech_generator.generate_character_random_tones_sync(vllm_char_profile)
                    
                    # 응답 구조 정리
                    if question in responses_data:
                        actual_responses = responses_data[question]
                    else:
                        if responses_data:
                            actual_responses = list(responses_data.values())[0]
                        else:
                            actual_responses = {}
                    
                    qa_response = VLLMQAGenerationResponse(
                        question=question,
                        responses=actual_responses
                    )
                    
                    task_info["results"].append(qa_response)
                    task_info["completed"] += 1
                    
                    # 진행 상황 로깅 (10개마다)
                    if task_info["completed"] % 10 == 0:
                        logger.info(f"QA 생성 진행: task_id={task_id}, completed={task_info['completed']}/{task_info['total_requests']}")
                    
                    # 짧은 대기 (서버 부하 방지)
                    await asyncio.sleep(0.1)
                    
                except Exception as e:
                    error_msg = f"{character_profile.name} QA 생성 실패: {str(e)}"
                    logger.error(f"❌ {error_msg}")
                    task_info["errors"].append(error_msg)
                    task_info["completed"] += 1
        
        # 작업 완료
        task_info["status"] = "completed"
        task_info["completed_at"] = datetime.now()
        
        logger.info(f"QA 생성 작업 완료: task_id={task_id}, total={task_info['total_requests']}, success={len(task_info['results'])}, errors={len(task_info['errors'])}")
        
    except Exception as e:
        logger.error(f"QA 생성 작업 실패: task_id={task_id}, error={e}")
        task_info["status"] = "failed"
        task_info["errors"].append(f"작업 실패: {str(e)}")
        task_info["completed_at"] = datetime.now()

def calculate_estimated_time(task_info: Dict[str, Any]) -> str:
    """
    예상 완료 시간을 계산합니다.
    """
    if task_info["completed"] == 0:
        return "계산 중..."
    
    elapsed_time = (datetime.now() - task_info["started_at"]).total_seconds()
    rate = task_info["completed"] / elapsed_time
    remaining = task_info["total_requests"] - task_info["completed"]
    
    if rate > 0:
        estimated_seconds = remaining / rate
        if estimated_seconds < 60:
            return f"{int(estimated_seconds)}초"
        elif estimated_seconds < 3600:
            return f"{int(estimated_seconds / 60)}분"
        else:
            return f"{int(estimated_seconds / 3600)}시간 {int((estimated_seconds % 3600) / 60)}분"
    
    return "계산 중..."

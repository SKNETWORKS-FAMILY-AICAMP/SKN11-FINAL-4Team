from fastapi import APIRouter, HTTPException, Depends
import logging

from app.models import (
    VLLMCharacterProfile, VLLMQAGenerationResponse, VLLMBatchQARequest, VLLMBatchQAResponse,
    VLLMQuestionRequest, VLLMQuestionResponse, VLLMBatchQuestionRequest, VLLMBatchQuestionResponse,
    VLLMToneRequest, VLLMToneResponse, VLLMBatchToneRequest, VLLMBatchToneResponse
)
from app.core import get_speech_generator
from pipeline.speech_generator import SpeechGenerator, CharacterProfile

logger = logging.getLogger(__name__)

router = APIRouter()

@router.get("/health")sync def health_check(speech_generator: SpeechGenerator = Depends(get_speech_generator)):
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
            gender=character_profile.gender,
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
                    gender=character_profile.gender,
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
            gender=request.character.gender,
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
            gender=request.character.gender,
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

from fastapi import APIRouter, HTTPException
import logging

from app.models import VLLMCharacterProfile, VLLMQAGenerationResponse
from app.core import speech_generator
from pipeline.speech_generator import CharacterProfile # CharacterProfile은 pipeline.speech_generator에서 가져옴

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/generate_qa", response_model=VLLMQAGenerationResponse)
async def generate_qa_for_character_vllm_endpoint(
    character_profile: VLLMCharacterProfile
):
    """
    캐릭터 프로필에 대한 질문과 3가지 톤 변형 응답을 생성합니다.
    """
    if not speech_generator:
        raise HTTPException(
            status_code=503, 
            detail="Speech Generator가 활성화되지 않았습니다. OPENAI_API_KEY를 설정해주세요."
        )
    
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

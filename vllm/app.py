import os
from fastapi import FastAPI, APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional

from vllm.pipeline.speech_generator import SpeechGenerator, CharacterProfile, Gender

# Load environment variables for VLLM server's OpenAI API key
# This API key is used by SpeechGenerator for certain GPT calls (e.g., tone summarization)
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not OPENAI_API_KEY:
    raise ValueError("OPENAI_API_KEY environment variable not set for VLLM server.")

# Initialize SpeechGenerator (it will use the OpenAI API key for its internal GPT calls)
speech_generator = SpeechGenerator(api_key=OPENAI_API_KEY)

app = FastAPI(
    title="VLLM Speech Generation API",
    description="API for generating speech tones and QA pairs using VLLM and OpenAI models.",
    version="1.0.0",
)

router = APIRouter()

class VLLMCharacterProfile(BaseModel):
    name: str
    description: str
    age_range: Optional[str] = None
    gender: Gender
    personality: str
    mbti: Optional[str] = None

    class Config:
        use_enum_values = True

class VLLMQAGenerationResponse(BaseModel):
    question: str
    responses: Dict[str, List[Dict[str, Any]]]

@router.post("/generate_qa", response_model=VLLMQAGenerationResponse)
async def generate_qa_for_character_vllm(
    character_profile: VLLMCharacterProfile
):
    """
    Generates a question and three tone-varied responses for a given character profile.
    This endpoint is intended to be called by the main backend service.
    """
    try:
        # Convert Pydantic model to dataclass for SpeechGenerator
        vllm_char_profile = CharacterProfile(
            name=character_profile.name,
            description=character_profile.description,
            age_range=character_profile.age_range,
            gender=character_profile.gender,
            personality=character_profile.personality,
            mbti=character_profile.mbti
        )

        question, responses_data = speech_generator.generate_character_random_tones_sync(vllm_char_profile)

        # The responses_data is already in a suitable format for the VLLM server's direct output
        # It's Dict[str, Dict[str, List[Dict[str, Any]]]] where the first key is the question
        # We need to extract the actual responses part.
        # The generate_character_random_tones_sync returns (selected_message, results)
        # results is {selected_message: {tone_name: [GeneratedToneResponse]}}
        # So we need to get results[question]

        # Ensure the structure matches VLLMQAGenerationResponse
        # The `responses_data` from `generate_character_random_tones_sync` is `Dict[str, Dict[str, List[Dict[str, Any]]]]`
        # where the outer key is the question. We need to extract the inner dict.
        if question in responses_data:
            actual_responses = responses_data[question]
        else:
            # This case should ideally not happen if generate_character_random_tones_sync works as expected
            # but as a fallback, we can try to find the first (and likely only) entry
            if responses_data:
                actual_responses = list(responses_data.values())[0]
            else:
                actual_responses = {}

        return VLLMQAGenerationResponse(
            question=question,
            responses=actual_responses
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"VLLM server internal error: {str(e)}")

app.include_router(router)

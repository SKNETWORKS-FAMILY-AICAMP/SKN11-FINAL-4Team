"""
인플루언서 QA 생성 관련 스키마
"""

from pydantic import BaseModel
from typing import List, Dict, Any, Optional
from enum import Enum


class Gender(Enum):
    MALE = "남성"
    FEMALE = "여성"
    NON_BINARY = "없음"


class CharacterProfile(BaseModel):
    """캐릭터 프로필"""
    name: str
    description: Optional[str] = ""
    age_range: Optional[str] = "알 수 없음"
    gender: Optional[Gender] = Gender.NON_BINARY
    personality: Optional[str] = "친근하고 활발한 성격"
    mbti: Optional[str] = None


class ToneGenerationRequest(BaseModel):
    """어투 생성 요청"""
    character: CharacterProfile
    num_tones: int = 3  # 생성할 어투 개수 (기본 3개)


class ToneGenerationResponse(BaseModel):
    """어투 생성 응답"""
    question: str
    responses: Dict[str, List[Dict[str, Any]]]  # 톤별 응답들
    generation_time_seconds: float
    method: str = "integrated_backend"
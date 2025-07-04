"""
간단한 Mock OpenAI 서비스 (패키지 오류 해결용)
"""

import os
import json
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod
from pydantic import BaseModel
import logging
from app.core.config import settings

logger = logging.getLogger(__name__)

# OpenAI 클라이언트 초기화 (API 키가 있을 때만)
openai_client = None
if settings.OPENAI_API_KEY:
    try:
        import openai
        openai_client = openai.OpenAI(api_key=settings.OPENAI_API_KEY)
        logger.info("OpenAI client initialized with API key")
    except ImportError:
        logger.warning("OpenAI package not installed. Install with: pip install openai")
    except Exception as e:
        logger.error(f"Failed to initialize OpenAI client: {e}")
else:
    logger.info("No OpenAI API key found. Using mock mode.")


# 요청/응답 모델 정의
class ContentGenerationRequest(BaseModel):
    """콘텐츠 생성 요청 모델"""
    topic: str
    platform: str
    include_content: Optional[str] = None
    hashtags: Optional[str] = None
    influencer_personality: Optional[str] = None
    influencer_tone: Optional[str] = None


class ContentGenerationResponse(BaseModel):
    """콘텐츠 생성 응답 모델"""
    social_media_content: str
    english_prompt_for_comfyui: str
    hashtags: List[str]
    metadata: Dict[str, Any]


class OpenAIService:
    """OpenAI 서비스 (실제 API 또는 Mock)"""
    
    def __init__(self):
        self.use_mock = not bool(settings.OPENAI_API_KEY and openai_client)
        logger.info(f"OpenAI Service initialized (Mock mode: {self.use_mock})")
    
    async def generate_social_content(self, request: ContentGenerationRequest) -> ContentGenerationResponse:
        """실제 또는 Mock 콘텐츠 생성"""
        
        if not self.use_mock and openai_client:
            return await self._generate_real_content(request)
        else:
            return await self._generate_mock_content(request)
    
    async def _generate_real_content(self, request: ContentGenerationRequest) -> ContentGenerationResponse:
        """실제 OpenAI API를 사용한 콘텐츠 생성"""
        try:
            # 시스템 프롬프트
            system_prompt = f"""
            당신은 {request.platform} 플랫폼에 특화된 소셜 미디어 콘텐츠 전문가입니다.
            주어진 주제와 내용을 바탕으로 다음을 생성해주세요:
            1. 매력적이고 참여도 높은 소셜 미디어 포스트 (한국어)
            2. 이미지 생성을 위한 영어 프롬프트 (ComfyUI용)
            3. 관련 해시태그
            
            응답은 반드시 JSON 형식으로 해주세요:
            {{
                "social_media_content": "포스트 내용",
                "english_prompt_for_comfyui": "영어 이미지 프롬프트",
                "hashtags": ["해시태그1", "해시태그2"]
            }}
            """
            
            # 사용자 프롬프트
            user_prompt = f"""
            주제: {request.topic}
            플랫폼: {request.platform}
            추가 내용: {request.include_content or "없음"}
            기존 해시태그: {request.hashtags or "없음"}
            인플루언서 성격: {request.influencer_personality or "친근하고 전문적"}
            톤: {request.influencer_tone or "밝고 긍정적"}
            """
            
            response = openai_client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                max_tokens=settings.OPENAI_MAX_TOKENS,
                temperature=0.7
            )
            
            content = response.choices[0].message.content
            
            # JSON 파싱 시도
            try:
                parsed_content = json.loads(content)
                return ContentGenerationResponse(
                    social_media_content=parsed_content.get("social_media_content", ""),
                    english_prompt_for_comfyui=parsed_content.get("english_prompt_for_comfyui", ""),
                    hashtags=parsed_content.get("hashtags", []),
                    metadata={
                        "model": settings.OPENAI_MODEL,
                        "platform": request.platform,
                        "tokens_used": response.usage.total_tokens if response.usage else 0,
                        "real_openai": True
                    }
                )
            except json.JSONDecodeError:
                # JSON 파싱 실패 시 텍스트 그대로 사용
                return ContentGenerationResponse(
                    social_media_content=content,
                    english_prompt_for_comfyui=f"high quality, realistic, {request.topic}, professional photography",
                    hashtags=["#AI생성", "#소셜미디어"],
                    metadata={
                        "model": settings.OPENAI_MODEL,
                        "platform": request.platform,
                        "note": "JSON 파싱 실패, 원본 응답 사용",
                        "real_openai": True
                    }
                )
                
        except Exception as e:
            logger.error(f"OpenAI API 호출 실패: {e}")
            # 실패 시 Mock 콘텐츠 반환
            return await self._generate_mock_content(request)
    
    async def _generate_mock_content(self, request: ContentGenerationRequest) -> ContentGenerationResponse:
        """Mock 콘텐츠 생성"""
        
        # 간단한 Mock 콘텐츠 생성
        content = f"안녕하세요! 오늘은 {request.topic}에 대해 이야기해보려고 해요! ✨\n\n"
        
        if request.include_content:
            content += f"{request.include_content}\n\n"
        
        content += "정말 흥미로운 주제인 것 같아요! 여러분은 어떻게 생각하시나요? 💭\n\n"
        content += "댓글로 여러분의 생각을 들려주세요! 💕"
        
        # Mock ComfyUI 프롬프트
        comfyui_prompt = f"high quality, realistic, {request.topic}, professional photography, beautiful lighting, 8k resolution, detailed"
        
        # 해시태그 처리
        hashtags = ["#일상", "#소통", "#AI"]
        if request.hashtags:
            hashtags.extend([tag.strip() for tag in request.hashtags.split() if tag.startswith('#')])
        
        return ContentGenerationResponse(
            social_media_content=content,
            english_prompt_for_comfyui=comfyui_prompt,
            hashtags=hashtags,
            metadata={
                "model": "mock-gpt",
                "platform": request.platform,
                "note": "Mock 데이터 - 실제 OpenAI API 키 설정 시 실제 생성됩니다",
                "real_openai": False
            }
        )
    
    async def generate_comfyui_prompt(self, topic: str, style: str = "realistic") -> str:
        """Mock ComfyUI 프롬프트 생성"""
        return f"high quality, {style}, {topic}, professional photography, beautiful lighting, 8k resolution, detailed"


# 싱글톤 패턴
_openai_service_instance = None

def get_openai_service() -> OpenAIService:
    """OpenAI 서비스 인스턴스 반환"""
    global _openai_service_instance
    if _openai_service_instance is None:
        _openai_service_instance = OpenAIService()
    return _openai_service_instance

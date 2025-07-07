"""
OpenAI API 서비스

SOLID 원칙:
- SRP: OpenAI API 연동 및 콘텐츠 생성만 담당
- OCP: 새로운 AI 모델이나 프롬프트 타입 추가 시 확장 가능
- LSP: 추상 인터페이스를 구현하여 다른 AI 서비스로 교체 가능
- ISP: 클라이언트별 인터페이스 분리 (콘텐츠 생성, 프롬프트 생성)
- DIP: 구체적인 OpenAI 구현이 아닌 추상화에 의존

Clean Architecture:
- Domain Layer: AI 콘텐츠 생성 비즈니스 로직
- Infrastructure Layer: 외부 OpenAI API 연동
"""

import os
import json
from typing import Dict, List, Optional, Any
from abc import ABC, abstractmethod
from pydantic import BaseModel
from app.core.config import settings
import logging

# OpenAI 패키지 안전한 import
try:
    import openai

    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False
    openai = None

logger = logging.getLogger(__name__)


# 요청/응답 모델 정의 (Clean Architecture - Domain Layer)
class ContentGenerationRequest(BaseModel):
    """콘텐츠 생성 요청 모델"""

    topic: str
    platform: str  # instagram, facebook, twitter, etc.
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


# 추상 인터페이스 (SOLID - DIP 원칙)
class AIContentGeneratorInterface(ABC):
    """AI 콘텐츠 생성 추상 인터페이스"""

    @abstractmethod
    async def generate_social_content(
        self, request: ContentGenerationRequest
    ) -> ContentGenerationResponse:
        """소셜 미디어 콘텐츠 생성"""
        pass

    @abstractmethod
    async def generate_comfyui_prompt(
        self, topic: str, style: str = "realistic"
    ) -> str:
        """ComfyUI용 영문 프롬프트 생성"""
        pass


class OpenAIService(AIContentGeneratorInterface):
    """
    OpenAI GPT API 서비스 구현

    SOLID 원칙 준수:
    - SRP: OpenAI API 호출과 응답 처리만 담당
    - OCP: 새로운 프롬프트 템플릿 추가 시 확장 가능
    """

    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY", "")
        self.use_mock = not self.api_key or self.api_key == ""

        if not self.use_mock:
            openai.api_key = self.api_key

        logger.info(f"OpenAI Service initialized (Mock mode: {self.use_mock})")

    async def generate_social_content(
        self, request: ContentGenerationRequest
    ) -> ContentGenerationResponse:
        """
        소셜 미디어 콘텐츠 생성

        Clean Architecture: 비즈니스 로직과 외부 서비스 분리
        """
        try:
            if self.use_mock:
                return await self._generate_mock_content(request)
            else:
                return await self._generate_real_content(request)
        except Exception as e:
            logger.error(f"Content generation failed: {e}")
            # 실패 시 Mock 데이터로 폴백
            return await self._generate_mock_content(request)

    async def generate_comfyui_prompt(
        self, topic: str, style: str = "realistic"
    ) -> str:
        """ComfyUI용 영문 프롬프트 생성"""
        if self.use_mock:
            return self._generate_mock_comfyui_prompt(topic, style)
        else:
            return await self._generate_real_comfyui_prompt(topic, style)

    async def _generate_real_content(
        self, request: ContentGenerationRequest
    ) -> ContentGenerationResponse:
        """실제 OpenAI API 호출"""

        # 플랫폼별 프롬프트 템플릿
        platform_prompts = {
            "instagram": self._get_instagram_prompt_template(),
            "facebook": self._get_facebook_prompt_template(),
            "twitter": self._get_twitter_prompt_template(),
        }

        prompt_template = platform_prompts.get(
            request.platform.lower(), platform_prompts["instagram"]
        )

        # 프롬프트 생성
        prompt = prompt_template.format(
            topic=request.topic,
            include_content=request.include_content or "",
            personality=request.influencer_personality or "친근하고 활발한",
            tone=request.influencer_tone or "캐주얼하고 친밀한",
            hashtags=request.hashtags or "",
        )

        try:
            # OpenAI API 호출
            response = await openai.ChatCompletion.acreate(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 전문적인 소셜 미디어 콘텐츠 크리에이터입니다.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=1000,
                temperature=0.7,
            )

            content = response.choices[0].message.content

            # ComfyUI 프롬프트 생성
            comfyui_prompt = await self.generate_comfyui_prompt(request.topic)

            # 해시태그 추출
            hashtags = self._extract_hashtags(content, request.hashtags)

            return ContentGenerationResponse(
                social_media_content=content,
                english_prompt_for_comfyui=comfyui_prompt,
                hashtags=hashtags,
                metadata={
                    "model": "gpt-3.5-turbo",
                    "platform": request.platform,
                    "generated_at": "2024-07-03T10:30:00Z",
                },
            )

        except Exception as e:
            logger.error(f"OpenAI API call failed: {e}")
            raise

    async def _generate_mock_content(
        self, request: ContentGenerationRequest
    ) -> ContentGenerationResponse:
        """Mock 데이터 생성 (API 키 없을 때 또는 테스트용)"""

        # 플랫폼별 Mock 콘텐츠 템플릿
        mock_templates = {
            "instagram": self._get_mock_instagram_content(request),
            "facebook": self._get_mock_facebook_content(request),
            "twitter": self._get_mock_twitter_content(request),
        }

        content = mock_templates.get(
            request.platform.lower(), mock_templates["instagram"]
        )

        # Mock ComfyUI 프롬프트
        comfyui_prompt = self._generate_mock_comfyui_prompt(request.topic)

        # 해시태그 처리
        hashtags = self._extract_hashtags(content, request.hashtags)

        return ContentGenerationResponse(
            social_media_content=content,
            english_prompt_for_comfyui=comfyui_prompt,
            hashtags=hashtags,
            metadata={
                "model": "mock-gpt",
                "platform": request.platform,
                "generated_at": "2024-07-03T10:30:00Z",
                "note": "Mock data - 실제 OpenAI API 키 설정 시 실제 생성됩니다",
            },
        )

    def _get_instagram_prompt_template(self) -> str:
        """Instagram용 프롬프트 템플릿"""
        return """
다음 조건에 맞는 Instagram 게시글을 작성해주세요:

주제: {topic}
포함할 내용: {include_content}
인플루언서 성격: {personality}
말투: {tone}
해시태그: {hashtags}

요구사항:
1. 친근하고 자연스러운 톤으로 작성
2. 이모지는 사용하지 마세요.
3. 입력된 설명(포함할 내용)의 모든 내용을 반드시 본문에 포함하세요. 내용을 누락하거나 생략하지 마세요.
4. 본문에는 해시태그를 포함하지 마세요. 해시태그는 별도로 생성하세요.
5. 적절한 해시태그 포함 (5-10개)

게시글:
"""

    def _get_facebook_prompt_template(self) -> str:
        """Facebook용 프롬프트 템플릿"""
        return """
다음 조건에 맞는 Facebook 게시글을 작성해주세요:

주제: {topic}
포함할 내용: {include_content}
인플루언서 성격: {personality}
말투: {tone}

요구사항:
1. 좀 더 자세하고 구체적인 내용 포함
2. 이모지는 사용하지 마세요.
3. 입력된 설명(포함할 내용)의 모든 내용을 반드시 본문에 포함하세요. 내용을 누락하거나 생략하지 마세요.
4. 본문에는 해시태그를 포함하지 마세요. 해시태그는 별도로 생성하세요.
5. 스토리텔링 요소 추가
6. 친구들과 공유하고 싶은 내용
7. 해시태그는 적게 사용 (3-5개)

게시글:
"""

    def _get_twitter_prompt_template(self) -> str:
        """Twitter용 프롬프트 템플릿"""
        return """
다음 조건에 맞는 Twitter 게시글을 작성해주세요:

주제: {topic}
포함할 내용: {include_content}
인플루언서 성격: {personality}
말투: {tone}

요구사항:
1. 280자 이내로 간결하게 작성
2. 이모지는 사용하지 마세요.
3. 입력된 설명(포함할 내용)의 모든 내용을 반드시 본문에 포함하세요. 내용을 누락하거나 생략하지 마세요.
4. 본문에는 해시태그를 포함하지 마세요. 해시태그는 별도로 생성하세요.
5. 임팩트 있는 첫 문장
6. 리트윗하고 싶은 내용
7. 해시태그 2-3개 사용

트윗:
"""

    def _get_mock_instagram_content(self, request: ContentGenerationRequest) -> str:
        """Mock Instagram 콘텐츠 생성"""

        base_content = f"안녕하세요 여러분! 🌟 오늘은 {request.topic}에 대해 이야기해보려고 해요!\n\n"

        if request.include_content:
            base_content += f"{request.include_content}\n\n"

        base_content += """정말 흥미로운 주제인 것 같아요! 여러분은 어떻게 생각하시나요? 💭
        
댓글로 여러분의 생각을 들려주세요! 같이 이야기 나눠봐요 💕

#일상 #소통 #팔로우 #좋아요 #데일리"""

        return base_content

    def _get_mock_facebook_content(self, request: ContentGenerationRequest) -> str:
        """Mock Facebook 콘텐츠 생성"""

        content = f"오늘 {request.topic}에 대해 깊이 생각해볼 기회가 있었어요.\n\n"

        if request.include_content:
            content += f"{request.include_content}\n\n"

        content += """이런 경험을 통해 많은 것을 배우게 되는 것 같아요. 때로는 작은 것들이 큰 변화를 가져다주기도 하고요.

여러분도 비슷한 경험이 있으시다면 댓글로 공유해주세요! 서로의 이야기를 나누며 함께 성장해나가요.

#일상공유 #소통 #성장"""

        return content

    def _get_mock_twitter_content(self, request: ContentGenerationRequest) -> str:
        """Mock Twitter 콘텐츠 생성"""

        content = f"{request.topic} 관련해서 오늘 새로운 것을 배웠어요! "

        if request.include_content:
            content += f"{request.include_content[:50]}... "

        content += "여러분은 어떻게 생각하시나요? #일상 #소통"

        return content

    def _generate_mock_comfyui_prompt(
        self, topic: str, style: str = "realistic"
    ) -> str:
        """Mock ComfyUI 프롬프트 생성"""

        # 주제별 기본 영문 프롬프트 생성
        topic_keywords = {
            "패션": "fashion, stylish outfit, trendy clothes, modern style",
            "음식": "delicious food, restaurant, cooking, gourmet meal",
            "여행": "travel destination, beautiful landscape, adventure, tourism",
            "운동": "fitness, workout, gym, healthy lifestyle, sports",
            "뷰티": "beauty, makeup, skincare, cosmetics, glamour",
            "라이프스타일": "lifestyle, daily life, cozy home, relaxation",
        }

        # 한국어 키워드를 영어로 매핑
        english_keywords = "lifestyle, daily life, modern, trendy"
        for kr_keyword, en_keyword in topic_keywords.items():
            if kr_keyword in topic:
                english_keywords = en_keyword
                break

        base_prompt = f"high quality, {style}, {english_keywords}, professional photography, 8k resolution, detailed, vibrant colors, natural lighting"

        return base_prompt

    async def _generate_real_comfyui_prompt(
        self, topic: str, style: str = "realistic"
    ) -> str:
        """실제 OpenAI API로 ComfyUI 프롬프트 생성"""

        prompt = f"""
다음 주제에 맞는 ComfyUI용 영문 프롬프트를 생성해주세요:

주제: {topic}
스타일: {style}

요구사항:
1. 영어로만 작성
2. 고품질 이미지 생성을 위한 키워드 포함
3. 쉼표로 구분된 키워드 형태
4. 카메라 설정, 조명, 품질 관련 키워드 포함
5. 50-100 단어 내외

프롬프트:
"""

        try:
            response = await openai.ChatCompletion.acreate(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert in creating prompts for AI image generation.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=200,
                temperature=0.5,
            )

            return response.choices[0].message.content.strip()

        except Exception as e:
            logger.error(f"ComfyUI prompt generation failed: {e}")
            return self._generate_mock_comfyui_prompt(topic, style)

    def _extract_hashtags(
        self, content: str, additional_hashtags: Optional[str] = None
    ) -> List[str]:
        """콘텐츠에서 해시태그 추출"""
        import re

        # 콘텐츠에서 해시태그 추출
        hashtags = re.findall(r"#\w+", content)

        # 추가 해시태그 처리
        if additional_hashtags:
            additional = [
                tag.strip()
                for tag in additional_hashtags.split()
                if tag.startswith("#")
            ]
            hashtags.extend(additional)

        # 중복 제거 및 정리
        hashtags = list(set(hashtags))

        return hashtags[:10]  # 최대 10개까지


# 싱글톤 패턴으로 서비스 인스턴스 관리
_openai_service_instance = None


def get_openai_service() -> OpenAIService:
    """OpenAI 서비스 싱글톤 인스턴스 반환"""
    global _openai_service_instance
    if _openai_service_instance is None:
        _openai_service_instance = OpenAIService()
    return _openai_service_instance

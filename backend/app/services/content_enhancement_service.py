import uuid
from openai import AsyncOpenAI
from typing import Dict, Any, Optional, List
from app.core.config import settings


class ContentEnhancementService:
    """게시글 설명 생성 + 인플루언서 말투 변환 통합 서비스"""

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.OPENAI_API_KEY)

    async def generate_content(
        self,
        topic: str,
        platform: str,
        influencer_personality: Optional[str] = None,
        influencer_tone: Optional[str] = None,
        include_content: Optional[str] = None,
        hashtags: Optional[str] = None,
    ) -> Dict[str, Any]:
        """OpenAI로 게시글 설명/해시태그 생성 (중립적 설명)"""
        prompt = f"""
주제: {topic}
플랫폼: {platform}
"""
        if influencer_personality:
            prompt += f"인플루언서 성격: {influencer_personality}\n"
        if influencer_tone:
            prompt += f"인플루언서 톤: {influencer_tone}\n"
        if include_content:
            prompt += f"포함할 내용: {include_content}\n"
        if hashtags:
            prompt += f"해시태그: {hashtags}\n"
        prompt += "\n위 정보를 바탕으로 소셜미디어 게시글 설명(본문)과 해시태그를 한국어로 생성해줘. 해시태그는 # 없이 공백으로 구분해서 따로 반환해줘.\n"

        try:
            response = await self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": "당신은 SNS 콘텐츠 작성 전문가입니다. 사용자의 입력을 바탕으로 소셜미디어용 설명과 해시태그를 생성해주세요.",
                    },
                    {"role": "user", "content": prompt},
                ],
                max_tokens=settings.OPENAI_MAX_TOKENS,
                temperature=0.7,
            )
            content = response.choices[0].message.content.strip()
            # 해시태그 추출 (예: 본문\n해시태그: tag1 tag2 ...)
            if "해시태그:" in content:
                parts = content.split("해시태그:")
                description = parts[0].strip()
                hashtags = parts[1].strip().split()
            else:
                description = content
                hashtags = []
            return {
                "social_media_content": description,
                "hashtags": hashtags,
                "model": settings.OPENAI_MODEL,
                "prompt": prompt,
            }
        except Exception as e:
            return {
                "social_media_content": f"{topic}에 대한 설명 생성 실패: {str(e)}",
                "hashtags": [],
                "model": "fallback",
                "prompt": prompt,
                "error": str(e),
            }

    async def convert_to_influencer_style(
        self,
        text: str,
        influencer_name: str,
        influencer_desc: Optional[str] = None,
        influencer_personality: Optional[str] = None,
    ) -> Dict[str, Any]:
        """생성된 설명을 인플루언서 말투로 변환 (LLM/vLLM 등 호출)"""
        # 시스템 프롬프트 구성
        system_prompt = f"너는 {influencer_name}라는 AI 인플루언서야.\n"
        if influencer_desc and str(influencer_desc).strip() != "":
            system_prompt += f"설명: {influencer_desc}\n"
        if influencer_personality and str(influencer_personality).strip() != "":
            system_prompt += f"성격: {influencer_personality}\n"
        system_prompt += "한국어로만 대답해.\n"
        # 유저 프롬프트
        user_prompt = f"""
아래 텍스트의 모든 문장과 단어를 빠짐없이, 순서와 의미를 바꾸지 말고 그대로 본문에 포함하되,
{influencer_name}의 개성(말투, 사설, 스타일 등)이 자연스럽게 드러나도록 다시 써줘.
정보는 절대 누락, 요약, 왜곡, 순서 변경 없이 모두 포함해야 하며,
인플루언서 특유의 말투, 감탄, 짧은 코멘트, 사설 등은 자연스럽게 추가해도 된다.

텍스트:
{text}
"""
        try:
            # vLLM 등 LLM 서버 호출 (여기서는 OpenAI 예시)
            response = await self.client.chat.completions.create(
                model=settings.OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=settings.OPENAI_MAX_TOKENS,
                temperature=0.7,
            )
            converted = response.choices[0].message.content.strip()
            return {
                "converted_text": converted,
                "model": settings.OPENAI_MODEL,
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
            }
        except Exception as e:
            return {
                "converted_text": f"{influencer_name} 말투 변환 실패: {str(e)}",
                "model": "fallback",
                "system_prompt": system_prompt,
                "user_prompt": user_prompt,
                "error": str(e),
            }

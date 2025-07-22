"""
OpenAI API 클라이언트 래퍼

이 모듈은 프로젝트 전반에서 사용되는 OpenAI API 호출을 표준화합니다.
- 공통 에러 처리
- 재시도 로직
- 로깅
- 설정 관리
"""

import os
import logging
import asyncio
from typing import List, Dict, Any, Optional, Union
from openai import AsyncOpenAI
import random

logger = logging.getLogger(__name__)


class OpenAIClientWrapper:
    """OpenAI API 클라이언트 래퍼 클래스"""
    
    def __init__(self, api_key: Optional[str] = None, timeout: int = 60, max_retries: int = 3):
        """
        OpenAI 클라이언트 초기화
        
        Args:
            api_key: OpenAI API 키 (None이면 환경변수에서 읽음)
            timeout: 요청 타임아웃 (초)
            max_retries: 최대 재시도 횟수
        """
        self.api_key = api_key or os.getenv('OPENAI_API_KEY')
        self.timeout = timeout
        self.max_retries = max_retries
        
        if not self.api_key:
            raise ValueError("OpenAI API 키가 설정되지 않았습니다. 환경변수 OPENAI_API_KEY를 확인하세요.")
        
        self.client = AsyncOpenAI(api_key=self.api_key, timeout=timeout)
        logger.info("✅ OpenAI 클라이언트 초기화 완료")
    
    async def chat_completion(
        self,
        messages: List[Dict[str, str]],
        model: str = "gpt-4o-mini",
        temperature: float = 0.7,
        max_tokens: Optional[int] = None,
        **kwargs
    ) -> str:
        """
        채팅 완성 API 호출
        
        Args:
            messages: 메시지 목록
            model: 사용할 모델
            temperature: 온도 파라미터
            max_tokens: 최대 토큰 수
            **kwargs: 추가 파라미터
            
        Returns:
            str: 생성된 응답 텍스트
            
        Raises:
            Exception: API 호출 실패 시
        """
        for attempt in range(self.max_retries + 1):
            try:
                logger.debug(f"OpenAI API 호출 시도 {attempt + 1}/{self.max_retries + 1}")
                
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    **kwargs
                )
                
                result = response.choices[0].message.content.strip()
                logger.debug(f"✅ OpenAI API 호출 성공 (길이: {len(result)} 문자)")
                return result
                
            except Exception as e:
                logger.warning(f"❌ OpenAI API 호출 실패 (시도 {attempt + 1}): {e}")
                
                if attempt < self.max_retries:
                    # 지수 백오프로 비동기 재시도
                    delay = (2 ** attempt) + random.uniform(0, 1)
                    logger.info(f"⏳ {delay:.1f}초 후 재시도...")
                    await asyncio.sleep(delay)
                else:
                    logger.error(f"🚫 OpenAI API 호출 최종 실패: {e}")
                    raise
    
    async def generate_question(
        self,
        character_info: str,
        temperature: float = 0.6,
        model: str = "gpt-4o-mini"
    ) -> str:
        """
        캐릭터 정보 기반 질문 생성
        
        Args:
            character_info: 캐릭터 정보
            temperature: 온도 파라미터
            model: 사용할 모델
            
        Returns:
            str: 생성된 질문
        """
        prompt = f"""
당신은 아래 캐릭터 정보를 바탕으로, 이 캐릭터가 가장 잘 드러날 수 있는 상황이나 일상적인 질문 하나를 한 문장으로 작성해주세요.

[캐릭터 정보]
{character_info}

조건:
- 질문은 반드시 하나만 작성해주세요.
- 질문은 일상적인 대화에서 자연스럽게 나올 수 있는 것이어야 합니다.
- 질문의 말투나 단어 선택도 캐릭터가 잘 드러나도록 유도해주세요.
"""

        messages = [
            {"role": "system", "content": "당신은 캐릭터 기반 대화 시나리오 생성 도우미입니다."},
            {"role": "user", "content": prompt}
        ]
        
        return await self.chat_completion(
            messages=messages,
            model=model,
            temperature=temperature,
            max_tokens=100
        )
    
    async def summarize_speech_style(
        self,
        system_prompt: str,
        model: str = "gpt-4o-mini"
    ) -> Dict[str, str]:
        """
        말투의 시스템 프롬프트를 기반으로 특징을 요약
        
        Args:
            system_prompt: 시스템 프롬프트
            model: 사용할 모델
            
        Returns:
            Dict[str, str]: 해시태그와 설명이 포함된 딕셔너리
        """
        system_instruction = """
주어진 말투의 system prompt를 기반으로 그 말투의 특징을 요약해주세요. 반드시 아래 형식을 그대로 지켜서 JSON으로 출력하세요.

형식:
{
    "hashtags": "#키워드1 #키워드2 #키워드3",
    "description": "말투 설명 (한 문장, '~말투'로 끝나야 함)"
}

조건:
1. 말투 스타일을 MZ 느낌나게 키워드 3개를 생성해 해시태그 형식으로 작성해 주세요.
2. 말투 스타일을 한 문장으로 요약해주세요. 반드시 '말투'로 끝나야 합니다. 서술어 없이 명사형으로 끝납니다.
3. 출력 형식은 반드시 JSON 형식으로 반환해주세요. (추가 설명 없이)
"""

        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": f"말투 지시사항:\n{system_prompt}"}
        ]
        
        try:
            response = await self.chat_completion(
                messages=messages,
                model=model,
                temperature=0.7,
                max_tokens=200
            )
            
            import json
            return json.loads(response)
            
        except Exception as e:
            logger.error(f"말투 요약 파싱 실패: {e}")
            return {
                "hashtags": "#GPT #응답파싱 #실패",
                "description": "말투 요약 실패한 말투"
            }
    
    async def generate_system_prompt_for_tone(
        self,
        character_info: str,
        tone_variation: int,
        model: str = "gpt-4o-mini"
    ) -> str:
        """
        캐릭터 정보를 기반으로 특정 말투에 대한 시스템 프롬프트 생성
        
        Args:
            character_info: 캐릭터 정보
            tone_variation: 말투 변형 번호 (1, 2, 3)
            model: 사용할 모델
            
        Returns:
            str: 생성된 시스템 프롬프트
        """
        tone_instructions = {
            1: "주어진 캐릭터 정보를 바탕으로 첫 번째 독특하고 창의적인 말투로 답변하세요. 캐릭터의 특성을 반영하되 예상치 못한 방식으로 표현해주세요.",
            2: "주어진 캐릭터 정보를 바탕으로 두 번째 독특하고 창의적인 말투로 답변하세요. 첫 번째와는 완전히 다른 새로운 스타일로 표현해주세요.",
            3: "주어진 캐릭터 정보를 바탕으로 세 번째 독특하고 창의적인 말투로 답변하세요. 앞의 두 가지와는 전혀 다른 참신한 방식으로 표현해주세요."
        }
        
        tone_instruction = tone_instructions.get(tone_variation, "캐릭터의 스타일을 반영한 창의적 말투를 사용하세요.")
        
        prompt = f"""
[요청 조건]
다음 캐릭터 정보에 기반하여 GPT의 말투 생성에 적합하도록 system prompt를 구성해주세요.
1. [캐릭터 정보]의 '설명'과 '성격'은 사용자가 입력한 의미를 유지하면서, GPT가 캐릭터의 말투를 자연스럽게 생성할 수 있도록 더 명확하고 생생하게 표현해주세요. 단, 새로운 설정을 추가하거나 의미를 바꾸면 안 돼요.
2. 이어서 해당 캐릭터 특성을 잘 반영한 [말투 지시사항]과 [주의사항]을 작성해주세요. 표현 방식, 말투, 감정 전달 방식 등 말투에 필요한 구체적인 특징이 드러나야 해요.
3. 전체 출력 포맷은 아래와 같아야 해요:

당신은 이제 캐릭터처럼 대화해야 합니다.

[캐릭터 정보]
{character_info}

[말투 지시사항]
{tone_instruction}

[주의사항]
{{캐릭터 특성에 따라 GPT가 직접 판단한 주의사항}}

모든 내용은 캐릭터 말투 생성을 위한 system prompt 용도로 사용되므로, 형식과 말투의 일관성을 유지해주세요.
""".strip()

        messages = [
            {"role": "system", "content": "아래 캐릭터 정보로 system prompt 전체를 구성해주세요. 문장 표현은 매끄럽고 정리된 스타일로 해주세요."},
            {"role": "user", "content": prompt}
        ]
        
        return await self.chat_completion(
            messages=messages,
            model=model,
            temperature=0.7,
            max_tokens=1000
        )


# 전역 인스턴스 (싱글톤 패턴) - thread-safe
_global_openai_client = None
_openai_client_lock = asyncio.Lock()


async def get_openai_client(**kwargs) -> OpenAIClientWrapper:
    """
    전역 OpenAI 클라이언트 인스턴스 반환 (thread-safe)
    
    Args:
        **kwargs: OpenAIClientWrapper 초기화 파라미터
        
    Returns:
        OpenAIClientWrapper: 클라이언트 인스턴스
    """
    global _global_openai_client
    
    async with _openai_client_lock:
        if _global_openai_client is None:
            _global_openai_client = OpenAIClientWrapper(**kwargs)
    
    return _global_openai_client


# 비동기 편의 함수들
async def chat_completion(messages: List[Dict[str, str]], **kwargs) -> str:
    """비동기 편의 함수: 채팅 완성 API 호출"""
    client = get_openai_client()
    return await client.chat_completion(messages, **kwargs)


async def generate_question(character_info: str, **kwargs) -> str:
    """비동기 편의 함수: 질문 생성"""
    client = get_openai_client()
    return await client.generate_question(character_info, **kwargs)


async def summarize_speech_style(system_prompt: str, **kwargs) -> Dict[str, str]:
    """비동기 편의 함수: 말투 요약"""
    client = get_openai_client()
    return await client.summarize_speech_style(system_prompt, **kwargs)
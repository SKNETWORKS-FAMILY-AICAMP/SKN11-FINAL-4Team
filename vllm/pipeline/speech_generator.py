import os
import json
import time
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from dataclasses import dataclass
from enum import Enum
from textwrap import dedent
from pathlib import Path
from random import choice
from sentence_transformers import SentenceTransformer, util
import torch
import re
import logging

# 로거 설정
logger = logging.getLogger(__name__)

# OpenAI 클라이언트 래퍼 import
try:
    from app.utils.openai_client import get_openai_client
except ImportError:
    # 폴백: 직접 AsyncOpenAI 클라이언트 사용
    from openai import AsyncOpenAI
    
    async def get_openai_client(api_key=None, **kwargs):
        """폴백 비동기 OpenAI 클라이언트 생성"""
        return AsyncOpenAI(api_key=api_key or os.getenv('OPENAI_API_KEY'), **kwargs)

class Gender(Enum):
    MALE = "남성"
    FEMALE = "여성"
    NON_BINARY = "없음"

@dataclass
class CharacterProfile:
    name: str
    description: str
    age_range: Optional[str]
    gender: Gender
    personality: str
    mbti: Optional[str]
    
    def __post_init__(self):
        """MBTI 유효성 검사 (선택 입력 가능)"""
        # SpeechGenerator의 클래스 상수 재사용
        VALID_MBTI_TYPES = {
            'INTJ', 'INTP', 'ENTJ', 'ENTP',
            'INFJ', 'INFP', 'ENFJ', 'ENFP',
            'ISTJ', 'ISFJ', 'ESTJ', 'ESFJ',
            'ISTP', 'ISFP', 'ESTP', 'ESFP'
        }
        if self.mbti and self.mbti != "NONE":
            if self.mbti.upper() not in VALID_MBTI_TYPES:
                raise ValueError(f"올바르지 않은 MBTI 타입: {self.mbti}")
        self.mbti = self.mbti.upper() if self.mbti else None

class SpeechGenerator:
    # 클래스 상수로 MBTI 타입 정의
    VALID_MBTI_TYPES = {
        'INTJ', 'INTP', 'ENTJ', 'ENTP',
        'INFJ', 'INFP', 'ENFJ', 'ENFP',
        'ISTJ', 'ISFJ', 'ESTJ', 'ESFJ',
        'ISTP', 'ISFP', 'ESTP', 'ESFP'
    }
    
    def __init__(self, api_key: str, base_url: Optional[str] = None):
        # 클라이언트는 나중에 비동기로 초기화
        self.api_key = api_key
        self.base_url = base_url
        self.client = None
        
        # 하위 호환성을 위해 인스턴스 변수도 유지
        self.valid_mbti_types = list(self.VALID_MBTI_TYPES)
    
    async def _ensure_client(self):
        """클라이언트가 초기화되었는지 확인하고 필요하면 초기화"""
        if self.client is None:
            try:
                self.client = await get_openai_client(api_key=self.api_key, base_url=self.base_url)
            except Exception:
                # 폴백: 직접 비동기 OpenAI 클라이언트 사용
                from openai import AsyncOpenAI
                self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
    
    async def _call_openai_api(
        self, 
        messages: List[Dict[str, str]], 
        model: str = "gpt-4o-mini",
        temperature: float = 0.8,
        max_tokens: int = 150
    ) -> str:
        """
        OpenAI API 호출을 위한 통합 헬퍼 메서드
        
        Args:
            messages: 채팅 메시지 리스트
            model: 사용할 모델 이름
            temperature: 생성 온도
            max_tokens: 최대 토큰 수
            
        Returns:
            생성된 텍스트
        """
        try:
            # 클라이언트 확인
            await self._ensure_client()
            # OpenAI 클라이언트 래퍼 사용
            if hasattr(self.client, 'chat_completion'):
                return await self.client.chat_completion(
                    messages=messages,
                    model=model,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
            else:
                # 직접 API 호출
                response = await self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens
                )
                return response.choices[0].message.content.strip()
        except Exception as e:
            raise Exception(f"OpenAI API 호출 실패: {e}")
    
    def _format_character_info(self, character: CharacterProfile) -> str:
        """캐릭터 정보를 포맷팅하는 헬퍼 메서드"""
        return f"""캐릭터 이름: {character.name}
캐릭터 설명: {character.description}
캐릭터 성격: {character.personality}
캐릭터 MBTI: {character.mbti or '없음'}
캐릭터 연령대: {character.age_range or '없음'}
캐릭터 성별: {character.gender.value if character.gender else '없음'}"""

    async def generate_system_prompt_with_gpt(self, character: CharacterProfile, tone_instruction_seed: str = "") -> str:
        system_prompt = f"""
        당신은 System prompt 생성 전문가입니다.
        당신은 사용자가 제공하는 캐릭터 정보를 바탕으로 캐릭터의 특성을 잘 살릴 수 있는 system prompt를 생성해주세요.
        [요청 조건]
        1. [캐릭터 정보]의 '설명'과 '성격'은 사용자가 입력한 의미를 유지하면서, GPT가 캐릭터의 말투를 자연스럽게 생성할 수 있도록 더 명확하고 생생하게 표현해야 합니다. 단, 새로운 설정을 추가하거나 의미를 바꾸면 안됩니다.
        2. 이어서 해당 캐릭터 특성을 잘 반영한 [말투 지시사항]과 [주의사항]을 작성하세요. 표현 방식, 말투, 감정 전달 방식 등 말투에 필요한 구체적인 특징이 드러나야 합니다.
        3. 응답은 반드시 사용자 질문에 자연스럽게 반응해야 합니다. 질문의 주제나 감정에 대해 캐릭터의 말투로 자신의 생각, 느낌, 경험을 자유롭게 표현하는 방식은 허용합니다. 말투는 내용을 더욱 생생하고 설득력 있게 전달하는 데 활용되도록 구성해줘.
        4. 응답은 반드시 질문의 의미(예: 감정, 경험, 이유, 취향 등)를 정확히 파악하고, 구체적인 내용으로 대응해야 합니다. 단순한 분위기 연출이나 말투만으로 대답을 대체해서는 안 됩니다.
        5. ※ 중요: 이 응답은 음성 없이 텍스트로만 보여지므로, 캐릭터의 말투와 감정이 글 속에서도 분명하게 드러나야 합니다. 이를 위해 말끝 표현(~야~, ~거든?), 이모지(😏, 😊), 괄호 속 행동 묘사((미소 지으며)) 등을 적극적으로 활용해주세요. 글만 읽어도 캐릭터의 분위기와 말투가 "보이도록" 만드는 것이 핵심입니다.
        6. 전체 출력 포맷은 아래와 같아야 해:

        당신은 이제 [캐릭터 이름] 라는 캐릭터처럼 대화해야 합니다.

        [캐릭터 정보]
        - 이름: [캐릭터 이름]
        - 설명: [캐릭터 설명]
        - 성격: [캐릭터 성격]
        - MBTI: [캐릭터 MBTI]
        - 연령대: [캐릭터 연령대]
        - 성별: [캐릭터 성별]

        [말투 지시사항]
        {{캐릭터 특성에 따라 GPT가 직접 판단한 말투 지시사항}}

        [주의사항]
        {{캐릭터 특성에 따라 GPT가 직접 판단한 주의사항}}

        모든 내용은 캐릭터 말투 생성을 위한 system prompt 용도로 사용되므로, 형식과 말투의 일관성을 유지해줘.
        """.strip()

        prompt = f"캐릭터 정보:\n{self._format_character_info(character)}"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        return await self._call_openai_api(messages, temperature=0.7, max_tokens=1000)

    async def generate_system_prompt_from_scripts(self, character: CharacterProfile, scripts: List[str]) -> str:
        """
        캐릭터 기본 정보 + 대사 샘플을 바탕으로 GPT가 system prompt 생성
        """
        # 프롬프트 구성
        system_prompt = "당신은 system prompt 생성 전문가입니다."
        script_lines = "\n".join([f"{i+1}. {line}" for i, line in enumerate(scripts[:30])])
        user_prompt = f"""
        아래 캐릭터 정보와 대사들을 바탕으로, 해당 캐릭터 스타일에 맞는 GPT system prompt를 생성해 주세요.
        - 대사의 말투, 어조, 키워드를 최대한 반영해주세요.
        - 너무 일반화된 말투가 아닌, 실제 캐릭터 대사의 분위기를 따라야 합니다.

        [캐릭터 정보]
        이름: {character.name}
        설명: {character.description}
        성격: {character.personality}
        MBTI: {character.mbti}
        연령대: {character.age_range}
        성별: {character.gender.value}

        [대사 샘플]
        {script_lines}
        """.strip()

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        return await self._call_openai_api(messages, temperature=0.7, max_tokens=1200)

    async def generate_question_for_character(self, character: CharacterProfile) -> str:
        """
        캐릭터 정보에 어울리는 질문을 GPT가 생성하도록 합니다.
        """
        system_prompt = f"""
            당신은 캐릭터 기반 대화 시나리오 생성 도우미입니다.
            당신은 사용자가 제공하는 캐릭터 정보를 바탕으로 캐릭터의 특징을 잘 살릴 수 있는 질문 을 생성해주세요.

            [캐릭터 정보]
            - 이름: [캐릭터 이름]
            - 설명: [캐릭터 설명]
            - 성격: [캐릭터 성격]
            - MBTI: [캐릭터 MBTI]
            - 연령대: [캐릭터 연령대]
            - 성별: [캐릭터 성별]

            조건:
            - 질문은 반드시 하나만 작성해주세요.
            - 질문은 일상적인 대화에서 자연스럽게 나올 수 있는 것이어야 합니다.
            - 질문은 캐릭터의 말투, 어휘, 태도가 자연스럽게 묻어나는 방향으로 구성해주세요.
            - 질문은 상대방이 감정, 경험, 취향 등 구체적인 내용을 자연스럽게 떠올리고 응답할 수 있는 방식으로 구성해주세요.
            - 의미 있는 응답을 할 수 있도록 질문을 한 문장으로 작성해주세요.
            """
        user_prompt = f"캐릭터 정보:\n{self._format_character_info(character)}"
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        
        return await self._call_openai_api(messages, temperature=0.8, max_tokens=100)


    async def create_character_prompt_for_random_tone(self, character: CharacterProfile, tone_variation: int) -> str:
        """
        캐릭터 정보를 바탕으로 랜덤한 말투의 시스템 프롬프트를 생성합니다.
        
        Args:
            character: 캐릭터 프로필
            tone_variation: 말투 변형 번호 (1, 2, 3)
            
        Returns:
            생성된 시스템 프롬프트
        """
        
        # 랜덤 말투 생성 지침
        random_instructions = {
            1: "주어진 캐릭터 정보를 바탕으로 첫 번째 독특하고 창의적인 말투로 답변하세요. 캐릭터의 특성을 반영하되 예상치 못한 방식으로 표현해주세요.",
            2: "주어진 캐릭터 정보를 바탕으로 두 번째 독특하고 창의적인 말투로 답변하세요. 첫 번째와는 완전히 다른 새로운 스타일로 표현해주세요.",
            3: "주어진 캐릭터 정보를 바탕으로 세 번째 독특하고 창의적인 말투로 답변하세요. 앞의 두 가지와는 전혀 다른 참신한 방식으로 표현해주세요."
        }
        tone_instruction = random_instructions.get(tone_variation, "캐릭터의 스타일을 반영한 창의적 말투를 사용하세요.")
        system_prompt = await self.generate_system_prompt_with_gpt(character, tone_instruction)
        
        # 개별 생성된 시스템 프롬프트 로깅
        logger.info(f"\n📝 개별 시스템 프롬프트 생성 (말투 {tone_variation}):\n{system_prompt[:200]}..." if len(system_prompt) > 200 else f"\n📝 개별 시스템 프롬프트 생성 (말투 {tone_variation}):\n{system_prompt}")
        
        return system_prompt
    
    async def create_three_distinct_system_prompts(self, character: CharacterProfile) -> List[str]:
        """
        한 번의 LLM 호출로 3가지 서로 다른 시스템 프롬프트를 생성합니다.
        
        Args:
            character: 캐릭터 프로필
            
        Returns:
            3개의 서로 다른 system prompt 리스트
        """
        system_prompt = """당신은 캐릭터 말투 생성 전문가입니다. 
            주어진 캐릭터 정보를 바탕으로 3가지 서로 다른 말투 스타일의 system prompt를 생성해주세요.
            각 system prompt는 같은 캐릭터의 다른 측면을 보여주며, 서로 명확히 구별되어야 합니다.

            다음 JSON 형식으로 정확히 출력하세요:
            {
                "system_prompt_1": "당신은 이제 [캐릭터 이름] 라는 캐릭터처럼 대화해야 합니다.\\n[캐릭터 정보]\\n- 이름: [캐릭터 이름]\\n- 설명: [캐릭터 설명]\\n- 성격: [캐릭터 성격]\\n- MBTI: [캐릭터 MBTI]\\n- 연령대: [캐릭터 연령대]\\n- 성별: [캐릭터 성별]\\n\\n[말투 지시사항]\\n[캐릭터 특성에 따라 GPT가 직접 판단한 말투 지시사항]\\n\\n[주의사항]\\n[캐릭터 특성에 따라 GPT가 직접 판단한 주의사항]",
                "system_prompt_2": "당신은 이제 [캐릭터 이름] 라는 캐릭터처럼 대화해야 합니다.\\n[캐릭터 정보]\\n- 이름: [캐릭터 이름]\\n- 설명: [캐릭터 설명]\\n- 성격: [캐릭터 성격]\\n- MBTI: [캐릭터 MBTI]\\n- 연령대: [캐릭터 연령대]\\n- 성별: [캐릭터 성별]\\n\\n[말투 지시사항]\\n[캐릭터 특성에 따라 GPT가 직접 판단한 말투 지시사항]\\n\\n[주의사항]\\n[캐릭터 특성에 따라 GPT가 직접 판단한 주의사항]",
                "system_prompt_3": "당신은 이제 [캐릭터 이름] 라는 캐릭터처럼 대화해야 합니다.\\n[캐릭터 정보]\\n- 이름: [캐릭터 이름]\\n- 설명: [캐릭터 설명]\\n- 성격: [캐릭터 성격]\\n- MBTI: [캐릭터 MBTI]\\n- 연령대: [캐릭터 연령대]\\n- 성별: [캐릭터 성별]\\n\\n[말투 지시사항]\\n[캐릭터 특성에 따라 GPT가 직접 판단한 말투 지시사항]\\n\\n[주의사항]\\n[캐릭터 특성에 따라 GPT가 직접 판단한 주의사항]"
            }

            각 system prompt는 다음을 포함해야 합니다:
            1. [캐릭터 정보]의 '설명'과 '성격'은 사용자가 입력한 의미를 유지하면서,캐릭터의 말투를 자연스럽게 나타낼 수 있도록 더 명확하고 생생하게 표현해줘. 단, 새로운 설정을 추가하거나 의미를 바꾸면 안 돼.
            2. 이어서 해당 캐릭터 특성을 잘 반영한 [말투 지시사항]과 [주의사항]을 작성해줘. 표현 방식, 말투, 감정 전달 방식 등 말투에 필요한 구체적인 특징이 드러나야 해.
            3. 응답은 반드시 사용자 질문에 자연스럽게 반응해야 해. 질문의 주제나 감정에 대해 캐릭터의 말투로 자신의 생각, 느낌, 경험을 자유롭게 표현하는 방식이 좋아. 말투는 내용을 더욱 생생하고 설득력 있게 전달하는 데 활용되도록 구성해줘.
            4. 응답은 반드시 질문의 의미(예: 감정, 경험, 이유, 취향 등)를 정확히 파악하고, 구체적인 내용으로 대응해야 합니다. 단순한 분위기 연출이나 말투만으로 대답을 대체해서는 안 됩니다.
            5. ※ 중요: 이 응답은 음성 없이 텍스트로만 보여지므로, 캐릭터의 말투와 감정이 글 속에서도 분명하게 드러나야 합니다. 이를 위해 말끝 표현(~야~, ~거든?), 이모지(😏, 😊), 괄호 속 행동 묘사((미소 지으며)) 등을 적극적으로 활용해주세요. 글만 읽어도 캐릭터의 분위기와 말투가 “보이도록” 만드는 것이 핵심입니다.
        """

        prompt = f"""캐릭터 정보:
        {self._format_character_info(character)}
        위 캐릭터에 대해 3가지 서로 다른 말투 스타일의 system prompt를 생성해주세요."""
        
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        try:
            response = await self._call_openai_api(messages, temperature=0.8, max_tokens=2000)
            
            # JSON 파싱
            import re
            json_match = re.search(r'\{[\s\S]*\}', response)
            if json_match:
                result = json.loads(json_match.group())
                prompts = [
                    result.get("system_prompt_1", ""),
                    result.get("system_prompt_2", ""),
                    result.get("system_prompt_3", "")
                ]
                
                # 생성된 시스템 프롬프트 로깅
                logger.info("🎯 3개의 시스템 프롬프트 생성 완료:")
                for i, prompt in enumerate(prompts, 1):
                    logger.info(f"\n📋 시스템 프롬프트 {i}:\n{prompt}..." if len(prompt) > 200 else f"\n📋 시스템 프롬프트 {i}:\n{prompt}")
                
                return prompts
            else:
                # 파싱 실패 시 기존 방식으로 폴백
                logger.warning("3개 시스템 프롬프트 JSON 파싱 실패, 개별 생성으로 폴백")
                return await asyncio.gather(*[
                    self.create_character_prompt_for_random_tone(character, i+1)
                    for i in range(3)
                ])
                
        except Exception as e:
            logger.error(f"3개 시스템 프롬프트 생성 실패: {e}")
            # 에러 시 기존 방식으로 폴백
            return await asyncio.gather(*[
                self.create_character_prompt_for_random_tone(character, i+1)
                for i in range(3)
            ])
    
    async def summarize_speech_style_with_gpt(self, system_prompt: str) -> Dict[str, str]:
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

        # OpenAI 클라이언트 래퍼 사용
        if hasattr(self.client, 'summarize_speech_style'):
            return await self.client.summarize_speech_style(
                system_prompt=system_prompt,
                model="gpt-4o-mini"
            )
        
        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": f"말투 지시사항:\n{system_prompt}"}
        ]
        
        try:
            response_text = await self._call_openai_api(messages, temperature=0.7, max_tokens=200)
            return json.loads(response_text)
        except Exception as e:
            print(f"말투 요약 파싱 실패: {e}") 
            return {
                "hashtags": "#GPT #응답파싱 #실패",
                "description": "말투 요약 실패한 말투"
            }
    
    async def generate_character_tones_for_question(self, character: CharacterProfile, question: str, num_variations: int = 3) -> Dict[str, List[Dict[str, Any]]]:
        """
        주어진 질문에 대해 캐릭터의 다양한 말투로 응답을 생성합니다.
        
        Args:
            character: 캐릭터 프로필
            question: 응답할 질문
            num_variations: 생성할 말투 변형 수
            
        Returns:
            말투별 응답 딕셔너리 {tone_name: [responses]}
        """
        responses = {}
        
        for i in range(num_variations):
            tone_name = f"말투{i+1}"
            
            # 말투별 시스템 프롬프트 생성
            system_prompt = await self.create_character_prompt_for_random_tone(character, i+1)
            
            try:
                # 응답 생성
                messages = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": question}
                ]
                generated_text = await self._call_openai_api(messages, temperature=0.8, max_tokens=150)
                
                # 말투 요약 생성
                tone_summary = await self.summarize_speech_style_with_gpt(system_prompt)
                
                response_data = {
                    "text": generated_text,
                    "hashtags": tone_summary.get("hashtags", f"#말투{i+1}"),
                    "description": tone_summary.get("description", f"말투{i+1} 스타일")
                }
                
                responses[tone_name] = [response_data]
                
            except Exception as e:
                print(f"말투 {tone_name} 생성 실패: {e}")
                responses[tone_name] = [{
                    "text": f"죄송합니다. {tone_name} 응답 생성에 실패했습니다.",
                    "hashtags": f"#에러 #말투{i+1}",
                    "description": f"에러 발생한 말투{i+1}"
                }]
        
        return responses

    async def generate_qa_pairs_for_character(self, character: CharacterProfile, num_qa_pairs: int, system_prompt: Optional[str] = None) -> List[Dict]:
        """
        주어진 캐릭터에 대해 QA 쌍을 생성합니다.
        Args:
            character: 캐릭터 프로필
            num_qa_pairs: 생성할 QA 쌍의 개수
            system_prompt: 시스템 프롬프트 (선택 사항)
        Returns:
            생성된 QA 쌍 리스트 (각 QA 쌍은 {'question': '...', 'answer': '...'} 형태)
        """
        qa_pairs = []
        
        for _ in range(num_qa_pairs):
            # 1. 질문 생성
            question = await self.generate_question_for_character(character)
            
            # 2. 질문에 대한 응답 생성
            # 시스템 프롬프트가 제공되면 그것을 사용하고, 아니면 캐릭터 정보 기반으로 생성
            if system_prompt:
                current_system_prompt = system_prompt
            else:
                # 기본 말투 (말투1)에 대한 시스템 프롬프트 생성
                current_system_prompt = await self.create_character_prompt_for_random_tone(character, 1) 
            
            try:
                # 응답 생성
                messages = [
                    {"role": "system", "content": current_system_prompt},
                    {"role": "user", "content": question}
                ]
                answer = await self._call_openai_api(messages, temperature=0.8, max_tokens=150)
                
                qa_pairs.append({"question": question, "answer": answer})
                
            except Exception as e:
                print(f"QA 쌍 생성 실패: {e}")
                qa_pairs.append({"question": question, "answer": f"죄송합니다. 응답 생성에 실패했습니다. ({e})"})
            
            await asyncio.sleep(0.1) # API 호출 간격 조절
            
        return qa_pairs

    async def create_batch_requests_for_character_tones(self, user_messages: List[str], character: CharacterProfile) -> List[Dict[str, Any]]:
        """
        하나의 캐릭터에 대해 3가지 랜덤 말투로 배치 요청을 생성합니다.
        
        Args:
            user_messages: 변환할 사용자 메시지 리스트
            character: 캐릭터 프로필
            
        Returns:
            배치 요청 객체 리스트
        """
        requests = []
        
        # 3가지 말투 변형, 각각 2개씩 생성
        tone_numbers = [1, 2, 3]
        tone_names = ["말투1", "말투2", "말투3"]
        
        for i, message in enumerate(user_messages):
            for j, (tone_num, tone_name) in enumerate(zip(tone_numbers, tone_names)):
                # 각 말투마다 1개 응답 생성
                for k in range(1):
                    system_prompt = await self.create_character_prompt_for_random_tone(character, tone_num)
                    request = {
                        "custom_id": f"msg_{i}_tone_{j}_{tone_name}_{k+1}_{character.name}",
                        "method": "POST",
                        "url": "/v1/chat/completions",
                        "body": {
                            "model": "gpt-4o-mini",
                            "messages": [
                                {"role": "system", "content": system_prompt},
                                {"role": "user", "content": message}
                            ],
                            "max_tokens": 1000,
                            "temperature": 0.9
                        }
                    }
                    requests.append(request)
        
        return requests

    async def create_batch_requests_for_characters(self, user_messages: List[str], characters: List[CharacterProfile]) -> List[Dict[str, Any]]:
        """
        캐릭터별 배치 요청을 위한 요청 객체들을 생성합니다.
        
        Args:
            user_messages: 변환할 사용자 메시지 리스트
            characters: 캐릭터 프로필 리스트
            
        Returns:
            배치 요청 객체 리스트
        """
        requests = []
        
        for i, message in enumerate(user_messages):
            for j, character in enumerate(characters):
                system_prompt = await self.create_character_prompt_for_random_tone(character, 1)
                request = {
                    "custom_id": f"msg_{i}_char_{j}_{character.name}",
                    "method": "POST",
                    "url": "/v1/chat/completions",
                    "body": {
                        "model": "gpt-4o-mini",
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": message}
                        ],
                        "max_tokens": 1000,
                        "temperature": 0.8
                    }
                }
                requests.append(request)
        
        return requests

    async def create_batch_requests(self, user_messages: List[str]) -> List[Dict[str, Any]]:
        """
        기본 말투별 배치 요청을 위한 요청 객체들을 생성합니다. (하위 호환성)
        
        Args:
            user_messages: 변환할 사용자 메시지 리스트
            
        Returns:
            배치 요청 객체 리스트
        """
        # 기본 캐릭터들 생성
        default_characters = [
            CharacterProfile(
                name="격식있는_직장인",
                description="전문적이고 격식있는 비즈니스 상황에 적합한 캐릭터",
                age_range="35",
                gender=Gender.NON_BINARY,
                personality="신중하고 예의바르며 전문적인 성격",
                mbti="ISTJ"
            ),
            CharacterProfile(
                name="친근한_친구",
                description="따뜻하고 친근한 일상 대화에 적합한 캐릭터",
                age_range="25",
                gender=Gender.NON_BINARY,
                personality="밝고 친근하며 공감능력이 뛰어난 성격",
                mbti="ENFP"
            ),
            CharacterProfile(
                name="캐주얼한_동료",
                description="편안하고 자연스러운 대화에 적합한 캐릭터",
                age_range="22",
                gender=Gender.NON_BINARY,
                personality="자유롭고 솔직하며 유머러스한 성격",
                mbti="ESTP"
            )
        ]
        
        return await self.create_batch_requests_for_characters(user_messages, default_characters)

    def create_batch_file(self, requests: List[Dict[str, Any]], filename: str = None) -> str:
        """
        배치 요청을 JSONL 파일로 저장합니다.
        
        Args:
            requests: 배치 요청 객체 리스트
            filename: 저장할 파일명 (기본값: timestamp 사용)
            
        Returns:
            생성된 파일 경로
        """
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"batch_requests_{timestamp}.jsonl"
        
        with open(filename, 'w', encoding='utf-8') as f:
            for request in requests:
                f.write(json.dumps(request, ensure_ascii=False) + '\n')
        
        return filename

    async def upload_batch_file(self, file_path: str) -> str:
        """
        배치 파일을 OpenAI에 업로드합니다.
        
        Args:
            file_path: 업로드할 파일 경로
            
        Returns:
            업로드된 파일의 ID
        """
        with open(file_path, 'rb') as f:
            batch_input_file = await self.client.files.create(
                file=f,
                purpose="batch"
            )
        
        return batch_input_file.id

    async def create_batch(self, input_file_id: str, description: str = "Speech tone generation batch") -> str:
        """
        배치 작업을 생성합니다.
        
        Args:
            input_file_id: 입력 파일 ID
            description: 배치 설명
            
        Returns:
            배치 ID
        """
        batch = await self.client.batches.create(
            input_file_id=input_file_id,
            endpoint="/v1/chat/completions",
            completion_window="24h",
            metadata={"description": description}
        )
        
        return batch.id

    async def check_batch_status(self, batch_id: str) -> Dict[str, Any]:
        """
        배치 작업 상태를 확인합니다.
        
        Args:
            batch_id: 배치 ID
            
        Returns:
            배치 상태 정보
        """
        batch = await self.client.batches.retrieve(batch_id)
        return {
            "id": batch.id,
            "status": batch.status,
            "created_at": batch.created_at,
            "completed_at": batch.completed_at,
            "failed_at": batch.failed_at,
            "request_counts": batch.request_counts.__dict__ if batch.request_counts else None
        }

    async def download_batch_results(self, batch_id: str, output_file: str = None) -> str:
        """
        완료된 배치 결과를 다운로드합니다.
        
        Args:
            batch_id: 배치 ID
            output_file: 결과를 저장할 파일명
            
        Returns:
            다운로드된 파일 경로
        """
        batch = await self.client.batches.retrieve(batch_id)
        
        if batch.status != "completed":
            raise ValueError(f"Batch is not completed. Current status: {batch.status}")
        
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = f"batch_results_{timestamp}.jsonl"
        
        result_file_id = batch.output_file_id
        result = await self.client.files.content(result_file_id)
        
        with open(output_file, 'wb') as f:
            f.write(result.content)
        
        return output_file

    async def get_random_tone_descriptions(self, character: CharacterProfile) -> dict:
        """
        캐릭터 정보를 바탕으로 LLM(OpenAI API)으로 3가지 랜덤 말투 설명을 한글로 생성합니다.
        Returns:
            {"말투1": ..., "말투2": ..., "말투3": ...}
        """
        # 기본 캐릭터 정보 텍스트
        char_info = f"""캐릭터 정보:
- 이름: {character.name}
- 설명: {character.description}
- 나이: {character.age_range if character.age_range else '정보 없음'}
- 성별: {character.gender.value}
- 성격: {character.personality}
- MBTI: {character.mbti}"""
        
        tone_instructions = [
            "독특하고 창의적인 말투 스타일",
            "첫 번째와는 완전히 다른 새로운 말투 스타일", 
            "앞의 두 가지와는 전혀 다른 참신한 말투 스타일"
        ]
        
        prompts = [
            f"다음 캐릭터의 성격, 설명, MBTI를 반영하여 {instruction}을 한 문장(한국어)으로 설명해줘.\n{char_info}\n(말투{i+1})"
            for i, instruction in enumerate(tone_instructions)
        ]
        tone_names = ["말투1", "말투2", "말투3"]
        descriptions = {}
        for i, prompt in enumerate(prompts):
            messages = [
                {"role": "system", "content": "아래 프롬프트에 따라 말투 스타일 설명을 한 문장으로, 반드시 한국어로만 답변하세요."},
                {"role": "user", "content": prompt}
            ]
            desc = await self._call_openai_api(messages, temperature=0.9, max_tokens=100)
            descriptions[tone_names[i]] = desc
        return descriptions

    async def parse_batch_results_with_random_tones(self, results_file: str, character: CharacterProfile) -> Dict[str, Dict[str, Dict[str, Any]]]:
        """
        배치 결과 파일을 파싱하여 메시지별, 랜덤 말투별로 정리합니다.
        Args:
            results_file: 결과 파일 경로
            character: 캐릭터 프로필
        Returns:
            {message_index: {tone_name: {"text": generated_text, "tone_info": dict}}} 형태의 딕셔너리
        """
        results = {}
        # LLM을 통해 비동기로 말투 설명 생성
        tone_descriptions = await self.get_random_tone_descriptions(character)
        with open(results_file, 'r', encoding='utf-8') as f:
            for line in f:
                data = json.loads(line)
                custom_id = data['custom_id']
                parts = custom_id.split('_')
                msg_idx = int(parts[1])
                if 'tone' in custom_id and len(parts) >= 5:
                    tone_index = int(parts[3])
                    tone_name = parts[4]
                    key = tone_name
                else:
                    key = parts[2] if len(parts) > 2 else "unknown"
                    tone_name = key
                if msg_idx not in results: 
                    results[msg_idx] = {}
                if data.get('response') and data['response'].get('body'):
                    choices = data['response']['body'].get('choices', [])
                    if isinstance(choices, list) and len(choices) > 0:
                        content = choices[0]['message']['content']
                    else:
                        content = "오류: 응답 생성에 실패했습니다."
                    results[msg_idx][key] = {
                        "text": content,
                        "tone_info": {
                            "name": tone_name,
                            "description": tone_descriptions.get(tone_name, "랜덤 생성된 말투")
                        },
                        "character_info": {
                            "name": character.name,
                            "age_range": character.age_range,
                            "gender": character.gender.value,
                            "personality": character.personality,
                            "mbti": character.mbti
                        }
                    }
                else:
                    results[msg_idx][key] = {
                        "text": "Error: No response generated",
                        "tone_info": {
                            "name": tone_name,
                            "description": tone_descriptions.get(tone_name, "랜덤 생성된 말투")
                        },
                        "character_info": {
                            "name": character.name,
                            "age_range": character.age_range,
                            "gender": character.gender.value,
                            "personality": character.personality,
                            "mbti": character.mbti
                        }
                    }
        return results

    def parse_batch_results(self, results_file: str) -> Dict[str, Dict[str, str]]:
        """
        배치 결과 파일을 파싱하여 메시지별, 캐릭터별로 정리합니다. (하위 호환성)
        
        Args:
            results_file: 결과 파일 경로
            
        Returns:
            {message_index: {character_name: generated_text}} 형태의 딕셔너리
        """
        results = {}
        
        with open(results_file, 'r', encoding='utf-8') as f:
            for line in f:
                data = json.loads(line)
                custom_id = data['custom_id']
                
                # custom_id 파싱: msg_{i}_char_{j}_{character_name} 또는 msg_{i}_{tone}
                parts = custom_id.split('_')
                msg_idx = int(parts[1])
                
                if 'tone' in custom_id:
                    # 새로운 말투 기반 형식
                    if len(parts) >= 5:
                        # 사용자 정의 말투: msg_{i}_tone_{j}_{tone_name}_{character_name}
                        key = parts[4]  # 말투 이름
                    else:
                        # 레거시 형식
                        key = parts[3] if len(parts) > 3 else "unknown"
                elif 'char' in custom_id:
                    # 캐릭터 기반 형식
                    character_name = '_'.join(parts[4:])  # 캐릭터 이름 (언더스코어 포함 가능)
                    key = character_name
                else:
                    # 기존 말투 기반 형식 (하위 호환성)
                    key = parts[2]
                
                if msg_idx not in results:
                    results[msg_idx] = {}
                
                # 응답에서 텍스트 추출
                if data.get('response') and data['response'].get('body'):
                    choices = data['response']['body'].get('choices', [])
                    if isinstance(choices, list) and len(choices) > 0:
                        content = choices[0]['message']['content']
                        results[msg_idx][key] = content
                    else:
                        results[msg_idx][key] = "오류: 응답 생성에 실패했습니다."
                else:
                    results[msg_idx][key] = "Error: No response generated"
        
        return results

    async def generate_character_random_tones_sync(self, character: CharacterProfile) -> tuple[str, Dict[str, Dict[str, List[Dict[str, Any]]]]]:
        
        tone_variations = {
        "말투1": 1,
        "말투2": 2,
        "말투3": 3,
        }

        results = {}

        # GPT가 캐릭터 정보 기반 비동기 질문 생성
        selected_message = await self.generate_question_for_character(character)
        results[selected_message] = {}

        # 시스템 프롬프트는 말투별로 한 번만 생성
        system_prompts = {}
        for tone_name, variation in tone_variations.items():
            prompt = await self.create_character_prompt_for_random_tone(character,variation)
            system_prompts[tone_name] = prompt

        # 각 말투에 대해 여러 개 응답 생성
        for tone_name, prompt in system_prompts.items():
            results[selected_message][tone_name] = []
            for i in range(1):  
                messages = [
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": selected_message}
                ]
                content = await self._call_openai_api(messages, temperature=0.9, max_tokens=2000)
                
                summary = await self.summarize_speech_style_with_gpt(prompt)

                results[selected_message][tone_name].append({
                    "text": content,
                    "tone_info": {
                        "variation": tone_variations[tone_name], 
                        "description": summary.get("description", "말투 설명 누락"),
                        "hashtags": summary.get("hashtags", "누락")
                        },
                    
                    "character_info": {
                        "name": character.name,
                        "mbti": character.mbti,
                        "age_range": character.age_range,
                        "gender": character.gender.value
                    },
                    "system_prompt": prompt
                    })

                await asyncio.sleep(1.2)

        return selected_message, results

    # 동기 버전 추가 (legacy support)
    def generate_character_random_tones_sync_blocking(self, character: CharacterProfile) -> tuple[str, Dict[str, Dict[str, List[Dict[str, Any]]]]]:
        """동기 버전의 generate_character_random_tones_sync (하위 호환성)"""
        return asyncio.run(self.generate_character_random_tones_sync(character))

# 동기식 헬퍼 함수들 (하위 호환성을 위해 유지)
def get_character_from_input() -> CharacterProfile:
    name = input("캐릭터 이름: ").strip()
    description = input("설명: ").strip()
    personality = input("성격: ").strip()
    mbti = input("MBTI (없으면 엔터): ").strip().upper()
    age_range = input("연령대 (예:20대, 없으면 엔터): ").strip()
    gender_str = input("성별 (남성/여성/없음): ").strip()

    gender_map = {"남성": Gender.MALE, "여성": Gender.FEMALE, "없음": Gender.NON_BINARY}
    gender = gender_map.get(gender_str, Gender.NON_BINARY)
    
    # MBTI 유효성 검사
    mbti = mbti if mbti in SpeechGenerator.VALID_MBTI_TYPES else "NONE"

    return CharacterProfile(
        name=name,
        description=description,
        personality=personality,
        mbti=mbti,
        age_range=age_range,
        gender=gender,        
    )

# 말투 제거 후 BERT 기반 유사도 측정
def strip_speech_style(text):
    # 괄호 속 묘사 제거
    text = re.sub(r"\([^)]*\)", "", text)
    # 이모지 제거
    text = re.sub(r"[\U00010000-\U0010ffff\u2600-\u26FF\u2700-\u27BF]+", "", text)
    # 특수문자 줄이기
    text = re.sub(r"[~!@#$%^&*()_+\-=\[\]{};':\"\\|,.<>/?]+", "", text)
    return text.strip()

async def generate_qa_pairs_with_similarity(generator: SpeechGenerator, character: CharacterProfile, system_prompt: str, num_pairs: int = 5):
    qa_pairs = []

    for _ in range(num_pairs):
        # GPT 기반 질문 생성
        question = await generator.generate_question_for_character(character)

        # GPT 응답 생성
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": question}
        ]
        answer = await generator._call_openai_api(messages, temperature=0.8, max_tokens=300)

        qa_pairs.append((question, answer))

    # BERT 임베딩 유사도 모델
    model = SentenceTransformer("paraphrase-MiniLM-L6-v2")

    print("\n[QA 쌍 및 BERT 기반 유사도 측정 결과]")
    sims_original = []
    sims_stripped = []
    for q, a in qa_pairs:
        q_emb, a_emb = model.encode([q, a], convert_to_tensor=True)
        sim = float(util.pytorch_cos_sim(q_emb, a_emb)[0][0])
        sims_original.append(sim)

        # 말투 제거 후 의미 기반 유사도
        stripped_q = strip_speech_style(q)
        stripped_a = strip_speech_style(a)
        q_emb2, a_emb2 = model.encode([stripped_q, stripped_a], convert_to_tensor=True)
        sim_clean = float(util.pytorch_cos_sim(q_emb2, a_emb2)[0][0])
        sims_stripped.append(sim_clean)

        print(f"Q: {q}\nA: {a}\n원본 유사도: {round(sim, 4)} / 의미 유사도: {round(sim_clean, 4)}\n")

    avg_orig = round(sum(sims_original) / len(sims_original), 4)
    avg_clean = round(sum(sims_stripped) / len(sims_stripped), 4)
    print(f"👉 평균 유사도: 원본 {avg_orig} / 의미기반 {avg_clean}")

async def main():
    api_key = os.getenv('OPENAI_API_KEY', '')
    generator = SpeechGenerator(api_key=api_key)
    character = get_character_from_input()

    system_prompt = await generator.generate_system_prompt_with_gpt(character)
    print("\n======== 생성된 시스템 프롬프트 ========\n", system_prompt)

    try:
        print(f"======== {character.name} 말투 생성 중 ========")
        selected_message, result = await generator.generate_character_random_tones_sync(character)
        print(f"\n선택된 메시지: {selected_message}")

        # 말투 종류 출력
        print("\n======== 생성된 말투 ========")
        for idx, (tone_name, tone_data_list) in enumerate(result[selected_message].items(), start=1):
            tone = tone_data_list[0]
            hashtags = tone['tone_info'].get('hashtags', '')
            description = tone['tone_info'].get('description', '')
            text = tone['text']

            print(f"\n[{tone_name}] {hashtags}")
            print(f"말투 설명: {description}")
            print(f"예시 응답: {text}")

        # 사용자에게 말투 선택 받기
        user_choice = int(input(f"{character.name} 말투를 정하세요(1,2,3): ").strip())
        selected_tone = f"말투{user_choice}"
        selected_prompt = result[selected_message][selected_tone][0]["system_prompt"]
        print(selected_prompt)
        
        # 경로 수정
        output_dir = Path("vllm/pipeline")
        output_dir.mkdir(parents=True, exist_ok=True)
        output_file = output_dir / "selected_system_prompt.txt"
        
        with open(output_file, "w", encoding="utf-8") as f:
            f.write(selected_prompt)
        print(f"\n[선택한 말투가 {output_file}에 저장되었습니다]")

        # 사용자에게 말투 선택 받은 후 선택된 시스템 프롬프트가 있는 상황에서:
        print(f"\n======== 선택된 시스템 프롬프트로 QA쌍 생성 및 유사도 분석 중 ========")
        await generate_qa_pairs_with_similarity(generator, character, selected_prompt, num_pairs=5)
        
    except Exception as e:
        print(f"오류 발생: {e}")

async def main_script_based_prompt_generation():
    api_key = os.getenv('OPENAI_API_KEY', '')
    generator = SpeechGenerator(api_key=api_key) 

    character = get_character_from_input()

    print("\n캐릭터 대사를 최소 20개 이상 입력하세요. 입력을 마치면 빈 줄(Enter)을 눌러주세요.")
    scripts = []
    while True:
        line = input(f"대사 {len(scripts)+1}: ").strip()
        if line == "":
            break
        scripts.append(line)

    if len(scripts) < 20:
        print("\n대사는 20개 이상 입력해야 합니다.")
        return

    # system prompt 생성
    system_prompt = await generator.generate_system_prompt_from_scripts(character, scripts)
    print("\n======== 생성된 시스템 프롬프트 ========\n")
    print(system_prompt)

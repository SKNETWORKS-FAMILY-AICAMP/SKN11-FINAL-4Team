"""
LangChain 기반 고속 어투 생성 유틸리티
3개 어투를 병렬 처리로 빠르게 생성
"""

import asyncio
from typing import List, Dict, Any, Optional
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser
from langchain_core.runnables import RunnableParallel, RunnableLambda, RunnablePassthrough
from pydantic import BaseModel, Field
import os
import logging
import json

logger = logging.getLogger(__name__)

class ToneResponse(BaseModel):
    """어투 응답 구조"""
    text: str = Field(description="생성된 응답 텍스트")
    description: str = Field(description="말투 설명")
    hashtags: str = Field(description="말투 해시태그")

class LangChainToneGenerator:
    """LangChain 기반 고속 어투 생성기"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Args:
            api_key: OpenAI API 키
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        
        # LangChain ChatOpenAI 초기화
        self.llm = ChatOpenAI(
            api_key=self.api_key,
            model="gpt-4o-mini",
            temperature=0.8,
            max_tokens=500,
            max_retries=2,
            request_timeout=30
        )
        
        # 어투 생성용 프롬프트 템플릿
        self.tone_prompt = ChatPromptTemplate.from_messages([
            ("system", self._get_tone_system_prompt()),
            ("user", self._get_tone_user_prompt())
        ])
        
        # 어투 요약용 프롬프트 템플릿
        self.summary_prompt = ChatPromptTemplate.from_messages([
            ("system", self._get_summary_system_prompt()),
            ("user", "말투 지시사항:\n{system_prompt}")
        ])
        
        # JSON 파서
        self.json_parser = JsonOutputParser(pydantic_object=ToneResponse)
        
        # 개별 어투 생성 체인 (각 어투별)
        self.tone_chain = self.tone_prompt | self.llm
        
        # 어투 요약 체인
        self.summary_chain = self.summary_prompt | self.llm | self.json_parser
        
        # 🚀 진짜 LangChain 병렬 처리 체인 - RunnableParallel 사용
        self.parallel_tone_chain = RunnableParallel(
            tone1=self._create_tone_chain(1),
            tone2=self._create_tone_chain(2), 
            tone3=self._create_tone_chain(3)
        )
        
        logger.info("✅ LangChain Tone Generator 초기화 완료")

    def _create_tone_chain(self, tone_num: int):
        """개별 어투 생성 체인 생성"""
        
        def add_tone_instruction(data):
            """어투별 지시사항 추가"""
            tone_instructions = self._get_tone_instructions()
            data["tone_instruction"] = tone_instructions[tone_num]
            data["tone_num"] = tone_num
            return data
        
        def format_response(llm_output):
            """LLM 출력을 최종 형태로 변환"""
            return {
                "text": llm_output.content.strip(),
                "tone_num": tone_num,
                "raw_content": llm_output.content
            }
        
        # 체인 구성: 입력 → 어투 지시사항 추가 → 프롬프트 → LLM → 포맷팅
        return (
            RunnableLambda(add_tone_instruction) 
            | self.tone_prompt 
            | self.llm 
            | RunnableLambda(format_response)
        )

    def _get_tone_system_prompt(self) -> str:
        """어투 생성용 시스템 프롬프트"""
        return """당신은 이제 '{character_name}'라는 캐릭터처럼 대화해야 합니다.

[캐릭터 정보]
- 이름: {character_name}
- 설명: {character_description}
- 성격: {character_personality}
- MBTI: {character_mbti}
- 연령대: {character_age}
- 성별: {character_gender}

[말투 지시사항]
{tone_instruction}

[주의사항]
- 캐릭터의 성격과 말투를 일관성 있게 유지하세요
- 자연스럽고 매력적인 대화를 하세요
- 주어진 질문에 캐릭터답게 답변하세요
- 말투의 특징을 잘 드러내세요"""

    def _get_tone_user_prompt(self) -> str:
        """어투 생성용 사용자 프롬프트"""
        return "{question}"

    def _get_summary_system_prompt(self) -> str:
        """어투 요약용 시스템 프롬프트"""
        return """주어진 말투의 system prompt를 기반으로 그 말투의 특징을 요약해주세요. 반드시 아래 형식을 그대로 지켜서 JSON으로 출력하세요.

형식:
{{
    "hashtags": "#키워드1 #키워드2 #키워드3",
    "description": "말투 설명 (한 문장, '~말투'로 끝나야 함)"
}}

조건:
1. 말투 스타일을 MZ 느낌나게 키워드 3개를 생성해 해시태그 형식으로 작성해 주세요.
2. 말투 스타일을 한 문장으로 요약해주세요. 반드시 '말투'로 끝나야 합니다. 서술어 없이 명사형으로 끝납니다.
3. 출력 형식은 반드시 JSON 형식으로 반환해주세요. (추가 설명 없이)"""

    def _get_tone_instructions(self) -> Dict[int, str]:
        """어투별 지시사항"""
        return {
            1: "주어진 캐릭터 정보를 바탕으로 첫 번째 독특하고 창의적인 말투로 답변하세요. 캐릭터의 특성을 반영하되 예상치 못한 방식으로 표현해주세요.",
            2: "주어진 캐릭터 정보를 바탕으로 두 번째 독특하고 창의적인 말투로 답변하세요. 첫 번째와는 완전히 다른 새로운 스타일로 표현해주세요.",
            3: "주어진 캐릭터 정보를 바탕으로 세 번째 독특하고 창의적인 말투로 답변하세요. 앞의 두 가지와는 전혀 다른 참신한 방식으로 표현해주세요."
        }

    async def generate_3_tones_parallel(
        self,
        character_data: Dict[str, Any],
        question: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        🚀 진짜 LangChain 체인 기반 3개 어투 병렬 생성
        RunnableParallel을 사용한 최적화된 병렬 처리
        
        Args:
            character_data: 캐릭터 정보
            question: 질문
            
        Returns:
            어투별 응답 딕셔너리
        """
        logger.info(f"🚀 LangChain 체인 기반 3개 어투 병렬 생성 시작: {character_data.get('name', '캐릭터')}")
        
        # 공통 입력 데이터 준비
        base_input = {
            "character_name": character_data.get("name", "캐릭터"),
            "character_description": character_data.get("description", ""),
            "character_personality": character_data.get("personality", "친근한 성격"),
            "character_mbti": character_data.get("mbti", "ENFP"),
            "character_age": character_data.get("age_range", "20-30대"),
            "character_gender": character_data.get("gender", "없음"),
            "question": question
        }
        
        try:
            # 🚀 진짜 LangChain RunnableParallel 체인 실행
            # 한 번의 체인 호출로 3개 어투 동시 생성
            start_time = asyncio.get_event_loop().time()
            
            parallel_results = await self.parallel_tone_chain.ainvoke(base_input)
            
            end_time = asyncio.get_event_loop().time()
            generation_time = end_time - start_time
            
            logger.info(f"✅ LangChain 체인 병렬 생성 완료: {generation_time:.2f}초")
            
            # 🔄 병렬로 어투 요약도 생성 (배치 처리)
            summary_tasks = []
            for tone_key, tone_result in parallel_results.items():
                tone_num = tone_result["tone_num"]
                
                # 시스템 프롬프트 생성
                tone_instructions = self._get_tone_instructions()
                system_prompt_input = {**base_input, "tone_instruction": tone_instructions[tone_num]}
                system_prompt = self._get_tone_system_prompt().format(**system_prompt_input)
                
                # 요약 생성 작업 추가
                summary_tasks.append(
                    self.summary_chain.ainvoke({"system_prompt": system_prompt})
                )
            
            # 🚀 어투 요약도 병렬 처리
            summary_results = await asyncio.gather(*summary_tasks, return_exceptions=True)
            
            # 📦 최종 결과 조립
            responses = {}
            tone_keys = ["tone1", "tone2", "tone3"]
            
            for i, (tone_key, tone_result) in enumerate(parallel_results.items()):
                tone_name = f"말투{i+1}"
                tone_num = tone_result["tone_num"]
                
                # 요약 결과 처리
                summary_result = summary_results[i] if i < len(summary_results) else {}
                if isinstance(summary_result, Exception):
                    logger.warning(f"⚠️ 말투 {tone_num} 요약 생성 실패: {summary_result}")
                    summary_result = {}
                
                # 시스템 프롬프트 재생성
                tone_instructions = self._get_tone_instructions()
                system_prompt_input = {**base_input, "tone_instruction": tone_instructions[tone_num]}
                system_prompt = self._get_tone_system_prompt().format(**system_prompt_input)
                
                responses[tone_name] = [{
                    "text": tone_result["text"],
                    "tone_info": {
                        "variation": tone_num,
                        "description": summary_result.get("description", f"LangChain 체인으로 생성된 말투 {tone_num}"),
                        "hashtags": summary_result.get("hashtags", f"#LangChain #말투{tone_num} #병렬처리")
                    },
                    "character_info": {
                        "name": character_data.get("name", "캐릭터"),
                        "mbti": character_data.get("mbti", "ENFP"),
                        "age_range": character_data.get("age_range", "20-30대"),
                        "gender": character_data.get("gender", "없음")
                    },
                    "system_prompt": system_prompt
                }]
            
            logger.info(f"✅ LangChain 체인 기반 3개 어투 + 요약 생성 완료!")
            return responses
            
        except Exception as e:
            logger.error(f"❌ LangChain 체인 병렬 생성 실패: {e}")
            
            # 🔄 실패 시 폴백 응답
            responses = {}
            for i in range(1, 4):
                tone_name = f"말투{i}"
                responses[tone_name] = [{
                    "text": f"죄송합니다. LangChain 체인 처리 중 오류가 발생했습니다. (말투 {i})",
                    "tone_info": {
                        "variation": i,
                        "description": "체인 처리 실패한 말투",
                        "hashtags": f"#오류 #LangChain #말투{i}"
                    },
                    "character_info": {
                        "name": character_data.get("name", "캐릭터"),
                        "mbti": character_data.get("mbti", "ENFP"),
                        "age_range": character_data.get("age_range", "20-30대"),
                        "gender": character_data.get("gender", "없음")
                    },
                    "system_prompt": "오류로 인한 기본 시스템 프롬프트"
                }]
            
            return responses


# 전역 인스턴스
_langchain_tone_generator = None

def get_langchain_tone_generator(**kwargs) -> LangChainToneGenerator:
    """전역 LangChain Tone Generator 인스턴스 반환"""
    global _langchain_tone_generator
    
    if _langchain_tone_generator is None:
        _langchain_tone_generator = LangChainToneGenerator(**kwargs)
    
    return _langchain_tone_generator
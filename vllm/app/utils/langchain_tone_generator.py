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
            max_tokens=2000,  # 3개 어투 생성을 위해 토큰 증가
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
        
        logger.info("✅ LangChain Tone Generator 초기화 완료")
    
    def _parse_summary_response(self, response) -> Dict[str, str]:
        """LLM 응답에서 요약 정보를 파싱"""
        try:
            # response가 AIMessage인 경우 content 추출
            if hasattr(response, 'content'):
                content = response.content.strip()
            else:
                content = str(response).strip()
            
            # JSON 파싱 시도
            # JSON 블록이 있는 경우 추출
            import re
            json_match = re.search(r'\{[\s\S]*?\}', content)
            if json_match:
                json_str = json_match.group()
                result = json.loads(json_str)
                
                # 유효성 검증
                if isinstance(result, dict) and result.get("hashtags") and result.get("description"):
                    logger.debug(f"요약 파싱 성공: {result}")
                    return result
            
            # JSON 파싱 실패 시 텍스트에서 추출
            logger.warning(f"JSON 파싱 실패, 텍스트 분석 시도: {content}")
            
            # 해시태그 추출
            hashtags = re.findall(r'#\w+', content)
            if hashtags:
                hashtag_str = " ".join(hashtags[:3])
            else:
                hashtag_str = "#개성있는 #창의적인 #캐릭터"
            
            # 설명 추출 (마지막 문장 또는 전체)
            sentences = content.split('.')
            description = sentences[-2].strip() + "." if len(sentences) > 1 else "독특하고 개성있는 말투"
            
            return {
                "hashtags": hashtag_str,
                "description": description
            }
            
        except Exception as e:
            logger.error(f"요약 파싱 중 오류: {e}")
            return {
                "hashtags": "#LangChain #AI #캐릭터",
                "description": "AI가 생성한 독특한 말투"
            }
    
    def _create_optimized_parallel_chain(self, system_prompts: List[str]):
        """최적화된 병렬 처리 체인 생성 - 한 번의 실행으로 모든 처리 완료"""
        
        # 3개 어투를 완전 병렬로 처리하는 최상위 체인
        return RunnableParallel(
            말투1=self._create_complete_tone_chain(1, system_prompts[0]),
            말투2=self._create_complete_tone_chain(2, system_prompts[1]),
            말투3=self._create_complete_tone_chain(3, system_prompts[2])
        )
    
    def _create_complete_tone_chain(self, tone_num: int, system_prompt: str):
        """단일 어투에 대한 완전한 처리 체인 (응답 + 요약)"""
        
        # 시스템 프롬프트 생성을 위한 전처리
        def prepare_prompt_data(data):
            """프롬프트 데이터 준비"""
            prompt_data = data.copy()
            prompt_data["system_prompt"] = system_prompt
            return prompt_data
        
        # 메시지 생성
        def create_messages(data):
            """LLM용 메시지 생성"""
            return [
                {"role": "system", "content": data["system_prompt"]},
                {"role": "user", "content": data["question"]}
            ]
        
        # 응답 텍스트 추출
        def extract_text(response):
            """LLM 응답에서 텍스트 추출"""
            if hasattr(response, 'content'):
                return response.content.strip()
            return str(response).strip()
        
        # 요약 입력 준비
        def prepare_summary_input(data):
            """요약 체인을 위한 입력 준비"""
            return {"system_prompt": data["system_prompt"]}
        
        # 최종 결과 포맷
        def format_final_result(data):
            """최종 결과를 speech_generator 형식으로 포맷"""
            response_text = data.get("response", f"응답 생성 실패 (말투 {tone_num})")
            summary_data = data.get("summary", {})
            
            # 디버깅을 위한 로깅
            if not isinstance(summary_data, dict) or not summary_data.get("hashtags"):
                logger.warning(f"말투{tone_num} 요약 데이터 문제: {summary_data}")
            
            return [{
                "text": response_text,
                "hashtags": summary_data.get("hashtags", f"#말투{tone_num} #캐릭터 #LangChain"),
                "description": summary_data.get("description", f"LangChain으로 생성된 말투{tone_num}")
            }]
        
        # 완전한 체인 구성: 한 번의 흐름으로 모든 처리
        return (
            # 1. 프롬프트 데이터 준비
            RunnableLambda(prepare_prompt_data)
            # 2. 응답과 요약을 병렬로 처리
            | RunnableParallel(
                # 응답 생성 브랜치
                response=(
                    RunnableLambda(create_messages)
                    | self.llm
                    | RunnableLambda(extract_text)
                ),
                # 요약 생성 브랜치 (더 안정적인 처리)
                summary=(
                    RunnableLambda(prepare_summary_input)
                    | self.summary_prompt
                    | self.llm
                    | RunnableLambda(self._parse_summary_response)
                )
            )
            # 4. 최종 포맷팅
            | RunnableLambda(format_final_result)
        )

    def _create_tone_chain(self, tone_num: int):
        """개별 어투 생성 체인 생성 - 응답과 요약을 하나의 체인으로 처리"""
        
        def add_tone_instruction(data):
            """어투별 지시사항 추가"""
            tone_instructions = self._get_tone_instructions()
            data["tone_instruction"] = tone_instructions[tone_num]
            data["tone_num"] = tone_num
            return data
        
        # 응답 생성과 요약을 병렬로 처리하는 체인
        def create_complete_tone_chain():
            # 시스템 프롬프트 생성 함수
            def generate_system_prompt(data):
                """완전한 시스템 프롬프트 생성"""
                return self._get_tone_system_prompt().format(**data)
            
            # 응답 생성 체인
            response_chain = (
                RunnablePassthrough.assign(
                    system_prompt=RunnableLambda(generate_system_prompt)
                )
                | RunnableLambda(lambda x: [
                    {"role": "system", "content": x["system_prompt"]},
                    {"role": "user", "content": x["question"]}
                ])
                | self.llm
                | RunnableLambda(lambda x: x.content.strip())
            )
            
            # 요약 생성 체인
            summary_chain = (
                RunnablePassthrough.assign(
                    system_prompt=RunnableLambda(generate_system_prompt)
                )
                | RunnableLambda(lambda x: {
                    "system_prompt": x["system_prompt"]
                })
                | self.summary_chain
            )
            
            # 응답과 요약을 병렬로 실행하고 결과를 합치는 체인
            combined_chain = (
                RunnableParallel(
                    response=response_chain,
                    summary=summary_chain
                )
                | RunnableLambda(lambda x: {
                    "text": x["response"],
                    "hashtags": x["summary"].get("hashtags", f"#말투{tone_num} #캐릭터 #창의적"),
                    "description": x["summary"].get("description", f"독특하고 창의적인 말투{tone_num}"),
                    "tone_num": tone_num
                })
            )
            
            return combined_chain
        
        # 최종 체인: 입력 → 어투 지시사항 추가 → 응답+요약 병렬 처리
        return (
            RunnableLambda(add_tone_instruction)
            | create_complete_tone_chain()
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
            {
                "hashtags": "#키워드1 #키워드2 #키워드3",
                "description": "말투 설명 (한 문장, '~말투'로 끝나야 함)"
            }

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
    
    def _get_single_request_system_prompt(self) -> str:
        """단일 요청으로 3가지 어투를 생성하는 시스템 프롬프트"""
        return """당신은 주어진 캐릭터의 3가지 서로 다른 말투 스타일을 생성하는 전문가입니다.

[캐릭터 정보]
- 이름: {character_name}
- 설명: {character_description}
- 성격: {character_personality}
- MBTI: {character_mbti}
- 연령대: {character_age}
- 성별: {character_gender}

[과제]
주어진 질문에 대해 같은 캐릭터가 3가지 완전히 다른 말투로 답변하는 것을 생성하세요.
각 말투는 서로 구별되는 독특한 특징을 가져야 합니다.

다음 JSON 형식으로 정확히 출력하세요:
{
    "말투1": {
        "text": "첫 번째 말투로 작성한 답변",
        "hashtags": "#특징1 #특징2 #특징3",
        "description": "이 말투의 특징을 설명하는 한 문장 (반드시 '말투'로 끝남)"
    },
    "말투2": {
        "text": "두 번째 말투로 작성한 답변 (첫 번째와 완전히 다른 스타일)",
        "hashtags": "#특징4 #특징5 #특징6",
        "description": "이 말투의 특징을 설명하는 한 문장 (반드시 '말투'로 끝남)"
    },
    "말투3": {
        "text": "세 번째 말투로 작성한 답변 (앞의 두 개와 완전히 다른 스타일)",
        "hashtags": "#특징7 #특징8 #특징9",
        "description": "이 말투의 특징을 설명하는 한 문장 (반드시 '말투'로 끝남)"
    }
}

[중요 지침]
1. 세 가지 말투는 서로 명확히 구별되어야 합니다.
2. 각 말투는 캐릭터의 기본 성격을 유지하되, 표현 방식이 달라야 합니다.
3. 해시태그는 각 말투의 특징을 MZ 감성으로 표현해주세요.
4. 반드시 위의 JSON 형식을 정확히 따라주세요."""

    async def generate_3_tones_single_request(
        self,
        character_data: Dict[str, Any],
        question: str,
        system_prompts: List[str]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        🚀 단일 요청으로 3가지 다른 어투 생성
        한 번의 LLM 호출로 서로 다른 3가지 어투를 생성하여 차별화 보장
        
        Args:
            character_data: 캐릭터 정보
            question: 질문
            system_prompts: 시스템 프롬프트 리스트
            
        Returns:
            어투별 응답 딕셔너리
        """
        logger.info(f"🎯 단일 요청 3개 어투 생성 시작: {character_data.get('name', '캐릭터')}")
        
        # 입력 데이터 준비
        input_data = {
            "character_name": character_data.get("name", "캐릭터"),
            "character_description": character_data.get("description", ""),
            "character_personality": character_data.get("personality", "친근한 성격"),
            "character_mbti": character_data.get("mbti", "ENFP"),
            "character_age": character_data.get("age_range", "20-30대"),
            "character_gender": character_data.get("gender", "없음"),
            "question": question
        }
        
        try:
            # 전달받은 시스템 프롬프트들을 조합한 메시지 생성
            # 템플릿 변수 인식 문제를 해결하기 위해 변수로 전달
            system_prompt_template = """당신은 주어진 3가지 다른 말투 스타일로 응답을 생성하는 전문가입니다.

각각의 말투 스타일은 다음과 같습니다:

[말투1]
{prompt1}

[말투2]
{prompt2}

[말투3]
{prompt3}

주어진 질문에 대해 위 3가지 말투로 각각 답변하세요. 각 답변은 2-3문장으로 간결하게 작성하세요.
다음 JSON 형식으로 정확히 출력하고, JSON 외에 다른 텍스트는 포함하지 마세요:
{json_format}"""
            
            # JSON 형식 예시
            json_format_escaped = """{
    "말투1": {
        "text": "첫 번째 말투로 작성한 답변",
        "hashtags": "#특징1 #특징2 #특징3",
        "description": "이 말투의 특징을 설명하는 한 문장 (반드시 '말투'로 끝남)"
    },
    "말투2": {
        "text": "두 번째 말투로 작성한 답변",
        "hashtags": "#특징4 #특징5 #특징6",
        "description": "이 말투의 특징을 설명하는 한 문장 (반드시 '말투'로 끝남)"
    },
    "말투3": {
        "text": "세 번째 말투로 작성한 답변",
        "hashtags": "#특징7 #특징8 #특징9",
        "description": "이 말투의 특징을 설명하는 한 문장 (반드시 '말투'로 끝남)"
    }
}"""
            
            # 단일 프롬프트로 3가지 어투 생성
            single_prompt = ChatPromptTemplate.from_messages([
                ("system", system_prompt_template),
                ("user", "{question}")
            ])
            
            # LLM 호출
            chain = single_prompt | self.llm
            start_time = asyncio.get_event_loop().time()
            
            response = await chain.ainvoke({
                "prompt1": system_prompts[0],
                "prompt2": system_prompts[1],
                "prompt3": system_prompts[2],
                "json_format": json_format_escaped,
                "question": question
            })
            
            # 응답 파싱
            content = response.content.strip() if hasattr(response, 'content') else str(response).strip()
            
            # JSON 파싱
            import re
            json_match = re.search(r'\{[\s\S]*\}', content)
            if json_match:
                json_str = json_match.group()
                # JSON 문자열 정리 (일반적인 문제 해결)
                json_str = json_str.replace('\n\n', '\n')  # 이중 줄바꿈 제거
                json_str = re.sub(r',\s*}', '}', json_str)  # 마지막 쉼표 제거
                json_str = re.sub(r',\s*]', ']', json_str)  # 배열 마지막 쉼표 제거
                
                # 불완전한 JSON 감지 및 수정 시도
                open_braces = json_str.count('{')
                close_braces = json_str.count('}')
                if open_braces > close_braces:
                    # 닫는 중괄호 추가
                    json_str += '"' if json_str.rstrip()[-1] not in '"' else ''
                    json_str += '}' * (open_braces - close_braces)
                    logger.warning(f"불완전한 JSON 감지. 닫는 중괄호 {open_braces - close_braces}개 추가")
                
                try:
                    result = json.loads(json_str)
                except json.JSONDecodeError as e:
                    logger.error(f"JSON 파싱 오류: {e}")
                    logger.error(f"원본 응답 길이: {len(content)}자")
                    logger.error(f"원본 응답: {content[:1000]}...")  # 더 많은 로그
                    logger.error(f"정리된 JSON 길이: {len(json_str)}자")
                    logger.error(f"정리된 JSON: {json_str[:1000]}...")
                    raise
                
                # 결과 포맷팅
                responses = {}
                for i, (tone_key, tone_data) in enumerate(result.items()):
                    responses[tone_key] = [{
                        "system_prompt": system_prompts[i] if i < len(system_prompts) else f"말투{i+1} 시스템 프롬프트",
                        "text": tone_data.get("text", ""),
                        "hashtags": tone_data.get("hashtags", f"#{tone_key}"),
                        "description": tone_data.get("description", f"{tone_key} 스타일의 말투")
                    }]
                
                generation_time = asyncio.get_event_loop().time() - start_time
                logger.info(f"✅ 단일 요청 3개 어투 생성 완료: {generation_time:.2f}초")
                
                return responses
                
            else:
                raise Exception("JSON 응답을 파싱할 수 없습니다.")
                
        except Exception as e:
            logger.error(f"❌ 단일 요청 어투 생성 실패: {e}")
            # 폴백: 기존 병렬 방식 사용
            return await self.generate_3_tones_parallel(character_data, question, system_prompts)

    async def generate_3_tones_parallel(
        self,
        character_data: Dict[str, Any],
        question: str,
        system_prompts: List[str]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        🚀 최적화된 LangChain 체인 기반 3개 어투 병렬 생성
        단일 체인 실행으로 응답과 요약을 동시에 처리
        
        Args:
            character_data: 캐릭터 정보
            question: 질문
            
        Returns:
            어투별 응답 딕셔너리
        """
        logger.info(f"🚀 최적화된 LangChain 체인 3개 어투 병렬 생성 시작: {character_data.get('name', '캐릭터')}")
        
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
            # 🚀 최적화된 단일 체인 실행 - 응답과 요약을 한번에!
            start_time = asyncio.get_event_loop().time()
            
            # 시스템 프롬프트와 함께 최적화된 병렬 체인 생성
            optimized_chain = self._create_optimized_parallel_chain(system_prompts)
            
            # 병렬 체인 실행 (각 체인이 응답과 요약을 동시에 처리)
            parallel_results = await optimized_chain.ainvoke(base_input)
            
            end_time = asyncio.get_event_loop().time()
            generation_time = end_time - start_time
            
            logger.info(f"✅ 최적화된 체인 병렬 생성 완료: {generation_time:.2f}초")
            
            # 📦 결과는 이미 올바른 형식으로 반환됨 (최적화된 체인에서 처리)
            responses = parallel_results
            
            logger.info(f"✅ 최적화된 LangChain 체인 3개 어투 생성 완료!")
            return responses
            
        except Exception as e:
            logger.error(f"❌ LangChain 체인 병렬 생성 실패: {e}")
            
            # 🔄 실패 시 폴백 응답
            responses = {}
            for i in range(1, 4):
                tone_name = f"말투{i}"
                responses[tone_name] = [{
                    "text": f"죄송합니다. LangChain 체인 처리 중 오류가 발생했습니다. (말투 {i})",
                    "hashtags": f"#오류 #LangChain #말투{i}",
                    "description": "체인 처리 실패한 말투"
                }]
            
            return responses
    
    async def _generate_single_tone_with_summary(
        self,
        character_data: Dict[str, Any],
        question: str,
        system_prompt: str,
        tone_num: int
    ) -> Dict[str, Any]:
        """
        단일 어투에 대한 응답과 요약을 생성합니다.
        speech_generator의 출력 형식과 동일하게 반환합니다.
        
        Args:
            character_data: 캐릭터 정보
            question: 질문
            system_prompt: 시스템 프롬프트  
            tone_num: 어투 번호 (1, 2, 3)
            
        Returns:
            speech_generator와 동일한 형식의 응답 딕셔너리
        """
        try:
            # 캐릭터 정보를 시스템 프롬프트에 반영
            formatted_prompt = system_prompt
            
            # LLM으로 응답 생성
            messages = [
                {"role": "system", "content": formatted_prompt},
                {"role": "user", "content": question}
            ]
            
            # ChatOpenAI를 사용한 응답 생성
            llm_response = await self.llm.ainvoke(messages)
            
            # response.content에서 텍스트 추출
            if hasattr(llm_response, 'content'):
                generated_text = llm_response.content.strip()
            else:
                generated_text = str(llm_response).strip()
            
            # 어투 요약 생성
            try:
                summary_response = await self.summary_chain.ainvoke({"system_prompt": formatted_prompt})
                
                # speech_generator와 동일한 형식으로 반환
                return {
                    "text": generated_text,
                    "hashtags": summary_response.get("hashtags", f"#말투{tone_num} #캐릭터 #LangChain"),
                    "description": summary_response.get("description", f"LangChain으로 생성된 말투{tone_num}")
                }
            except Exception as summary_error:
                logger.warning(f"어투 요약 생성 실패 (말투 {tone_num}): {summary_error}")
                # 요약 실패 시 기본값 반환
                return {
                    "text": generated_text,
                    "hashtags": f"#말투{tone_num} #캐릭터 #LangChain",
                    "description": f"LangChain으로 생성된 말투{tone_num}"
                }
            
        except Exception as e:
            logger.error(f"단일 어투 생성 실패 (말투 {tone_num}): {e}")
            raise e


# 전역 인스턴스
_langchain_tone_generator = None

def get_langchain_tone_generator(**kwargs) -> LangChainToneGenerator:
    """전역 LangChain Tone Generator 인스턴스 반환"""
    global _langchain_tone_generator
    
    if _langchain_tone_generator is None:
        _langchain_tone_generator = LangChainToneGenerator(**kwargs)
    
    return _langchain_tone_generator
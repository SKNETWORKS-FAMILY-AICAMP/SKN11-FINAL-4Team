"""
지능적인 도구 선택을 사용한 MCP 챗봇 구현
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from fastapi import APIRouter, HTTPException, status, Depends, Body
from pydantic import BaseModel
import os
import asyncio
import math
import re
from datetime import datetime
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.security import get_current_user

# 로깅 설정
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter()


class MCPToolProcessor:
    """MCP 도구 처리 클래스"""

    def __init__(self):
        self.mcp_client_service = None
        self.vllm_client = None

    async def initialize(self):
        """초기화"""
        try:
            from app.services.mcp_client import mcp_client_service
            from app.services.vllm_client import get_vllm_client

            self.mcp_client_service = mcp_client_service
            self.vllm_client = await get_vllm_client()
            logger.info("MCP 도구 처리기 초기화 완료")
        except Exception as e:
            logger.error(f"MCP 도구 처리기 초기화 실패: {e}")

    async def should_use_mcp_tools(self, message: str) -> bool:
        """메시지가 MCP 도구 사용이 필요한지 확인"""
        try:
            logger.info("🔍 MCP 도구 사용 여부 판단 시작:")
            logger.info(f"  - 사용자 메시지: {message}")

            if not self.vllm_client:
                logger.info("🔧 VLLM 클라이언트 초기화 중...")
                await self.initialize()

            # VLLM을 사용한 지능적 판단
            prompt = f"""
다음 사용자 메시지가 수학 계산, 날씨 정보, 파일 처리, 번역, 웹 검색 등의 도구가 필요한지 판단해주세요.

사용자 메시지: {message}

다음 중 하나라도 해당되면 'YES'를, 그렇지 않으면 'NO'를 답변해주세요:
- 수학 계산 (덧셈, 뺄셈, 곱셈, 나눗셈, 제곱, 제곱근, 팩토리얼, 방정식 등)
- 날씨 정보 (현재 날씨, 예보, 대기질, 자외선 지수 등) - "날씨", "기온", "예보" 등의 키워드가 포함된 경우
- 웹 검색 (최신 정보, 뉴스, 검색, 찾기 등) - "검색", "찾아줘", "알려줘", "뉴스" 등의 키워드가 포함된 경우
- 파일 처리 (파일 읽기, 쓰기, 변환 등)
- 번역 (언어 간 번역)
- 기타 도구가 필요한 작업

주의: 날씨 관련 키워드가 포함된 경우는 항상 도구를 사용하세요.
예시: "서울 날씨", "날씨 알려줘", "기온은?", "예보" 등

답변 (YES/NO만):
"""

            logger.info("🧠 VLLM을 사용한 도구 사용 여부 분석 중...")
            result = await self.vllm_client.generate_response(
                user_message=prompt,
                system_message="당신은 도구 사용 여부를 판단하는 AI입니다. YES 또는 NO로만 답변하세요.",
                influencer_name="도구판단AI",
                max_new_tokens=10,
                temperature=0.1,
            )

            response_text = result.get("response", "").strip().upper()
            should_use = "YES" in response_text

            logger.info(f"📊 도구 사용 여부 판단 결과:")
            logger.info(f"  - VLLM 응답: {response_text}")
            logger.info(f"  - 도구 사용 여부: {should_use}")
            logger.info("🔍 MCP 도구 사용 여부 판단 완료")

            return should_use

        except Exception as e:
            logger.error(f"❌ 도구 사용 여부 판단 실패: {e}")
            return False

    def extract_korean(self, text: str) -> str:
        """텍스트에서 한글이 포함된 문장만 추출"""
        # 한글이 포함된 문장만 추출 (마침표, 물음표, 느낌표, 줄바꿈 기준)
        sentences = re.findall(r"([가-힣][^.!?\n]*[.!?\n])", text)
        return " ".join(sentences).strip() if sentences else None

    def _convert_search_result_to_natural_language(
        self, search_result: dict, original_query: str
    ) -> str:
        logger.info(
            f"[한국어 추출] _convert_search_result_to_natural_language 호출됨: query={original_query}"
        )
        try:
            results = search_result.get("results", [])
            if not results:
                logger.info(f"[한국어 추출] 결과 없음: {original_query}")
                return f"'{original_query}'에 대한 검색 결과를 찾을 수 없습니다."
            korean_texts = []
            for result in results:
                text = result.get("text", "")
                korean = self.extract_korean(text)
                if korean:
                    logger.info(
                        f"[한국어 추출] 결과에서 한국어 문장 발견: {korean[:100]}..."
                    )
                    korean_texts.append(korean)
            if korean_texts:
                combined = " ".join(korean_texts)
                max_len = 700
                if len(combined) > max_len:
                    combined = combined[:max_len] + "..."
                logger.info(
                    f"[한국어 추출] 최종 합쳐진 한국어 텍스트: {combined[:100]}..."
                )
                return combined
            logger.info(f"[한국어 추출] 한국어 결과 없음: {original_query}")
            return f"'{original_query}'에 대한 한국어 결과를 찾을 수 없습니다."
        except Exception as e:
            logger.error(f"검색 결과 변환 중 오류: {e}")
            return f"'{original_query}'에 대한 검색 결과를 처리하는 중 오류가 발생했습니다."

    async def process_with_mcp_tools(
        self, message: str, selected_servers: List[str] = None
    ) -> Tuple[Optional[str], List[str]]:
        """MCP 도구를 사용하여 메시지 처리 (도구 결과를 LLM에 다시 넣어 자연스러운 답변 생성)"""
        try:
            logger.info("=" * 50)
            logger.info("🚀 MCPToolProcessor 도구 처리 시작")
            logger.info(f"📝 사용자 메시지: {message}")
            logger.info("=" * 50)

            if not self.mcp_client_service or not self.vllm_client:
                logger.info("🔧 MCPToolProcessor 초기화 중...")
                await self.initialize()

            # 1단계: 도구 사용 필요 여부 판단
            should_use_tool = await self.should_use_mcp_tools(message)
            logger.info(f"🔍 도구 사용 필요 여부: {should_use_tool}")
            if not should_use_tool:
                logger.info("❌ 도구 사용 불필요. 일반 대화로 전환.")
                return None, []

            # 사용 가능한 모든 MCP 서버의 도구들 가져오기
            all_tools = []

            # MCP 서버 매니저에서 사용 가능한 서버 목록 가져오기
            from app.services.mcp_server_manager import mcp_server_manager

            server_status = mcp_server_manager.get_server_status()

            # 선택된 서버가 있으면 해당 서버만 사용, 없으면 모든 실행 중인 서버 사용
            if selected_servers:
                available_servers = [
                    name
                    for name in selected_servers
                    if name in server_status
                    and server_status[name].get("running", False)
                ]
                logger.info(f"📋 선택된 MCP 서버만 사용: {available_servers}")
            else:
                available_servers = [
                    name
                    for name, status in server_status.items()
                    if status.get("running", False)
                ]
                logger.info(f"📋 모든 실행 중인 MCP 서버 사용: {available_servers}")

            # 동적으로 사용 가능한 서버 목록 사용
            for server_name in available_servers:
                try:
                    logger.info(f"📥 MCP 서버 '{server_name}'에서 도구 로드 시작...")

                    # MCP 클라이언트 서비스 초기화 확인
                    if not self.mcp_client_service.mcp_client:
                        logger.info(f"🔄 MCP 클라이언트 '{server_name}' 초기화 중...")
                        await self.mcp_client_service.initialize_mcp_client()

                    # 캐시된 도구 목록 사용
                    tools = await self.mcp_client_service.get_cached_tools(server_name)
                    logger.info(
                        f"✅ MCP 서버 '{server_name}'에서 {len(tools)}개 도구 로드 완료 (캐시 사용)"
                    )

                    # 도구 상세 정보 로깅
                    for i, tool in enumerate(tools):
                        if isinstance(tool, dict):
                            tool_name = tool.get("name", "Unknown")
                            tool_desc = tool.get("description", "No description")
                        else:
                            tool_name = getattr(tool, "name", "Unknown")
                            tool_desc = getattr(tool, "description", "No description")
                        logger.info(f"  - 도구 {i+1}: {tool_name} - {tool_desc}")

                    all_tools.extend(tools)
                except Exception as e:
                    logger.warning(f"❌ MCP 서버 '{server_name}' 도구 로드 실패: {e}")
                    import traceback

                    logger.warning(f"  - 상세 오류: {traceback.format_exc()}")

            if not all_tools:
                logger.info(
                    "❌ 사용 가능한 MCP 도구가 없습니다. 일반 대화로 진행합니다."
                )
                logger.info("=" * 50)
                return None, []  # MCP 사용하지 않고 일반 대화로 전환

            logger.info(f"🎯 총 {len(all_tools)}개의 MCP 도구 사용 가능")

            # 도구 목록을 문자열로 변환 (딕셔너리 형태 처리)
            tools_description_parts = []
            for tool in all_tools:
                try:
                    if isinstance(tool, dict):
                        name = tool.get("name", "Unknown")
                        description = tool.get("description", "No description")
                    else:
                        # 객체 형태인 경우 - 다양한 속성 시도
                        name = None
                        description = None

                        # 가능한 속성들 확인
                        for attr in ["name", "tool_name", "function_name"]:
                            if hasattr(tool, attr):
                                name = getattr(tool, attr)
                                break

                        # 설명 속성 확인
                        for attr in ["description", "doc", "help"]:
                            if hasattr(tool, attr):
                                description = getattr(tool, attr)
                                break

                        # 기본값 설정
                        if name is None:
                            name = str(tool.__class__.__name__)
                        if description is None:
                            description = "No description"

                    tools_description_parts.append(f"- {name}: {description}")
                except Exception as e:
                    logger.warning(f"도구 정보 파싱 실패: {e}, 도구: {tool}")
                    tools_description_parts.append(f"- Unknown: No description")

            tools_description = "\n".join(tools_description_parts)
            logger.info(f"📋 사용 가능한 도구 목록:\n{tools_description}")

            # 1단계: 사용자 메시지에서 어떤 도구를 사용할지 판단
            intent_prompt = f"""사용자의 메시지를 분석하여 어떤 도구를 사용해야 하는지 판단해주세요.

사용 가능한 도구들:
{tools_description}

사용자 메시지: {message}

다음 형식으로 답변해주세요:
사용할 도구: [정확한 도구명]
필요한 매개변수: [매개변수1=값1, 매개변수2=값2, ...]

주의사항:
- 도구명은 정확히 위에 나열된 도구명 중 하나를 사용해야 합니다
- 사용 가능한 도구 목록에서 정확한 이름을 선택하세요
- 사용자의 질문에 '날씨', '기온', '미세먼지', '자외선', '강수', '비', '눈', '기상', '온도' 등 날씨 관련 단어와 '오늘', '내일', '주간', '이번 주' 등 시간 표현이 함께 포함된 경우에만 weather 관련 도구(get_current_weather, get_weather_forecast 등)를 사용하세요.
- 그렇지 않으면(날씨 관련 단어가 없으면) 반드시 web_search_exa 도구를 사용하세요.
- 수학 계산(덧셈, 뺄셈, 곱셈, 나눗셈, 제곱, 제곱근, 팩토리얼 등)은 반드시 math 관련 도구(add, subtract, multiply, divide, power, sqrt, factorial 등)를 사용하세요.
- "위키", "위키피디아", "wikipedia"라는 단어가 명확히 포함된 경우에만 wikipedia_search_exa를 사용하세요.
- 그 외의 정보성 질문(뉴스, 인물, 상식, 일반 지식 등)은 반드시 web_search_exa 도구를 사용하세요.
- location 매개변수는 실제 도시명(서울, 부산, 대구 등)만 사용하세요
- 예시나 설명 텍스트는 포함하지 마세요

만약 위의 도구들로 처리할 수 없는 질문이라면 "웹검색 필요"라고 답변하세요.
기존 도구로 처리할 수 있다면 해당 도구를 선택하세요."""

            logger.info("🧠 VLLM을 사용한 도구 사용 의도 분석 시작...")
            intent_result = await self.vllm_client.generate_response(
                user_message=intent_prompt,
                system_message="당신은 도구 사용 의도를 분석하는 AI입니다. 정확한 도구명과 매개변수를 추출해주세요.",
                influencer_name="도구분석AI",
                max_new_tokens=200,
                temperature=0.3,
            )

            intent_text = intent_result.get("response", "")
            logger.info(f"📊 도구 사용 의도 분석 결과: {intent_text}")

            # 2단계: 도구 실행
            tools_used = []
            tool_results = []

            if "도구 불필요" not in intent_text and "웹검색 필요" not in intent_text:
                # 도구명과 매개변수 추출
                tool_name = None
                parameters = {}

                # 간단한 파싱 (실제로는 더 정교한 파싱이 필요)
                if "사용할 도구:" in intent_text:
                    tool_line = (
                        intent_text.split("사용할 도구:")[1].split("\n")[0].strip()
                    )
                    tool_name = tool_line.strip()
                    logger.info(f"🔧 선택된 도구: {tool_name}")

                if "필요한 매개변수:" in intent_text:
                    params_line = (
                        intent_text.split("필요한 매개변수:")[1].split("\n")[0].strip()
                    )
                    # 매개변수 파싱
                    params_parts = params_line.split(",")
                    for part in params_parts:
                        if "=" in part:
                            key, value = part.split("=", 1)
                            parameters[key.strip()] = value.strip()

                    # 날씨 관련 도구일 때만 location 매개변수 처리
                    weather_tools = [
                        "get_current_weather",
                        "get_weather_forecast",
                        "get_air_quality",
                        "get_uv_index",
                    ]
                    if tool_name in weather_tools:
                        if "location" not in parameters:
                            # 메시지에서 도시명 추출 시도
                            import re

                            city_pattern = r"(서울|부산|대구|인천|광주|대전|울산|세종|수원|성남|안양|안산|고양|용인|부천|춘천|강릉|청주|전주|광주|대전|울산|포항|창원|진주|여수|순천|목포|군산|익산|전주|정읍|나주|광양|동해|태백|속초|삼척|원주|충주|제천|보은|옥천|영동|증평|진천|괴산|음성|단양|천안|공주|보령|아산|서산|논산|계룡|당진|금산|부여|서천|청양|홍성|예산|태안)"
                            city_match = re.search(city_pattern, message)
                            if city_match:
                                parameters["location"] = city_match.group(1)
                            else:
                                # 도시명이 없으면 도시명을 물어보는 응답 반환
                                return (
                                    "어느 도시의 날씨를 알고 싶으신가요? (예: 서울, 부산, 대구, 인천, 광주, 대전, 울산, 세종, 수원, 성남, 안양, 안산, 고양, 용인, 부천, 춘천, 강릉, 청주, 전주, 포항, 창원, 진주, 여수, 순천, 목포, 군산, 익산, 정읍, 나주, 광양, 동해, 태백, 속초, 삼척, 원주, 충주, 제천, 보은, 옥천, 영동, 증평, 진천, 괴산, 음성, 단양, 천안, 공주, 보령, 아산, 서산, 논산, 계룡, 당진, 금산, 부여, 서천, 청양, 홍성, 예산, 태안)",
                                    [],
                                )
                        else:
                            # LLM이 추출한 location 값이 이상한 경우 처리
                            location_value = parameters["location"]
                            if (
                                "[" in location_value
                                or "]" in location_value
                                or "예시" in location_value
                            ):
                                # 메시지에서 도시명 다시 추출
                                import re

                                city_pattern = r"(서울|부산|대구|인천|광주|대전|울산|세종|수원|성남|안양|안산|고양|용인|부천|춘천|강릉|청주|전주|광주|대전|울산|포항|창원|진주|여수|순천|목포|군산|익산|전주|정읍|나주|광양|동해|태백|속초|삼척|원주|충주|제천|보은|옥천|영동|증평|진천|괴산|음성|단양|천안|공주|보령|아산|서산|논산|계룡|당진|금산|부여|서천|청양|홍성|예산|태안)"
                                city_match = re.search(city_pattern, message)
                                if city_match:
                                    parameters["location"] = city_match.group(1)
                                else:
                                    # 도시명이 없으면 도시명을 물어보는 응답 반환
                                    return (
                                        "어느 도시의 날씨를 알고 싶으신가요? (예: 서울, 부산, 대구, 인천, 광주, 대전, 울산, 세종, 수원, 성남, 안양, 안산, 고양, 용인, 부천, 춘천, 강릉, 청주, 전주, 포항, 창원, 진주, 여수, 순천, 목포, 군산, 익산, 정읍, 나주, 광양, 동해, 태백, 속초, 삼척, 원주, 충주, 제천, 보은, 옥천, 영동, 증평, 진천, 괴산, 음성, 단양, 천안, 공주, 보령, 아산, 서산, 논산, 계룡, 당진, 금산, 부여, 서천, 청양, 홍성, 예산, 태안)",
                                        [],
                                    )

                    logger.info(f"📝 추출된 매개변수: {parameters}")

                if tool_name:
                    # LLM이 선택한 도구가 실제로 존재하는지 확인
                    tool_exists = False
                    actual_tool = None

                    for tool in all_tools:
                        tool_actual_name = None

                        # 도구 이름 추출
                        if isinstance(tool, dict):
                            tool_actual_name = tool.get("name")
                        else:
                            # 객체 형태인 경우 다양한 속성 시도
                            for attr in ["name", "tool_name", "function_name"]:
                                if hasattr(tool, attr):
                                    tool_actual_name = getattr(tool, attr)
                                    break

                        if tool_actual_name == tool_name:
                            tool_exists = True
                            actual_tool = tool
                            break

                    if not tool_exists:
                        logger.warning(
                            f"❌ LLM이 선택한 도구 '{tool_name}'이 존재하지 않습니다."
                        )

                        # 사용 가능한 도구 목록 로깅
                        available_tool_names = []
                        for tool in all_tools:
                            if isinstance(tool, dict):
                                available_tool_names.append(tool.get("name", "Unknown"))
                            else:
                                # 객체 형태인 경우
                                tool_name_attr = None
                                for attr in ["name", "tool_name", "function_name"]:
                                    if hasattr(tool, attr):
                                        tool_name_attr = getattr(tool, attr)
                                        break
                                available_tool_names.append(
                                    tool_name_attr or str(tool.__class__.__name__)
                                )

                        logger.info(f"📋 사용 가능한 도구들: {available_tool_names}")

                        # 가장 유사한 도구 찾기 (개선된 유사도 매칭)
                        best_match = None
                        best_score = 0

                        for tool in all_tools:
                            tool_actual_name = None
                            tool_description = ""

                            # 도구 이름과 설명 추출
                            if isinstance(tool, dict):
                                tool_actual_name = tool.get("name", "")
                                tool_description = tool.get("description", "").lower()
                            else:
                                # 객체 형태인 경우
                                for attr in ["name", "tool_name", "function_name"]:
                                    if hasattr(tool, attr):
                                        tool_actual_name = getattr(tool, attr)
                                        break

                                for attr in ["description", "doc", "help"]:
                                    if hasattr(tool, attr):
                                        tool_description = getattr(tool, attr).lower()
                                        break

                            if tool_actual_name:
                                # 개선된 유사도 매칭
                                score = 0

                                # 정확한 매칭
                                if tool_name.lower() == tool_actual_name.lower():
                                    score += 10

                                # 부분 매칭
                                if tool_name.lower() in tool_actual_name.lower():
                                    score += 5
                                if tool_actual_name.lower() in tool_name.lower():
                                    score += 3

                                # 설명에서 키워드 매칭
                                if tool_name.lower() in tool_description:
                                    score += 2

                                # 언더스코어로 구분된 키워드 매칭
                                tool_keywords = tool_name.lower().split("_")
                                for keyword in tool_keywords:
                                    if (
                                        keyword in tool_actual_name.lower()
                                        or keyword in tool_description
                                    ):
                                        score += 1

                                if score > best_score:
                                    best_score = score
                                    best_match = tool_actual_name

                        if best_match and best_score > 0:
                            original_tool_name = tool_name
                            tool_name = best_match
                            logger.info(
                                f"🔧 유사한 도구로 매핑: {original_tool_name} → {tool_name} (점수: {best_score})"
                            )
                        else:
                            logger.error(
                                f"❌ 유사한 도구를 찾을 수 없습니다: {tool_name}"
                            )
                            logger.info("🔄 사용 가능한 도구가 없어 일반 대화로 전환")
                            logger.info("=" * 50)
                            return None, []  # MCP 사용하지 않고 일반 대화로 전환

                    # 도구 실행
                    if tool_name:  # tool_name이 None이 아닌 경우에만 실행
                        try:
                            logger.info(f"🚀 도구 실행 시작:")
                            logger.info(f"  - 도구 이름: {tool_name}")
                            logger.info(f"  - 매개변수: {parameters}")

                            # MCP 클라이언트를 통해 도구 실행
                            # 어떤 서버에 있는 도구인지 찾기
                            target_server = None
                            for server_name in available_servers:
                                try:
                                    server_tools = (
                                        await self.mcp_client_service.get_tools(
                                            server_name
                                        )
                                    )
                                    for tool in server_tools:
                                        # 도구 이름 추출
                                        tool_actual_name = None
                                        if isinstance(tool, dict):
                                            tool_actual_name = tool.get("name")
                                        else:
                                            # 객체 형태인 경우 다양한 속성 시도
                                            for attr in [
                                                "name",
                                                "tool_name",
                                                "function_name",
                                            ]:
                                                if hasattr(tool, attr):
                                                    tool_actual_name = getattr(
                                                        tool, attr
                                                    )
                                                    break

                                        if tool_actual_name == tool_name:
                                            target_server = server_name
                                            break
                                    if target_server:
                                        break
                                except Exception as e:
                                    logger.warning(
                                        f"서버 '{server_name}' 도구 검색 실패: {e}"
                                    )

                            if target_server:
                                logger.info(
                                    f"✅ 도구 '{tool_name}'을 서버 '{target_server}'에서 찾음"
                                )

                                # 매개변수 매핑 및 변환
                                if not parameters:
                                    parameters = {"message": message}
                                elif "message" not in parameters:
                                    parameters["message"] = message

                                # 수학 도구 매개변수 매핑
                                math_tools = [
                                    "add",
                                    "subtract",
                                    "multiply",
                                    "divide",
                                    "power",
                                    "sqrt",
                                    "factorial",
                                    "gcd",
                                    "lcm",
                                ]
                                if tool_name in math_tools:
                                    # LLM이 추출한 매개변수를 실제 도구 매개변수로 매핑
                                    mapped_params = {}

                                    # 숫자 매개변수 매핑
                                    if "숫자1" in parameters:
                                        mapped_params["a"] = float(parameters["숫자1"])
                                    if "숫자2" in parameters:
                                        mapped_params["b"] = float(parameters["숫자2"])
                                    if "number" in parameters:
                                        mapped_params["number"] = float(
                                            parameters["number"]
                                        )
                                    if "base" in parameters:
                                        mapped_params["base"] = float(
                                            parameters["base"]
                                        )
                                    if "exponent" in parameters:
                                        mapped_params["exponent"] = float(
                                            parameters["exponent"]
                                        )
                                    if "n" in parameters:
                                        mapped_params["n"] = int(parameters["n"])

                                    # 매핑된 매개변수가 있으면 사용
                                    if mapped_params:
                                        parameters = mapped_params
                                        logger.info(
                                            f"🔧 매개변수 매핑 완료: {parameters}"
                                        )

                                # 검색 도구의 경우 query 매개변수 추가
                                if (
                                    "search" in tool_name.lower()
                                    or "web" in tool_name.lower()
                                ):
                                    if "query" not in parameters:
                                        # 메시지에서 검색어 추출
                                        import re

                                        search_terms = re.findall(
                                            r'["\']([^"\']+)["\']', message
                                        )
                                        if search_terms:
                                            parameters["query"] = search_terms[0]
                                        else:
                                            # 따옴표가 없으면 전체 메시지를 검색어로 사용
                                            parameters["query"] = message.strip()
                                    logger.info(f"🔍 검색 도구 매개변수: {parameters}")

                                logger.info(
                                    f"📤 서버 '{target_server}'로 도구 실행 요청:"
                                )
                                logger.info(f"  - 도구: {tool_name}")
                                logger.info(f"  - 매개변수: {parameters}")

                                result = await self.mcp_client_service.execute_tool(
                                    target_server, tool_name, parameters
                                )

                                logger.info(f"📥 도구 실행 결과: {result}")

                                # 도구 실행 결과가 실패 메시지인지 확인
                                if isinstance(result, str):
                                    failure_keywords = [
                                        "죄송해요",
                                        "죄송합니다",
                                        "가져올 수 없어요",
                                        "일시적인 문제",
                                        "오류가 발생",
                                        "실패",
                                    ]
                                    if any(
                                        keyword in result
                                        for keyword in failure_keywords
                                    ):
                                        logger.info(
                                            "🔄 도구 실행 실패로 일반 대화로 전환"
                                        )
                                        logger.info("=" * 50)
                                        return (
                                            None,
                                            [],
                                        )  # MCP 사용하지 않고 일반 대화로 전환

                                # 검색 결과를 자연어로 변환
                                if isinstance(result, dict):
                                    # 웹검색 결과인지 확인
                                    if "results" in result and "requestId" in result:
                                        # 웹검색 결과를 자연어로 변환
                                        natural_result = self._convert_search_result_to_natural_language(
                                            result, message
                                        )
                                        tool_results.append(natural_result)
                                    else:
                                        # 다른 dict 결과는 기존 방식으로 처리
                                        tool_results.append(str(result))
                                else:
                                    tool_results.append(str(result))

                        except Exception as e:
                            logger.error(f"❌ 도구 실행 중 오류: {e}")
                            logger.info("🔄 MCP 도구 실행 실패로 일반 대화로 전환")
                            logger.info("=" * 50)
                            return None, []  # MCP 사용하지 않고 일반 대화로 전환

                    # 도구 사용 기록
                    if tool_name:
                        tools_used.append(tool_name)

            # 웹검색이 필요한 경우 처리
            elif "웹검색 필요" in intent_text:
                logger.info("🌐 웹검색이 필요한 질문으로 판단됨")

                # 웹검색 도구 선택
                web_search_tools = [
                    "web_search_exa",
                    "wikipedia_search_exa",
                    "github_search_exa",
                    "research_paper_search_exa",
                ]

                # 질문 유형에 따라 적절한 검색 도구 선택
                search_tool = "web_search_exa"  # 기본값

                if any(
                    keyword in message.lower()
                    for keyword in ["위키", "위키피디아", "wikipedia"]
                ):
                    search_tool = "wikipedia_search_exa"
                elif any(
                    keyword in message.lower()
                    for keyword in ["깃허브", "github", "코드", "프로그래밍"]
                ):
                    search_tool = "github_search_exa"
                elif any(
                    keyword in message.lower()
                    for keyword in ["논문", "연구", "학술", "academic"]
                ):
                    search_tool = "research_paper_search_exa"

                logger.info(f"🔍 선택된 검색 도구: {search_tool}")

                try:
                    # 웹검색 실행
                    search_parameters = {"query": message}

                    # websearch 서버에서 도구 실행
                    search_result = await self.mcp_client_service.execute_tool(
                        "websearch", search_tool, search_parameters
                    )

                    if search_result:
                        logger.info(f"✅ 웹검색 성공: {search_result[:200]}...")
                        return search_result, [search_tool]
                    else:
                        logger.warning("❌ 웹검색 실패")
                        return None, []

                except Exception as e:
                    logger.error(f"❌ 웹검색 중 오류: {e}")
                    return None, []

            # 결과 조합
            if tool_results:
                tool_result_text = "\n".join(tool_results)
                # 도구 결과를 LLM에 다시 넣어 자연스러운 답변 생성
                final_prompt = f"사용자 질문: {message}\n도구 결과: {tool_result_text}\n위 정보를 바탕으로, 친근하고 자연스럽게 답변해 주세요."
                llm_final = await self.vllm_client.generate_response(
                    user_message=final_prompt,
                    system_message="당신은 친근하고 유용한 AI 어시스턴트입니다.",
                    max_new_tokens=200,
                    temperature=0.7,
                )
                final_response = llm_final.get("response", "").strip()
                logger.info(f"🎯 최종 LLM 자연어 답변: {final_response}")
                logger.info(f"📋 사용된 도구: {tools_used}")
                logger.info("=" * 50)
                return final_response, tools_used
            else:
                logger.info("❌ 도구 실행 결과가 없음")
                logger.info("=" * 50)
                return None, []

        except Exception as e:
            logger.error(f"❌ MCPToolProcessor 도구 처리 중 오류: {e}")
            logger.info("🔄 MCP 처리 중 오류로 일반 대화로 전환")
            logger.info("=" * 50)
            return None, []  # MCP 사용하지 않고 일반 대화로 전환


# 전역 MCP 도구 처리기 인스턴스
mcp_tool_processor = MCPToolProcessor()


# MCP 도구 처리 함수들 (외부에서 사용)
async def should_use_mcp_tools(message: str) -> bool:
    """메시지가 MCP 도구 사용이 필요한지 확인"""
    return await mcp_tool_processor.should_use_mcp_tools(message)


async def process_with_mcp_tools(
    message: str, selected_servers: List[str] = None
) -> Tuple[Optional[str], List[str]]:
    """MCP 도구를 사용하여 메시지 처리"""
    return await mcp_tool_processor.process_with_mcp_tools(message, selected_servers)


# MCP 서버 관리 엔드포인트들
@router.post("/servers/{server_name}/add")
async def add_mcp_server(server_name: str, server_url: str):
    """새로운 MCP 서버를 추가합니다."""
    try:
        from app.services.mcp_server_manager import mcp_server_manager

        # 서버 추가
        await mcp_server_manager.add_server(server_name, server_url)

        return {
            "message": f"MCP 서버 {server_name} 추가 완료",
            "server_name": server_name,
            "server_url": server_url,
        }
    except Exception as e:
        logger.error(f"MCP 서버 추가 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"MCP 서버 추가 실패: {str(e)}",
        )


@router.delete("/servers/{server_name}")
async def remove_mcp_server(server_name: str):
    """MCP 서버를 제거합니다."""
    try:
        from app.services.mcp_server_manager import mcp_server_manager

        # 서버 제거
        await mcp_server_manager.remove_server(server_name)

        return {
            "message": f"MCP 서버 {server_name} 제거 완료",
            "server_name": server_name,
        }
    except Exception as e:
        logger.error(f"MCP 서버 제거 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"MCP 서버 제거 실패: {str(e)}",
        )


@router.get("/servers")
async def get_mcp_servers():
    """등록된 MCP 서버 목록을 가져옵니다."""
    try:
        from app.services.mcp_server_manager import mcp_server_manager

        server_status = mcp_server_manager.get_server_status()
        return {"servers": server_status, "total_count": len(server_status)}
    except Exception as e:
        logger.error(f"MCP 서버 목록 조회 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"MCP 서버 목록 조회 실패: {str(e)}",
        )


@router.post("/servers/{server_name}/start")
async def start_mcp_server(server_name: str):
    """MCP 서버를 시작합니다."""
    try:
        from app.services.mcp_server_manager import mcp_server_manager

        await mcp_server_manager.start_server(server_name)

        return {"message": f"MCP 서버 {server_name} 시작 완료"}
    except Exception as e:
        logger.error(f"MCP 서버 시작 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"MCP 서버 시작 실패: {str(e)}",
        )


@router.post("/servers/{server_name}/stop")
async def stop_mcp_server(server_name: str):
    """MCP 서버를 중지합니다."""
    try:
        from app.services.mcp_server_manager import mcp_server_manager

        await mcp_server_manager.stop_server(server_name)

        return {"message": f"MCP 서버 {server_name} 중지 완료"}
    except Exception as e:
        logger.error(f"MCP 서버 중지 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"MCP 서버 중지 실패: {str(e)}",
        )


# 디버그 및 상태 확인 엔드포인트들
@router.get("/debug/tools")
async def debug_tools():
    """현재 사용 가능한 도구들의 상태를 가져옵니다."""
    try:
        from app.services.mcp_server_manager import mcp_server_manager

        server_status = mcp_server_manager.get_server_status()
        available_servers = [
            name
            for name, status in server_status.items()
            if status.get("running", False)
        ]

        all_tools = []
        for server_name in available_servers:
            try:
                from app.services.mcp_client import mcp_client_service

                tools = await mcp_client_service.get_tools(server_name)
                all_tools.extend(tools)
            except Exception as e:
                logger.warning(f"서버 '{server_name}' 도구 로드 실패: {e}")

        return {
            "total_tools": len(all_tools),
            "available_servers": available_servers,
            "tools": all_tools,
        }
    except Exception as e:
        logger.error(f"도구 상태 조회 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"도구 상태 조회 실패: {str(e)}",
        )


@router.get("/vllm/status")
async def get_vllm_status():
    """VLLM 서버 상태를 확인합니다."""
    try:
        from app.services.vllm_client import vllm_health_check

        is_healthy = await vllm_health_check()
        return {
            "status": "healthy" if is_healthy else "unhealthy",
            "timestamp": datetime.now().isoformat(),
        }
    except Exception as e:
        logger.error(f"VLLM 상태 확인 실패: {e}")
        return {
            "status": "error",
            "error": str(e),
            "timestamp": datetime.now().isoformat(),
        }


@router.post("/vllm/test")
async def test_vllm_connection():
    """VLLM 연결을 테스트합니다."""
    try:
        from app.services.vllm_client import get_vllm_client

        vllm_client = await get_vllm_client()
        result = await vllm_client.generate_response(
            user_message="안녕하세요",
            system_message="테스트 메시지입니다.",
            influencer_name="테스트",
            max_new_tokens=10,
            temperature=0.1,
        )

        return {
            "success": True,
            "message": "VLLM 연결 테스트 성공",
            "response": result.get("response", ""),
        }
    except Exception as e:
        logger.error(f"VLLM 연결 테스트 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"VLLM 연결 테스트 실패: {str(e)}",
        )


@router.post("/vllm/load-adapter")
async def load_vllm_adapter(
    model_id: str,
    hf_repo_name: str,
    hf_token: Optional[str] = None,
    base_model_override: Optional[str] = None,
):
    """VLLM 어댑터를 로드합니다."""
    try:
        from app.services.vllm_client import get_vllm_client

        vllm_client = await get_vllm_client()
        await vllm_client.load_adapter(
            hf_repo_name, model_id, hf_token, base_model_override
        )

        return {
            "success": True,
            "message": f"어댑터 '{model_id}' 로드 완료",
            "model_id": model_id,
            "hf_repo_name": hf_repo_name,
        }
    except Exception as e:
        logger.error(f"VLLM 어댑터 로드 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"VLLM 어댑터 로드 실패: {str(e)}",
        )


@router.get("/vllm/adapters")
async def list_vllm_adapters():
    """로드된 VLLM 어댑터 목록을 가져옵니다."""
    try:
        from app.services.vllm_client import get_vllm_client

        vllm_client = await get_vllm_client()
        adapters = vllm_client.get_loaded_adapters()

        return {
            "adapters": adapters,
            "total_count": len(adapters),
        }
    except Exception as e:
        logger.error(f"VLLM 어댑터 목록 조회 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"VLLM 어댑터 목록 조회 실패: {str(e)}",
        )


@router.delete("/vllm/adapters/{model_id}")
async def unload_vllm_adapter(model_id: str):
    """VLLM 어댑터를 언로드합니다."""
    try:
        from app.services.vllm_client import get_vllm_client

        vllm_client = await get_vllm_client()
        await vllm_client.unload_adapter(model_id)

        return {
            "success": True,
            "message": f"어댑터 '{model_id}' 언로드 완료",
            "model_id": model_id,
        }
    except Exception as e:
        logger.error(f"VLLM 어댑터 언로드 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"VLLM 어댑터 언로드 실패: {str(e)}",
        )


# process_with_mcp_tools 엔드포인트에서 influencer_name 파라미터 제거
@router.post("/process")
async def process_mcp_message(message: str = Body(..., embed=True)):
    """
    MCP 챗봇 메시지 처리 엔드포인트
    - message(str): 사용자의 입력 메시지
    - return: { response: str, tools_used: List[str] }
    """
    try:
        response, tools_used = await process_with_mcp_tools(message)
        return {"response": response, "tools_used": tools_used}
    except Exception as e:
        logger.error(f"MCP 메시지 처리 실패: {e}")
        return {"response": "MCP 처리 중 오류가 발생했습니다.", "tools_used": []}

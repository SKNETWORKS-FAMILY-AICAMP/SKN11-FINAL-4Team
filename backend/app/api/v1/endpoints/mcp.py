"""
지능적인 도구 선택을 사용한 MCP 챗봇 구현
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from fastapi import APIRouter, HTTPException, status, Depends, Body, Request
from pydantic import BaseModel, root_validator
import os
import asyncio
import math
import re
from datetime import datetime
from sqlalchemy.orm import Session
from app.database import get_db
from app.core.security import get_current_user
from app.services.openai_service_simple import OpenAIService

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
        self.openai_service = OpenAIService()

    async def initialize(self):
        """초기화"""
        try:
            from app.services.mcp_client import mcp_client_service

            self.mcp_client_service = mcp_client_service
            # vllm_client 초기화 삭제
            logger.info("MCP 도구 처리기 초기화 완료")
        except Exception as e:
            logger.error(f"MCP 도구 처리기 초기화 실패: {e}")

    async def should_use_mcp_tools(self, message: str) -> bool:
        """메시지가 MCP 도구 사용이 필요한지 확인"""
        try:
            logger.info("🔍 MCP 도구 사용 여부 판단 시작:")
            logger.info(f"  - 사용자 메시지: {message}")

            # OpenAI를 사용한 지능적 판단
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
            logger.info("🧠 OpenAI를 사용한 도구 사용 여부 분석 중...")
            response = await self.openai_service.openai_tool_selection(
                user_prompt=prompt,
                system_prompt="당신은 도구 사용 여부를 판단하는 AI입니다. YES 또는 NO로만 답변하세요.",
            )
            response_text = response.strip().upper()
            should_use = "YES" in response_text
            logger.info(f"📊 도구 사용 여부 판단 결과:")
            logger.info(f"  - OpenAI 응답: {response_text}")
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

    async def process_with_mcp_tools(
        self, message: str, selected_servers: List[str] = None
    ) -> Tuple[Optional[str], List[str]]:
        """MCP 도구를 사용하여 메시지 처리 (도구 결과를 LLM에 다시 넣어 자연스러운 답변 생성)"""
        try:
            logger.info("=" * 50)
            logger.info("🚀 MCPToolProcessor 도구 처리 시작")
            logger.info(f"📝 사용자 메시지: {message}")
            logger.info("=" * 50)

            if not self.mcp_client_service:
                logger.info("🔧 MCPToolProcessor 초기화 중...")
                await self.initialize()

            # 1단계: 도구 사용 필요 여부 판단
            should_use_tool = await self.should_use_mcp_tools(message)
            logger.info(f"🔍 도구 사용 필요 여부: {should_use_tool}")
            if not should_use_tool:
                logger.info("❌ 도구 사용 불필요. 일반 대화로 전환.")
                return None, []

            # 선택된 서버만 도구 미리 캐시
            if selected_servers:
                await self.mcp_client_service.initialize_mcp_client(selected_servers)
            else:
                await self.mcp_client_service.initialize_mcp_client()

            # 사용 가능한 모든 MCP 서버의 도구들 가져오기
            all_tools = []
            from app.services.mcp_server_manager import mcp_server_manager

            server_status = mcp_server_manager.get_server_status()
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

            logger.info("🧠 OpenAI를 사용한 도구 사용 의도 분석 시작...")
            # OpenAI로 도구 선택
            intent_result = await self.openai_service.openai_tool_selection(
                user_prompt=intent_prompt,
                system_prompt="당신은 도구 사용 의도를 분석하는 AI입니다. 정확한 도구명과 매개변수를 추출해주세요.",
            )
            intent_text = intent_result
            logger.info(f"📊 도구 사용 의도 분석 결과: {intent_text}")

            # 2단계: 도구 실행
            tools_used = []
            tool_results = []

            if "도구 불필요" not in intent_text:
                # 도구명과 매개변수 추출
                tool_name = None
                parameters = {}
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
                    params_parts = params_line.split(",")
                    for part in params_parts:
                        if "=" in part:
                            key, value = part.split("=", 1)
                            parameters[key.strip()] = value.strip()
                logger.info(f"📝 추출된 매개변수: {parameters}")

                if tool_name:
                    target_server = None
                    for server_name in available_servers:
                        server_tools = await self.mcp_client_service.get_tools(
                            server_name
                        )
                        for tool in server_tools:
                            tool_actual_name = (
                                tool.get("name")
                                if isinstance(tool, dict)
                                else getattr(tool, "name", None)
                            )
                            if tool_actual_name == tool_name:
                                target_server = server_name
                                break
                        if target_server:
                            break
                    if not target_server:
                        logger.error(
                            f"❌ 도구 '{tool_name}'을 실행할 서버를 찾을 수 없습니다."
                        )
                        return None, []
                    logger.info(f"🚀 도구 실행 시작:")
                    logger.info(f"  - 도구 이름: {tool_name}")
                    logger.info(f"  - 매개변수: {parameters}")
                    result = await self.mcp_client_service.execute_tool(
                        target_server, tool_name, parameters
                    )
                    logger.info(f"📥 도구 실행 결과: {result}")

                    def get_tool_type(tool_name, all_tools):
                        for tool in all_tools:
                            tname = (
                                tool.get("name")
                                if isinstance(tool, dict)
                                else getattr(tool, "name", None)
                            )
                            ttype = (
                                tool.get("type")
                                if isinstance(tool, dict)
                                else getattr(tool, "type", None)
                            )
                            if tname == tool_name:
                                return ttype or None
                        return None

                    tool_type = get_tool_type(tool_name, all_tools)
                    if tool_type == "numeric":
                        parse_prompt = (
                            "아래 도구 결과의 모든 정보(수치, 상태 등)를 빠짐없이, 변형/누락 없이 명확하게 전달하세요. "
                            "불필요한 사설, 감탄, 이모지, 인사말, 추천, 조언 등은 절대 포함하지 마세요.\n"
                            f"\n도구 결과:\n{result}"
                        )
                    elif tool_type == "search":
                        parse_prompt = (
                            "아래 검색 결과의 모든 항목을 빠짐없이, 불필요한 URL, 특수문자, 메타데이터만 제거하고 명확하게 전달하세요. "
                            "요약하지 말고, 모든 항목을 포함하세요. 사설, 감탄, 이모지, 인사말, 추천, 조언 등은 절대 포함하지 마세요.\n"
                            f"\n도구 결과:\n{result}"
                        )
                    elif tool_type == "text":
                        parse_prompt = (
                            "아래 결과의 모든 정보(주요 내용 등)를 빠짐없이, 변형/누락 없이 명확하게 전달하세요. "
                            "불필요한 사설, 감탄, 이모지, 인사말, 추천, 조언 등은 절대 포함하지 마세요.\n"
                            f"\n도구 결과:\n{result}"
                        )
                    else:
                        parse_prompt = (
                            "아래 도구 결과의 모든 정보(수치, 상태, 주요 내용 등)를 빠짐없이, 변형/누락 없이 명확하게 전달하세요. "
                            "불필요한 사설, 감탄, 이모지, 인사말, 추천, 조언 등은 절대 포함하지 마세요.\n"
                            f"\n도구 결과:\n{result}"
                        )
                    parsed_result = await self.openai_service.openai_tool_selection(
                        user_prompt=parse_prompt,
                        system_prompt="당신은 정보를 명확하고 정확하게, 가장 적합한 형태로만 전달하는 AI입니다. 불필요한 말은 절대 포함하지 마세요.",
                    )
                    logger.info(f"📝 파싱된 도구 결과: {parsed_result}")
                    tool_results.append(parsed_result)
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
                # 도구 결과를 LLM에 다시 넣어 자연어 답변 생성 (도구 결과의 정보가 반드시 포함되도록 프롬프트 강화)
                final_prompt = (
                    f"아래 도구 결과의 정보를 반드시 포함해서, 정보가 누락/왜곡/변형되지 않게 명확하게 답변하세요. "
                    f"사설, 감탄, 이모지, 말투, 인사말, 추천, 조언 등은 절대 포함하지 마세요.\n"
                    f"도구 결과: {tool_result_text}\n"
                    f"사용자 질문: {message}"
                )
                llm_final = await self.openai_service.openai_tool_selection(
                    user_prompt=final_prompt,
                    system_prompt="당신은 정보를 명확하고 정확하게, 도구 결과를 반드시 포함해서 답변하는 AI입니다. 불필요한 말은 절대 포함하지 마세요.",
                )
                final_response = llm_final.strip()
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


class MCPServerAddRequest(BaseModel):
    server_url: Optional[str] = None
    command: Optional[str] = None
    args: Optional[List[str]] = None
    transport: Optional[str] = None
    description: Optional[str] = None

    @root_validator(pre=True)
    def validate_and_autofill(cls, values):
        # command/args만 있으면 transport=stdio 자동 추가
        if values.get("command") and values.get("args") and not values.get("transport"):
            values["transport"] = "stdio"
        return values


@router.post("/servers/add")
async def add_mcp_server(request: Request):
    """새로운 MCP 서버를 추가합니다. (HTTP: 쿼리/JSON, STDIO: JSON 전체)"""
    try:
        from app.services.mcp_server_manager import mcp_server_manager

        data = await request.json()
        # STDIO 방식: {"frankfurtermcp": { ... }} 형태
        if (
            isinstance(data, dict)
            and len(data) == 1
            and isinstance(list(data.values())[0], dict)
        ):
            server_name = list(data.keys())[0]
            config = data[server_name]

            # transport 필드가 없으면 자동으로 stdio 추가
            if "command" in config and "args" in config and "transport" not in config:
                config["transport"] = "stdio"

            # description 필드가 없으면 기본값 추가
            if "description" not in config:
                config["description"] = f"{server_name} MCP 서버"

            # 서버 설정 추가
            mcp_server_manager.server_configs[server_name] = config

            # 서버 시작
            try:
                await mcp_server_manager._start_server_with_config(server_name, config)
                logger.info(f"✅ MCP 서버 '{server_name}' 시작 완료")

                # MCP 클라이언트에 동적으로 서버 추가
                from app.services.mcp_client import get_mcp_client

                mcp_client_service = get_mcp_client()

                # 동적 추가 시도 (실패 시 전체 재초기화)
                await mcp_client_service.add_server_dynamically(server_name, config)
                logger.info(f"✅ MCP 클라이언트에 서버 '{server_name}' 추가 완료")

            except Exception as e:
                logger.error(f"❌ MCP 서버 '{server_name}' 시작 실패: {e}")
                # 시작 실패해도 설정은 유지 (나중에 수동으로 시작 가능)

            return {
                "message": f"MCP 서버 {server_name} 추가 완료 (STDIO)",
                "server_name": server_name,
                "config": config,
            }
        # HTTP 방식: {"server_url": ...} 형태
        elif "server_url" in data:
            server_name = data.get("name")
            if not server_name:
                raise HTTPException(
                    status_code=400,
                    detail="HTTP 방식은 name 필드(서버명)가 필요합니다.",
                )
            await mcp_server_manager.add_server(server_name, data["server_url"])
            return {
                "message": f"MCP 서버 {server_name} 추가 완료 (HTTP)",
                "server_name": server_name,
                "server_url": data["server_url"],
            }
        else:
            raise HTTPException(
                status_code=400,
                detail='지원하지 않는 형식입니다. STDIO: {"name": {...}}, HTTP: {"name":..., "server_url":...}',
            )
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
async def process_mcp_message(
    message: str = Body(..., embed=True),
    selected_servers: Optional[List[str]] = Body(None, embed=True),
):
    """
    MCP 챗봇 메시지 처리 엔드포인트
    - message(str): 사용자의 입력 메시지
    - selected_servers(List[str], optional): 사용할 MCP 서버 목록
    - return: { response: str, tools_used: List[str] }
    """
    try:
        response, tools_used = await process_with_mcp_tools(message, selected_servers)
        return {"response": response, "tools_used": tools_used}
    except Exception as e:
        logger.error(f"MCP 메시지 처리 실패: {e}")
        return {"response": "MCP 처리 중 오류가 발생했습니다.", "tools_used": []}


@router.post("/chat/set-selected-servers")
async def set_selected_servers(
    influencer_id: str = Body(..., embed=True),
    selected_servers: List[str] = Body(..., embed=True),
):
    """챗봇에서 사용할 선택된 서버 정보를 데이터베이스에 저장합니다."""
    try:
        from app.services.chat_session_service import ChatSessionService
        from app.services.mcp_server_manager import mcp_server_manager

        # 허용된 서버 목록 검증
        available_servers = list(mcp_server_manager.server_configs.keys())
        validated_servers = [
            server for server in selected_servers if server in available_servers
        ]

        # 데이터베이스에 저장
        success = ChatSessionService.save_selected_servers(
            influencer_id=influencer_id, selected_servers=validated_servers
        )

        if success:
            logger.info(
                f"선택된 서버 정보 저장 완료: influencer_id={influencer_id}, servers={validated_servers}"
            )
            return {
                "message": "선택된 서버 정보가 저장되었습니다.",
                "influencer_id": influencer_id,
                "selected_servers": validated_servers,
            }
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="서버 정보 저장에 실패했습니다.",
            )

    except Exception as e:
        logger.error(f"서버 정보 저장 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"서버 정보 저장 실패: {str(e)}",
        )


@router.get("/chat/get-selected-servers/{influencer_id}")
async def get_selected_servers(influencer_id: str):
    """챗봇에서 사용할 선택된 서버 정보를 데이터베이스에서 가져옵니다."""
    try:
        from app.services.chat_session_service import ChatSessionService

        # 데이터베이스에서 저장된 서버 정보 가져오기
        selected_servers = ChatSessionService.get_selected_servers(influencer_id)

        logger.info(
            f"저장된 서버 정보 조회: influencer_id={influencer_id}, servers={selected_servers}"
        )

        return {"influencer_id": influencer_id, "selected_servers": selected_servers}

    except Exception as e:
        logger.error(f"서버 정보 조회 실패: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"서버 정보 조회 실패: {str(e)}",
        )

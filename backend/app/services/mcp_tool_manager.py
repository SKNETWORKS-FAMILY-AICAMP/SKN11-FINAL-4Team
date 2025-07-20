"""
MCP 도구들을 동적으로 관리하는 서비스
"""
import logging
from typing import List, Dict, Any, Optional
from langchain.tools import Tool
import math
import httpx
import json

logger = logging.getLogger(__name__)

class MCPToolManager:
    def __init__(self):
        self.tools: Dict[str, Tool] = {}
        self.mcp_servers: Dict[str, str] = {}
        self.is_initialized = False
        
    async def initialize(self):
        """MCP 도구들을 초기화합니다."""
        try:
            # 1. 기본 수학 도구들 등록
            await self._register_basic_math_tools()
            
            # 2. MCP 서버들에서 도구들 동적 로드
            await self._load_mcp_server_tools()
            
            self.is_initialized = True
            logger.info(f"MCP 도구 매니저 초기화 완료: {len(self.tools)}개 도구")
            return True
            
        except Exception as e:
            logger.error(f"MCP 도구 매니저 초기화 실패: {e}")
            return False
    
    async def _register_basic_math_tools(self):
        """기본 수학 도구들을 등록합니다."""
        def add_numbers(a: float, b: float) -> float:
            """두 숫자를 더합니다"""
            return a + b
        
        def multiply_numbers(a: float, b: float) -> float:
            """두 숫자를 곱합니다"""
            return a * b
        
        def sqrt_number(number: float) -> float:
            """숫자의 제곱근을 계산합니다"""
            return math.sqrt(number)
        
        def factorial_number(n: int) -> int:
            """숫자의 팩토리얼을 계산합니다"""
            return math.factorial(n)
        
        # 기본 수학 도구들 등록
        basic_tools = [
            ("add", add_numbers, "두 숫자를 더합니다"),
            ("multiply", multiply_numbers, "두 숫자를 곱합니다"),
            ("sqrt", sqrt_number, "숫자의 제곱근을 계산합니다"),
            ("factorial", factorial_number, "숫자의 팩토리얼을 계산합니다"),
        ]
        
        for name, func, description in basic_tools:
            self.tools[name] = Tool(
                name=name,
                description=description,
                func=func
            )
            logger.info(f"기본 도구 등록: {name}")
    
    async def _load_mcp_server_tools(self):
        """MCP 서버들에서 도구들을 동적으로 로드합니다."""
        # MCP 서버 설정 (추후 확장 가능)
        mcp_servers = {
            "math": "http://localhost:8001",
            "weather": "http://localhost:8002",
        }
        
        for server_name, server_url in mcp_servers.items():
            try:
                await self._load_tools_from_server(server_name, server_url)
            except Exception as e:
                logger.warning(f"MCP 서버 {server_name} 로드 실패: {e}")
    
    async def _load_tools_from_server(self, server_name: str, server_url: str):
        """특정 MCP 서버에서 도구들을 로드합니다."""
        try:
            async with httpx.AsyncClient() as client:
                # 서버 상태 확인
                response = await client.get(f"{server_url}/health")
                if response.status_code != 200:
                    logger.warning(f"MCP 서버 {server_name} 연결 실패")
                    return
                
                # 도구 목록 가져오기
                response = await client.get(f"{server_url}/tools")
                if response.status_code == 200:
                    tools_data = response.json()
                    
                    for tool_data in tools_data.get("tools", []):
                        tool_name = tool_data.get("name")
                        if tool_name:
                            # MCP 서버 도구를 LangChain 도구로 래핑
                            wrapped_tool = await self._create_mcp_tool_wrapper(
                                server_name, server_url, tool_data
                            )
                            self.tools[f"{server_name}_{tool_name}"] = wrapped_tool
                            logger.info(f"MCP 도구 등록: {server_name}_{tool_name}")
                            
        except Exception as e:
            logger.error(f"MCP 서버 {server_name} 도구 로드 실패: {e}")
    
    async def _create_mcp_tool_wrapper(self, server_name: str, server_url: str, tool_data: Dict) -> Tool:
        """MCP 도구를 LangChain 도구로 래핑합니다."""
        tool_name = tool_data.get("name")
        description = tool_data.get("description", "")
        
        async def mcp_tool_wrapper(**kwargs):
            """MCP 서버의 도구를 호출하는 래퍼 함수"""
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{server_url}/tools/{tool_name}",
                        json={"parameters": kwargs}
                    )
                    
                    if response.status_code == 200:
                        result = response.json()
                        return result.get("result", "도구 실행 실패")
                    else:
                        return f"도구 실행 오류: {response.status_code}"
                        
            except Exception as e:
                return f"도구 실행 중 오류: {str(e)}"
        
        return Tool(
            name=f"{server_name}_{tool_name}",
            description=f"[{server_name}] {description}",
            func=mcp_tool_wrapper
        )
    
    def get_tools(self) -> List[Tool]:
        """등록된 모든 도구들을 반환합니다."""
        return list(self.tools.values())
    
    def get_tool_names(self) -> List[str]:
        """등록된 도구 이름들을 반환합니다."""
        return list(self.tools.keys())
    
    def add_tool(self, name: str, tool: Tool):
        """새로운 도구를 추가합니다."""
        self.tools[name] = tool
        logger.info(f"새 도구 추가: {name}")
    
    def remove_tool(self, name: str):
        """도구를 제거합니다."""
        if name in self.tools:
            del self.tools[name]
            logger.info(f"도구 제거: {name}")
    
    def get_tool_info(self) -> Dict[str, Dict]:
        """모든 도구의 정보를 반환합니다."""
        tool_info = {}
        for name, tool in self.tools.items():
            tool_info[name] = {
                "name": tool.name,
                "description": tool.description,
                "type": "basic" if not "_" in name else "mcp"
            }
        return tool_info

# 전역 인스턴스
mcp_tool_manager = MCPToolManager() 
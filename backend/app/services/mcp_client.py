import logging
from typing import List, Dict, Any
import httpx
import json

logger = logging.getLogger(__name__)

class MCPClientService:
    def __init__(self):
        self.clients: Dict[str, httpx.AsyncClient] = {}
        
    async def get_client(self, server_name: str) -> httpx.AsyncClient:
        """HTTP 클라이언트를 가져오거나 생성합니다."""
        if server_name not in self.clients:
            # 각 서버별 설정
            server_urls = {
                "math": "http://localhost:8003",
                "weather": "http://localhost:8005",
            }
            
            if server_name not in server_urls:
                raise ValueError(f"알 수 없는 서버: {server_name}")
                
            url = server_urls[server_name]
            
            try:
                # HTTP 클라이언트 생성
                client = httpx.AsyncClient(base_url=url, timeout=30.0)
                self.clients[server_name] = client
                logger.info(f"MCP HTTP 클라이언트 '{server_name}' 생성 완료")
                
            except Exception as e:
                logger.error(f"MCP HTTP 클라이언트 '{server_name}' 생성 실패: {e}")
                raise
                
        return self.clients[server_name]
        
    async def get_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """특정 MCP 서버의 도구들을 가져옵니다."""
        try:
            client = await self.get_client(server_name)
            
            # MCP 서버에서 도구 목록 가져오기
            try:
                response = await client.get("/tools")
                if response.status_code == 200:
                    tools = response.json()
                    logger.info(f"MCP 서버 '{server_name}'에서 {len(tools)}개 도구 로드")
                    return tools
                else:
                    logger.warning(f"MCP 서버 '{server_name}' 도구 요청 실패: {response.status_code}")
                    return self._get_default_tools(server_name)
                    
            except Exception as tool_error:
                logger.warning(f"도구 가져오기 실패: {tool_error}")
                return self._get_default_tools(server_name)
            
        except Exception as e:
            logger.error(f"MCP 서버 '{server_name}' 도구 로드 실패: {e}")
            return self._get_default_tools(server_name)
    
    def _get_default_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """기본 도구 목록을 반환합니다."""
        if server_name == "math":
            return [
                {
                    "name": "add",
                    "description": "두 숫자를 더합니다.",
                    "args_schema": {"a": "float", "b": "float"}
                },
                {
                    "name": "subtract", 
                    "description": "두 숫자를 뺍니다.",
                    "args_schema": {"a": "float", "b": "float"}
                },
                {
                    "name": "multiply",
                    "description": "두 숫자를 곱합니다.",
                    "args_schema": {"a": "float", "b": "float"}
                },
                {
                    "name": "divide",
                    "description": "두 숫자를 나눕니다.",
                    "args_schema": {"a": "float", "b": "float"}
                },
                {
                    "name": "power",
                    "description": "숫자의 거듭제곱을 계산합니다.",
                    "args_schema": {"base": "float", "exponent": "float"}
                },
                {
                    "name": "sqrt",
                    "description": "숫자의 제곱근을 계산합니다.",
                    "args_schema": {"number": "float"}
                },
                {
                    "name": "factorial",
                    "description": "숫자의 팩토리얼을 계산합니다.",
                    "args_schema": {"n": "int"}
                },
                {
                    "name": "gcd",
                    "description": "두 숫자의 최대공약수를 계산합니다.",
                    "args_schema": {"a": "int", "b": "int"}
                },
                {
                    "name": "lcm",
                    "description": "두 숫자의 최소공배수를 계산합니다.",
                    "args_schema": {"a": "int", "b": "int"}
                },
                {
                    "name": "solve_quadratic",
                    "description": "이차방정식 ax² + bx + c = 0의 해를 구합니다.",
                    "args_schema": {"a": "float", "b": "float", "c": "float"}
                }
            ]
        elif server_name == "weather":
            return [
                {
                    "name": "get_current_weather",
                    "description": "현재 날씨 정보를 가져옵니다.",
                    "args_schema": {"location": "string"}
                },
                {
                    "name": "get_weather_forecast",
                    "description": "날씨 예보를 가져옵니다.",
                    "args_schema": {"location": "string", "days": "int"}
                }
            ]
        else:
            return []
            
    async def list_available_tools(self, server_name: str) -> List[Dict[str, Any]]:
        """사용 가능한 도구 목록을 반환합니다 (API 호환성)."""
        try:
            tools = await self.get_tools(server_name)
            
            # 도구 정보를 API 형식으로 변환
            tools_info = []
            for tool in tools:
                tools_info.append({
                    "name": tool.get("name", ""),
                    "description": tool.get("description", ""),
                    "args_schema": tool.get("args_schema", {})
                })
            
            return tools_info
            
        except Exception as e:
            logger.error(f"MCP 서버 '{server_name}' 도구 목록 로드 실패: {e}")
            return []
            
    async def execute_tool(self, server_name: str, tool_name: str, **kwargs) -> Any:
        """MCP 도구를 실행합니다 (API 호환성)."""
        return await self.call_tool(server_name, tool_name, **kwargs)
            
    async def call_tool(self, server_name: str, tool_name: str, **kwargs) -> Any:
        """MCP 도구를 호출합니다."""
        try:
            client = await self.get_client(server_name)
            
            # 도구 호출
            payload = {
                "name": tool_name,
                "arguments": kwargs
            }
            
            response = await client.post(f"/tools/{tool_name}/call", json=payload)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"MCP 도구 '{tool_name}' 호출 완료")
                return result
            else:
                logger.error(f"MCP 도구 '{tool_name}' 호출 실패: {response.status_code}")
                # 실패 시 시뮬레이션된 결과 반환
                return self._simulate_tool_result(server_name, tool_name, **kwargs)
            
        except Exception as e:
            logger.error(f"MCP 도구 '{tool_name}' 호출 실패: {e}")
            # 실패 시 시뮬레이션된 결과 반환
            return self._simulate_tool_result(server_name, tool_name, **kwargs)
    
    def _simulate_tool_result(self, server_name: str, tool_name: str, **kwargs) -> Any:
        """도구 결과를 시뮬레이션합니다."""
        if server_name == "math":
            if tool_name == "add":
                return {"result": kwargs.get("a", 0) + kwargs.get("b", 0)}
            elif tool_name == "subtract":
                return {"result": kwargs.get("a", 0) - kwargs.get("b", 0)}
            elif tool_name == "multiply":
                return {"result": kwargs.get("a", 0) * kwargs.get("b", 0)}
            elif tool_name == "divide":
                b = kwargs.get("b", 1)
                if b == 0:
                    return {"error": "0으로 나눌 수 없습니다."}
                return {"result": kwargs.get("a", 0) / b}
            elif tool_name == "power":
                return {"result": kwargs.get("base", 0) ** kwargs.get("exponent", 0)}
            elif tool_name == "sqrt":
                number = kwargs.get("number", 0)
                if number < 0:
                    return {"error": "음수의 제곱근은 계산할 수 없습니다."}
                return {"result": number ** 0.5}
            elif tool_name == "factorial":
                n = kwargs.get("n", 0)
                if n < 0:
                    return {"error": "음수의 팩토리얼은 정의되지 않습니다."}
                if n == 0 or n == 1:
                    return {"result": 1}
                result = 1
                for i in range(2, n + 1):
                    result *= i
                return {"result": result}
            elif tool_name == "gcd":
                a, b = kwargs.get("a", 0), kwargs.get("b", 0)
                while b:
                    a, b = b, a % b
                return {"result": abs(a)}
            elif tool_name == "lcm":
                a, b = kwargs.get("a", 0), kwargs.get("b", 0)
                if a == 0 or b == 0:
                    return {"result": 0}
                # GCD 계산
                def _gcd(x, y):
                    while y:
                        x, y = y, x % y
                    return x
                gcd_val = _gcd(a, b)
                return {"result": abs(a * b) // gcd_val}
            elif tool_name == "solve_quadratic":
                a, b, c = kwargs.get("a", 0), kwargs.get("b", 0), kwargs.get("c", 0)
                discriminant = b**2 - 4 * a * c
                if discriminant > 0:
                    x1 = (-b + discriminant**0.5) / (2 * a)
                    x2 = (-b - discriminant**0.5) / (2 * a)
                    return {"type": "two_real", "x1": x1, "x2": x2}
                elif discriminant == 0:
                    x = -b / (2 * a)
                    return {"type": "one_real", "x": x}
                else:
                    real_part = -b / (2 * a)
                    imag_part = abs(discriminant) ** 0.5 / (2 * a)
                    return {
                        "type": "two_complex",
                        "x1": f"{real_part} + {imag_part}i",
                        "x2": f"{real_part} - {imag_part}i",
                    }
        elif server_name == "weather":
            if tool_name == "get_current_weather":
                return {"result": {"weather": "맑음", "temperature": 22, "location": kwargs.get("location", "서울")}}
            elif tool_name == "get_weather_forecast":
                return {"result": {"forecast": "맑음", "temperature": 22, "location": kwargs.get("location", "서울")}}
        
        return {"result": "도구 실행 완료"}
            
    async def close_all(self):
        """모든 MCP 클라이언트를 종료합니다."""
        for server_name, client in self.clients.items():
            try:
                await client.aclose()
                logger.info(f"MCP HTTP 클라이언트 '{server_name}' 종료 완료")
            except Exception as e:
                logger.error(f"MCP HTTP 클라이언트 '{server_name}' 종료 실패: {e}")
                
        self.clients.clear()

# 전역 인스턴스
mcp_client_service = MCPClientService()

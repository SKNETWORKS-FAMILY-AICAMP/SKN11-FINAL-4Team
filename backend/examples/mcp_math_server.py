#!/usr/bin/env python3
"""
MCP 수학 서버 예제
간단한 수학 계산 도구들을 제공하는 HTTP 서버
"""

import os
import sys
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI 앱 생성
app = FastAPI(title="Math Server", version="1.0.0")

# 도구 정의
class ToolRequest(BaseModel):
    name: str
    arguments: Dict[str, Any]

class ToolResponse(BaseModel):
    result: Any
    error: str = None

# 수학 도구들
async def add(a: float, b: float) -> float:
    """두 숫자를 더합니다."""
    result = a + b
    logger.info(f"add({a}, {b}) = {result}")
    return result

async def subtract(a: float, b: float) -> float:
    """두 숫자를 뺍니다."""
    result = a - b
    logger.info(f"subtract({a}, {b}) = {result}")
    return result

async def multiply(a: float, b: float) -> float:
    """두 숫자를 곱합니다."""
    result = a * b
    logger.info(f"multiply({a}, {b}) = {result}")
    return result

async def divide(a: float, b: float) -> float:
    """두 숫자를 나눕니다. b가 0이 아닌지 확인합니다."""
    if b == 0:
        raise ValueError("0으로 나눌 수 없습니다.")
    result = a / b
    logger.info(f"divide({a}, {b}) = {result}")
    return result

async def power(base: float, exponent: float) -> float:
    """숫자의 거듭제곱을 계산합니다."""
    result = base**exponent
    logger.info(f"power({base}, {exponent}) = {result}")
    return result

async def sqrt(number: float) -> float:
    """숫자의 제곱근을 계산합니다."""
    if number < 0:
        raise ValueError("음수의 제곱근은 계산할 수 없습니다.")
    result = number**0.5
    logger.info(f"sqrt({number}) = {result}")
    return result

async def factorial(n: int) -> int:
    """숫자의 팩토리얼을 계산합니다."""
    if n < 0:
        raise ValueError("음수의 팩토리얼은 정의되지 않습니다.")
    if n == 0 or n == 1:
        return 1
    result = 1
    for i in range(2, n + 1):
        result *= i
    logger.info(f"factorial({n}) = {result}")
    return result

async def gcd(a: int, b: int) -> int:
    """두 숫자의 최대공약수를 계산합니다."""
    def _gcd(x: int, y: int) -> int:
        while y:
            x, y = y, x % y
        return x
    result = _gcd(abs(a), abs(b))
    logger.info(f"gcd({a}, {b}) = {result}")
    return result

async def lcm(a: int, b: int) -> int:
    """두 숫자의 최소공배수를 계산합니다."""
    def _gcd(x: int, y: int) -> int:
        while y:
            x, y = y, x % y
        return x
    if a == 0 or b == 0:
        return 0
    result = abs(a * b) // _gcd(a, b)
    logger.info(f"lcm({a}, {b}) = {result}")
    return result

async def solve_quadratic(a: float, b: float, c: float) -> dict:
    """이차방정식 ax² + bx + c = 0의 해를 구합니다."""
    discriminant = b**2 - 4 * a * c
    if discriminant > 0:
        x1 = (-b + discriminant**0.5) / (2 * a)
        x2 = (-b - discriminant**0.5) / (2 * a)
        result = {"type": "two_real", "x1": x1, "x2": x2}
    elif discriminant == 0:
        x = -b / (2 * a)
        result = {"type": "one_real", "x": x}
    else:
        real_part = -b / (2 * a)
        imag_part = abs(discriminant) ** 0.5 / (2 * a)
        result = {
            "type": "two_complex",
            "x1": f"{real_part} + {imag_part}i",
            "x2": f"{real_part} - {imag_part}i",
        }
    logger.info(f"solve_quadratic({a}, {b}, {c}) = {result}")
    return result

# 도구 목록
TOOLS = {
    "add": {
        "name": "add",
        "description": "두 숫자를 더합니다.",
        "args_schema": {"a": "float", "b": "float"},
        "function": add
    },
    "subtract": {
        "name": "subtract",
        "description": "두 숫자를 뺍니다.",
        "args_schema": {"a": "float", "b": "float"},
        "function": subtract
    },
    "multiply": {
        "name": "multiply",
        "description": "두 숫자를 곱합니다.",
        "args_schema": {"a": "float", "b": "float"},
        "function": multiply
    },
    "divide": {
        "name": "divide",
        "description": "두 숫자를 나눕니다.",
        "args_schema": {"a": "float", "b": "float"},
        "function": divide
    },
    "power": {
        "name": "power",
        "description": "숫자의 거듭제곱을 계산합니다.",
        "args_schema": {"base": "float", "exponent": "float"},
        "function": power
    },
    "sqrt": {
        "name": "sqrt",
        "description": "숫자의 제곱근을 계산합니다.",
        "args_schema": {"number": "float"},
        "function": sqrt
    },
    "factorial": {
        "name": "factorial",
        "description": "숫자의 팩토리얼을 계산합니다.",
        "args_schema": {"n": "int"},
        "function": factorial
    },
    "gcd": {
        "name": "gcd",
        "description": "두 숫자의 최대공약수를 계산합니다.",
        "args_schema": {"a": "int", "b": "int"},
        "function": gcd
    },
    "lcm": {
        "name": "lcm",
        "description": "두 숫자의 최소공배수를 계산합니다.",
        "args_schema": {"a": "int", "b": "int"},
        "function": lcm
    },
    "solve_quadratic": {
        "name": "solve_quadratic",
        "description": "이차방정식 ax² + bx + c = 0의 해를 구합니다.",
        "args_schema": {"a": "float", "b": "float", "c": "float"},
        "function": solve_quadratic
    }
}

@app.get("/")
async def root():
    return {"message": "Math Server is running"}

@app.get("/tools")
async def get_tools():
    """사용 가능한 도구 목록을 반환합니다."""
    tools_list = []
    for tool_name, tool_info in TOOLS.items():
        tools_list.append({
            "name": tool_info["name"],
            "description": tool_info["description"],
            "args_schema": tool_info["args_schema"]
        })
    return tools_list

@app.post("/tools/{tool_name}/call")
async def call_tool(tool_name: str, request: ToolRequest):
    """도구를 호출합니다."""
    if tool_name not in TOOLS:
        raise HTTPException(status_code=404, detail=f"Tool {tool_name} not found")
    
    try:
        tool_info = TOOLS[tool_name]
        result = await tool_info["function"](**request.arguments)
        return {"result": result}
    except Exception as e:
        logger.error(f"Tool {tool_name} execution failed: {e}")
        return {"error": str(e)}

@app.get("/health")
async def health_check():
    """서버 상태를 확인합니다."""
    return {"status": "healthy", "server": "Math Server"}

if __name__ == "__main__":
    import uvicorn
    import os
    
    # 환경변수 설정
    port = int(os.environ.get("MCP_PORT", 8003))
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    
    print(f"Math Server를 포트 {port}에서 시작합니다...")
    print(f"MCP_PORT: {port}")
    print(f"MCP_HOST: {host}")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )

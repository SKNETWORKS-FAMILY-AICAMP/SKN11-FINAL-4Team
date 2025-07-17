#!/usr/bin/env python3
"""
MCP 수학 서버 예제
간단한 수학 계산 도구들을 제공하는 MCP 서버
"""

from mcp.server.fastmcp import FastMCP
from mcp.server.models import InitializationOptions
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastMCP 서버 생성
mcp = FastMCP("Math Server")


@mcp.tool()
async def add(a: float, b: float) -> float:
    """두 숫자를 더합니다."""
    result = a + b
    logger.info(f"add({a}, {b}) = {result}")
    return result


@mcp.tool()
async def subtract(a: float, b: float) -> float:
    """두 숫자를 뺍니다."""
    result = a - b
    logger.info(f"subtract({a}, {b}) = {result}")
    return result


@mcp.tool()
async def multiply(a: float, b: float) -> float:
    """두 숫자를 곱합니다."""
    result = a * b
    logger.info(f"multiply({a}, {b}) = {result}")
    return result


@mcp.tool()
async def divide(a: float, b: float) -> float:
    """두 숫자를 나눕니다. b가 0이 아닌지 확인합니다."""
    if b == 0:
        raise ValueError("0으로 나눌 수 없습니다.")
    result = a / b
    logger.info(f"divide({a}, {b}) = {result}")
    return result


@mcp.tool()
async def power(base: float, exponent: float) -> float:
    """숫자의 거듭제곱을 계산합니다."""
    result = base**exponent
    logger.info(f"power({base}, {exponent}) = {result}")
    return result


@mcp.tool()
async def sqrt(number: float) -> float:
    """숫자의 제곱근을 계산합니다."""
    if number < 0:
        raise ValueError("음수의 제곱근은 계산할 수 없습니다.")
    result = number**0.5
    logger.info(f"sqrt({number}) = {result}")
    return result


@mcp.tool()
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


@mcp.tool()
async def gcd(a: int, b: int) -> int:
    """두 숫자의 최대공약수를 계산합니다."""

    def _gcd(x: int, y: int) -> int:
        while y:
            x, y = y, x % y
        return x

    result = _gcd(abs(a), abs(b))
    logger.info(f"gcd({a}, {b}) = {result}")
    return result


@mcp.tool()
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


@mcp.tool()
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


if __name__ == "__main__":
    # 서버 실행
    mcp.run(transport="stdio")

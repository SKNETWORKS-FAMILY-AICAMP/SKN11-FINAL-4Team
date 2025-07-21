"""
MCP Math Server - FastMCP 사용
"""

import logging
import re
from typing import Dict, Any
from mcp.server.fastmcp import FastMCP

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastMCP 서버 생성
mcp = FastMCP("Math")


def _extract_numbers_from_params(params: Dict[str, Any], message: str = "") -> tuple:
    """매개변수에서 숫자를 추출합니다."""
    a_value = None
    b_value = None

    # VLLM이 추출한 매개변수 처리
    if "numbers" in params and "value" in params:
        try:
            a_value = float(params["numbers"])
            b_value = float(params["value"])
        except (ValueError, TypeError):
            pass

    # 직접 숫자 매개변수 처리
    elif "a" in params and "b" in params:
        try:
            a_value = float(params["a"])
            b_value = float(params["b"])
        except (ValueError, TypeError):
            pass

    # 메시지에서 숫자 추출
    if a_value is None or b_value is None:
        numbers = re.findall(r"\d+", message)
        if len(numbers) >= 2:
            try:
                a_value = float(numbers[0])
                b_value = float(numbers[1])
            except (ValueError, TypeError):
                pass

    return a_value, b_value


@mcp.tool()
async def add(a: float = None, b: float = None) -> str:
    """두 숫자를 더합니다."""
    # 매개변수 변환
    import inspect

    frame = inspect.currentframe()
    local_vars = frame.f_back.f_locals if frame and frame.f_back else {}
    message = local_vars.get("message", "")
    if a is None or b is None:
        from typing import Dict

        def _extract_numbers_from_params(params: Dict, message: str = ""):
            import re

            a_value = None
            b_value = None
            if "numbers" in params and "number" in params:
                try:
                    a_value = float(params["numbers"])
                    b_value = float(params["number"])
                except (ValueError, TypeError):
                    pass
            if a_value is None or b_value is None:
                numbers = re.findall(r"\d+", message)
                if len(numbers) >= 2:
                    try:
                        a_value = float(numbers[0])
                        b_value = float(numbers[1])
                    except (ValueError, TypeError):
                        pass
            return a_value, b_value

        a_val, b_val = _extract_numbers_from_params(local_vars, message)
        a = a_val if a is None else a
        b = b_val if b is None else b
    if a is None:
        a = 0
    if b is None:
        b = 0
    result = a + b
    return f"🔢 계산 결과: {a} + {b} = {result}"


@mcp.tool()
async def subtract(a: float = None, b: float = None) -> str:
    """두 숫자를 뺍니다."""
    # 매개변수 변환
    import inspect

    frame = inspect.currentframe()
    local_vars = frame.f_back.f_locals if frame and frame.f_back else {}
    message = local_vars.get("message", "")
    if a is None or b is None:
        from typing import Dict

        def _extract_numbers_from_params(params: Dict, message: str = ""):
            import re

            a_value = None
            b_value = None
            if "numbers" in params and "number" in params:
                try:
                    a_value = float(params["numbers"])
                    b_value = float(params["number"])
                except (ValueError, TypeError):
                    pass
            if a_value is None or b_value is None:
                numbers = re.findall(r"\d+", message)
                if len(numbers) >= 2:
                    try:
                        a_value = float(numbers[0])
                        b_value = float(numbers[1])
                    except (ValueError, TypeError):
                        pass
            return a_value, b_value

        a_val, b_val = _extract_numbers_from_params(local_vars, message)
        a = a_val if a is None else a
        b = b_val if b is None else b
    if a is None:
        a = 0
    if b is None:
        b = 0
    result = a - b
    return f"🔢 계산 결과: {a} - {b} = {result}"


@mcp.tool()
async def multiply(a: float = None, b: float = None) -> str:
    """두 숫자를 곱합니다."""
    # 매개변수 변환
    import inspect

    frame = inspect.currentframe()
    local_vars = frame.f_back.f_locals if frame and frame.f_back else {}
    message = local_vars.get("message", "")
    if a is None or b is None:
        from typing import Dict

        def _extract_numbers_from_params(params: Dict, message: str = ""):
            import re

            a_value = None
            b_value = None
            if "numbers" in params and "number" in params:
                try:
                    a_value = float(params["numbers"])
                    b_value = float(params["number"])
                except (ValueError, TypeError):
                    pass
            if a_value is None or b_value is None:
                numbers = re.findall(r"\d+", message)
                if len(numbers) >= 2:
                    try:
                        a_value = float(numbers[0])
                        b_value = float(numbers[1])
                    except (ValueError, TypeError):
                        pass
            return a_value, b_value

        a_val, b_val = _extract_numbers_from_params(local_vars, message)
        a = a_val if a is None else a
        b = b_val if b is None else b
    if a is None:
        a = 0
    if b is None:
        b = 0
    result = a * b
    return f"🔢 계산 결과: {a} × {b} = {result}"


@mcp.tool()
async def divide(a: float = None, b: float = None) -> str:
    """두 숫자를 나눕니다."""
    # 매개변수 변환
    import inspect

    frame = inspect.currentframe()
    local_vars = frame.f_back.f_locals if frame and frame.f_back else {}
    message = local_vars.get("message", "")
    if a is None or b is None:
        from typing import Dict

        def _extract_numbers_from_params(params: Dict, message: str = ""):
            import re

            a_value = None
            b_value = None
            if "numbers" in params and "number" in params:
                try:
                    a_value = float(params["numbers"])
                    b_value = float(params["number"])
                except (ValueError, TypeError):
                    pass
            if a_value is None or b_value is None:
                numbers = re.findall(r"\d+", message)
                if len(numbers) >= 2:
                    try:
                        a_value = float(numbers[0])
                        b_value = float(numbers[1])
                    except (ValueError, TypeError):
                        pass
            return a_value, b_value

        a_val, b_val = _extract_numbers_from_params(local_vars, message)
        a = a_val if a is None else a
        b = b_val if b is None else b
    if a is None:
        a = 0
    if b is None:
        b = 1
    if b == 0:
        return "❌ 오류: 0으로 나눌 수 없습니다."
    result = a / b
    return f"🔢 계산 결과: {a} ÷ {b} = {result}"


@mcp.tool()
async def power(base: float = None, exponent: float = None, **kwargs) -> float:
    """숫자의 거듭제곱을 계산합니다."""
    # 매개변수 변환
    if base is None or exponent is None:
        a_val, b_val = _extract_numbers_from_params(kwargs, kwargs.get("message", ""))
        base = a_val if base is None else base
        exponent = b_val if exponent is None else exponent

    # 기본값 설정
    if base is None:
        base = 0
    if exponent is None:
        exponent = 0

    logger.info(f"🔢 power 도구 실행: {base} ^ {exponent}")
    result = base**exponent
    logger.info(f"✅ 결과: {result}")
    return result


@mcp.tool()
async def sqrt(number: float = None, **kwargs) -> float:
    """숫자의 제곱근을 계산합니다."""
    # 매개변수 변환
    if number is None:
        a_val, _ = _extract_numbers_from_params(kwargs, kwargs.get("message", ""))
        number = a_val

    # 기본값 설정
    if number is None:
        number = 0

    if number < 0:
        raise ValueError("음수의 제곱근은 계산할 수 없습니다.")

    logger.info(f"🔢 sqrt 도구 실행: √{number}")
    result = number**0.5
    logger.info(f"✅ 결과: {result}")
    return result


@mcp.tool()
async def factorial(n: int = None, **kwargs) -> int:
    """숫자의 팩토리얼을 계산합니다."""
    # 매개변수 변환
    if n is None:
        a_val, _ = _extract_numbers_from_params(kwargs, kwargs.get("message", ""))
        n = int(a_val) if a_val is not None else None

    # 기본값 설정
    if n is None:
        n = 0

    if n < 0:
        raise ValueError("음수의 팩토리얼은 정의되지 않습니다.")
    if n == 0 or n == 1:
        return 1

    logger.info(f"🔢 factorial 도구 실행: {n}!")
    result = 1
    for i in range(2, n + 1):
        result *= i
    logger.info(f"✅ 결과: {result}")
    return result


@mcp.tool()
async def gcd(a: int = None, b: int = None, **kwargs) -> int:
    """두 숫자의 최대공약수를 계산합니다."""
    # 매개변수 변환
    if a is None or b is None:
        a_val, b_val = _extract_numbers_from_params(kwargs, kwargs.get("message", ""))
        a = int(a_val) if a_val is not None else a
        b = int(b_val) if b_val is not None else b

    # 기본값 설정
    if a is None:
        a = 0
    if b is None:
        b = 0

    logger.info(f"🔢 gcd 도구 실행: gcd({a}, {b})")
    while b:
        a, b = b, a % b
    result = abs(a)
    logger.info(f"✅ 결과: {result}")
    return result


@mcp.tool()
async def lcm(a: int = None, b: int = None, **kwargs) -> int:
    """두 숫자의 최소공배수를 계산합니다."""
    # 매개변수 변환
    if a is None or b is None:
        a_val, b_val = _extract_numbers_from_params(kwargs, kwargs.get("message", ""))
        a = int(a_val) if a_val is not None else a
        b = int(b_val) if b_val is not None else b

    # 기본값 설정
    if a is None:
        a = 0
    if b is None:
        b = 0

    if a == 0 or b == 0:
        return 0

    # GCD 계산
    def _gcd(x: int, y: int) -> int:
        while y:
            x, y = y, x % y
        return x

    logger.info(f"🔢 lcm 도구 실행: lcm({a}, {b})")
    gcd_val = _gcd(a, b)
    result = abs(a * b) // gcd_val
    logger.info(f"✅ 결과: {result}")
    return result


@mcp.tool()
async def solve_quadratic(
    a: float = None, b: float = None, c: float = None, **kwargs
) -> dict:
    """이차방정식 ax² + bx + c = 0을 풉니다."""
    # 매개변수 변환
    if a is None or b is None or c is None:
        a_val, b_val = _extract_numbers_from_params(kwargs, kwargs.get("message", ""))
        if a is None:
            a = a_val if a_val is not None else 1
        if b is None:
            b = b_val if b_val is not None else 0
        if c is None:
            c = 0  # 기본값

    # 기본값 설정
    if a is None:
        a = 1
    if b is None:
        b = 0
    if c is None:
        c = 0

    logger.info(f"🔢 solve_quadratic 도구 실행: {a}x² + {b}x + {c} = 0")

    discriminant = b**2 - 4 * a * c

    if discriminant > 0:
        x1 = (-b + discriminant**0.5) / (2 * a)
        x2 = (-b - discriminant**0.5) / (2 * a)
        result = {"x1": x1, "x2": x2, "type": "two_real_roots"}
    elif discriminant == 0:
        x = -b / (2 * a)
        result = {"x": x, "type": "one_real_root"}
    else:
        real_part = -b / (2 * a)
        imaginary_part = abs(discriminant) ** 0.5 / (2 * a)
        result = {
            "x1": f"{real_part} + {imaginary_part}i",
            "x2": f"{real_part} - {imaginary_part}i",
            "type": "complex_roots",
        }

    logger.info(f"✅ 결과: {result}")
    return result


if __name__ == "__main__":
    import os
    import uvicorn

    # 환경변수 설정
    port = int(os.environ.get("MCP_PORT", 8003))
    host = os.environ.get("MCP_HOST", "0.0.0.0")

    print(f"Math Server를 포트 {port}에서 시작합니다...")
    print(f"MCP_PORT: {port}")
    print(f"MCP_HOST: {host}")

    # FastMCP 서버를 uvicorn으로 실행 (올바른 속성 사용)
    uvicorn.run(mcp.streamable_http_app, host=host, port=port)

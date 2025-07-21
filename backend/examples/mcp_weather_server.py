"""
MCP Weather Server - FastMCP 사용
"""

import logging
from typing import Dict, Any
from mcp.server.fastmcp import FastMCP

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastMCP 서버 생성
mcp = FastMCP("Weather")


@mcp.tool()
async def get_current_weather(location: str) -> str:
    """지정된 위치의 현재 날씨 정보를 가져옵니다."""
    # 실제 구현에서는 날씨 API를 호출합니다
    # 여기서는 시뮬레이션된 데이터를 반환합니다
    weather_data = {
        "location": location,
        "temperature": 22,
        "condition": "맑음",
        "humidity": 65,
        "wind_speed": 10,
    }

    # 사용자 친화적인 결과 포맷팅
    formatted_result = f"""🌤️ {location} 현재 날씨
• 기온: {weather_data['temperature']}°C
• 날씨: {weather_data['condition']}
• 습도: {weather_data['humidity']}%
• 풍속: {weather_data['wind_speed']}km/h"""

    logger.info(f"✅ 날씨 정보 반환: {location}")
    return formatted_result


@mcp.tool()
async def get_weather_forecast(location: str, days: int = 5) -> str:
    """지정된 위치의 날씨 예보를 가져옵니다."""
    # 실제 구현에서는 날씨 API를 호출합니다
    # 여기서는 시뮬레이션된 데이터를 반환합니다
    forecast_data = {
        "location": location,
        "forecast_days": days,
        "forecast": [
            {
                "date": "2024-01-15",
                "temperature": {"min": 15, "max": 25},
                "condition": "맑음",
                "humidity": 60,
            },
            {
                "date": "2024-01-16",
                "temperature": {"min": 12, "max": 22},
                "condition": "흐림",
                "humidity": 70,
            },
            {
                "date": "2024-01-17",
                "temperature": {"min": 10, "max": 20},
                "condition": "비",
                "humidity": 85,
            },
        ],
    }

    # 사용자 친화적인 결과 포맷팅
    formatted_result = f"🌤️ {location} {days}일 날씨 예보\n\n"
    for day in forecast_data["forecast"]:
        formatted_result += f"📅 {day['date']}\n"
        formatted_result += f"   • 기온: {day['temperature']['min']}°C ~ {day['temperature']['max']}°C\n"
        formatted_result += f"   • 날씨: {day['condition']}\n"
        formatted_result += f"   • 습도: {day['humidity']}%\n\n"

    logger.info(f"✅ 날씨 예보 반환: {location}, {days}일")
    return formatted_result


@mcp.tool()
async def get_air_quality(location: str) -> str:
    """지정된 위치의 대기질 정보를 가져옵니다."""
    # 실제 구현에서는 대기질 API를 호출합니다
    air_quality_data = {
        "location": location,
        "aqi": 45,
        "level": "좋음",
        "pm25": 12,
        "pm10": 25,
    }

    # 사용자 친화적인 결과 포맷팅
    formatted_result = f"""🌬️ {location} 대기질 정보
• 대기질 지수: {air_quality_data['aqi']} ({air_quality_data['level']})
• 미세먼지(PM2.5): {air_quality_data['pm25']}㎍/㎥
• 미세먼지(PM10): {air_quality_data['pm10']}㎍/㎥"""

    logger.info(f"✅ 대기질 정보 반환: {location}")
    return formatted_result


@mcp.tool()
async def get_uv_index(location: str) -> str:
    """지정된 위치의 자외선 지수를 가져옵니다."""
    # 실제 구현에서는 자외선 지수 API를 호출합니다
    uv_data = {
        "location": location,
        "uv_index": 3,
        "level": "보통",
        "recommendation": "자외선 차단제 사용을 권장합니다.",
    }

    # 사용자 친화적인 결과 포맷팅
    formatted_result = f"""☀️ {location} 자외선 지수
• 자외선 지수: {uv_data['uv_index']} ({uv_data['level']})
• 권장사항: {uv_data['recommendation']}"""

    logger.info(f"✅ 자외선 지수 반환: {location}")
    return formatted_result


if __name__ == "__main__":
    import os
    import uvicorn

    # 환경변수 설정
    port = int(os.environ.get("MCP_PORT", 8005))
    host = os.environ.get("MCP_HOST", "0.0.0.0")

    print(f"Weather Server를 포트 {port}에서 시작합니다...")
    print(f"MCP_PORT: {port}")
    print(f"MCP_HOST: {host}")

    # FastMCP 서버를 uvicorn으로 실행 (올바른 속성 사용)
    uvicorn.run(mcp.streamable_http_app, host=host, port=port)

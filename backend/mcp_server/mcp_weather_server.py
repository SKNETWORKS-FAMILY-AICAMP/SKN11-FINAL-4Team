"""
MCP Weather Server - FastMCP 사용
"""

import logging
from typing import Dict, Any, List
from mcp.server.fastmcp import FastMCP
import httpx
import asyncio
from datetime import datetime, timedelta
import random

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastMCP 서버 생성
mcp = FastMCP("Weather")

import os

# 날씨 API 설정 (OpenWeatherMap 사용 예시)
WEATHER_API_KEY = os.environ.get("WEATHER_API_KEY", "")  # 환경변수에서 API 키 가져오기
WEATHER_BASE_URL = "http://api.openweathermap.org/data/2.5"

# API 키 상태 로깅
if WEATHER_API_KEY:
    logger.info(f"[날씨] WEATHER_API_KEY 설정됨: {WEATHER_API_KEY[:8]}...")
else:
    logger.warning(
        "[날씨] WEATHER_API_KEY가 설정되지 않았습니다. 시뮬레이션 모드로 실행됩니다."
    )
    logger.info("[날씨] 환경변수 설정 방법: export WEATHER_API_KEY='your_api_key_here'")


async def get_real_weather_data(location: str) -> Dict[str, Any]:
    """실제 날씨 API에서 데이터를 가져옵니다."""
    # API 키가 없으면 시뮬레이션 모드
    if not WEATHER_API_KEY:
        logger.info(
            "[날씨] WEATHER_API_KEY가 설정되지 않아 시뮬레이션 모드로 실행됩니다."
        )
        return None

    try:
        # OpenWeatherMap API 호출
        url = f"{WEATHER_BASE_URL}/weather"
        params = {
            "q": location,
            "appid": WEATHER_API_KEY,
            "units": "metric",
            "lang": "kr",
        }

        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                return {
                    "temperature": data["main"]["temp"],
                    "condition": data["weather"][0]["description"],
                    "humidity": data["main"]["humidity"],
                    "wind_speed": data["wind"]["speed"],
                    "pressure": data["main"]["pressure"],
                }
            else:
                logger.warning(f"날씨 API 호출 실패: {response.status_code}")
                return None
    except Exception as e:
        logger.error(f"날씨 API 호출 중 오류: {e}")
        return None


# 시뮬레이션/랜덤/가짜 날씨 데이터 생성 코드 전체 삭제
# 실제 API 실패 시 에러 메시지 반환만 남김


@mcp.tool()
async def get_current_weather(location: str = "서울") -> str:
    """지정된 위치의 현재 날씨 정보를 가져옵니다."""
    try:
        if not location or location.strip() == "":
            location = "서울"
        weather_data = await get_real_weather_data(location)
        if weather_data:
            temp_desc = (
                "따뜻한"
                if weather_data["temperature"] > 20
                else "시원한" if weather_data["temperature"] > 10 else "쌀쌀한"
            )
            response = f"오늘 {location} 날씨는 {weather_data['condition']}이고, 기온은 {weather_data['temperature']}°C로 {temp_desc} 날씨야."
            return response
        else:
            return f"죄송합니다. 현재 {location}의 날씨 정보를 가져올 수 없습니다. 잠시 후 다시 시도해 주세요."
    except Exception as e:
        logger.error(f"날씨 정보 가져오기 실패: {e}")
        return f"죄송합니다! {location} 날씨 정보를 가져오는 중에 오류가 발생했어요. 잠시 후에 다시 시도해보시겠어요?"


@mcp.tool()
async def get_weather_forecast(location: str = "서울", days: int = 5) -> str:
    """지정된 위치의 날씨 예보를 가져옵니다."""
    try:
        if not location or location.strip() == "":
            location = "서울"
        # 실제 날씨 예보 API 호출 시도
        # (실제 API 연동이 구현되어 있지 않으면 무조건 실패)
        return f"죄송합니다. 현재 {location}의 날씨 예보 정보를 가져올 수 없습니다. 잠시 후 다시 시도해 주세요."
    except Exception as e:
        logger.error(f"날씨 예보 가져오기 실패: {e}")
        return f"죄송해요! {location}의 날씨 예보를 가져올 수 없어요. 예보 서비스에 일시적인 문제가 있는 것 같네요. 잠시 후에 다시 시도해보시겠어요?"


@mcp.tool()
async def get_air_quality(location: str = "서울") -> str:
    """지정된 위치의 대기질 정보를 가져옵니다."""
    try:
        if not location or location.strip() == "":
            location = "서울"
        url = f"{WEATHER_BASE_URL}/air_pollution"
        params = {"q": location, "appid": WEATHER_API_KEY}
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                aqi = data["list"][0]["main"]["aqi"]
                components = data["list"][0]["components"]
                aqi_levels = {
                    1: "좋음",
                    2: "보통",
                    3: "나쁨",
                    4: "매우 나쁨",
                    5: "위험",
                }
                level = aqi_levels.get(aqi, "알 수 없음")
                response = f"{location}의 대기질은 {level} 상태입니다."
                return response
            else:
                return f"죄송합니다. 현재 {location}의 대기질 정보를 가져올 수 없습니다. 잠시 후 다시 시도해 주세요."
    except Exception as e:
        logger.error(f"대기질 정보 가져오기 실패: {e}")
        return f"죄송해요! {location}의 대기질 정보를 가져오는 중에 오류가 발생했어요. 잠시 후에 다시 시도해보시겠어요?"


@mcp.tool()
async def get_uv_index(location: str = "서울") -> str:
    """지정된 위치의 자외선 지수를 가져옵니다."""
    try:
        if not location or location.strip() == "":
            location = "서울"
        url = f"{WEATHER_BASE_URL}/uvi"
        params = {"q": location, "appid": WEATHER_API_KEY}
        async with httpx.AsyncClient() as client:
            response = await client.get(url, params=params)
            if response.status_code == 200:
                data = response.json()
                uv_index = data["value"]
                if uv_index <= 2:
                    level = "낮음"
                elif uv_index <= 5:
                    level = "보통"
                elif uv_index <= 7:
                    level = "높음"
                elif uv_index <= 10:
                    level = "매우 높음"
                else:
                    level = "위험"
                response = (
                    f"{location}의 자외선 지수는 {uv_index}로 {level} 수준입니다."
                )
                return response
            else:
                return f"죄송합니다. 현재 {location}의 자외선 지수 정보를 가져올 수 없습니다. 잠시 후 다시 시도해 주세요."
    except Exception as e:
        logger.error(f"자외선 지수 가져오기 실패: {e}")
        return f"죄송해요! {location}의 자외선 지수를 가져오는 중에 오류가 발생했어요. 잠시 후에 다시 시도해보시겠어요?"


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(mcp.streamable_http_app, host="0.0.0.0", port=8005)

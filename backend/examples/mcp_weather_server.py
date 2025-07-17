#!/usr/bin/env python3
"""
MCP 날씨 서버 예제
날씨 정보를 제공하는 MCP 서버
"""

from mcp.server.fastmcp import FastMCP
from datetime import datetime, timedelta
import random
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastMCP 서버 생성
mcp = FastMCP("Weather Server")

# 가상의 날씨 데이터
WEATHER_DATA = {
    "서울": {"temp": 22, "condition": "맑음", "humidity": 45},
    "부산": {"temp": 25, "condition": "흐림", "humidity": 70},
    "대구": {"temp": 28, "condition": "맑음", "humidity": 40},
    "인천": {"temp": 20, "condition": "비", "humidity": 85},
    "광주": {"temp": 26, "condition": "맑음", "humidity": 50},
    "대전": {"temp": 24, "condition": "흐림", "humidity": 65},
    "울산": {"temp": 23, "condition": "맑음", "humidity": 55},
    "세종": {"temp": 21, "condition": "비", "humidity": 80},
    "제주": {"temp": 27, "condition": "맑음", "humidity": 60},
}


@mcp.tool()
async def get_current_weather(location: str) -> dict:
    """특정 지역의 현재 날씨 정보를 가져옵니다."""
    location = location.strip()

    if location in WEATHER_DATA:
        weather = WEATHER_DATA[location].copy()
        weather["location"] = location
        weather["timestamp"] = datetime.now().isoformat()
        logger.info(f"get_current_weather({location}) = {weather}")
        return weather
    else:
        # 알 수 없는 지역의 경우 랜덤 데이터 생성
        conditions = ["맑음", "흐림", "비", "눈", "안개"]
        weather = {
            "location": location,
            "temp": random.randint(15, 30),
            "condition": random.choice(conditions),
            "humidity": random.randint(30, 90),
            "timestamp": datetime.now().isoformat(),
        }
        logger.info(f"get_current_weather({location}) = {weather} (랜덤)")
        return weather


@mcp.tool()
async def get_weather_forecast(location: str, days: int = 5) -> dict:
    """특정 지역의 날씨 예보를 가져옵니다."""
    location = location.strip()

    forecast = []
    for i in range(days):
        date = datetime.now() + timedelta(days=i)
        conditions = ["맑음", "흐림", "비", "눈", "안개"]
        daily_forecast = {
            "date": date.strftime("%Y-%m-%d"),
            "temp_high": random.randint(20, 35),
            "temp_low": random.randint(10, 25),
            "condition": random.choice(conditions),
            "humidity": random.randint(30, 90),
            "precipitation_chance": random.randint(0, 100),
        }
        forecast.append(daily_forecast)

    result = {
        "location": location,
        "forecast": forecast,
        "generated_at": datetime.now().isoformat(),
    }

    logger.info(f"get_weather_forecast({location}, {days}) = {result}")
    return result


@mcp.tool()
async def get_air_quality(location: str) -> dict:
    """특정 지역의 대기질 정보를 가져옵니다."""
    location = location.strip()

    # 가상의 대기질 데이터
    aqi_levels = ["좋음", "보통", "나쁨", "매우나쁨"]
    aqi_values = random.randint(1, 500)

    if aqi_values <= 50:
        level = "좋음"
    elif aqi_values <= 100:
        level = "보통"
    elif aqi_values <= 150:
        level = "나쁨"
    else:
        level = "매우나쁨"

    air_quality = {
        "location": location,
        "aqi": aqi_values,
        "level": level,
        "pm10": random.randint(10, 100),
        "pm25": random.randint(5, 50),
        "timestamp": datetime.now().isoformat(),
    }

    logger.info(f"get_air_quality({location}) = {air_quality}")
    return air_quality


@mcp.tool()
async def get_uv_index(location: str) -> dict:
    """특정 지역의 자외선 지수를 가져옵니다."""
    location = location.strip()

    uv_value = random.randint(1, 11)

    if uv_value <= 2:
        level = "낮음"
        protection = "선글라스와 모자 권장"
    elif uv_value <= 5:
        level = "보통"
        protection = "자외선 차단제 사용 권장"
    elif uv_value <= 7:
        level = "높음"
        protection = "자외선 차단제 필수, 오후 시간대 외출 자제"
    elif uv_value <= 10:
        level = "매우높음"
        protection = "오후 시간대 외출 자제, 그늘에서 활동"
    else:
        level = "극도로높음"
        protection = "외출 자제, 실내 활동 권장"

    uv_info = {
        "location": location,
        "uv_index": uv_value,
        "level": level,
        "protection": protection,
        "timestamp": datetime.now().isoformat(),
    }

    logger.info(f"get_uv_index({location}) = {uv_info}")
    return uv_info


@mcp.tool()
async def get_wind_info(location: str) -> dict:
    """특정 지역의 바람 정보를 가져옵니다."""
    location = location.strip()

    wind_speed = random.randint(0, 30)
    wind_direction = random.choice(
        ["북", "북동", "동", "남동", "남", "남서", "서", "북서"]
    )

    if wind_speed <= 5:
        description = "약한 바람"
    elif wind_speed <= 10:
        description = "보통 바람"
    elif wind_speed <= 20:
        description = "강한 바람"
    else:
        description = "매우 강한 바람"

    wind_info = {
        "location": location,
        "speed": wind_speed,
        "direction": wind_direction,
        "description": description,
        "timestamp": datetime.now().isoformat(),
    }

    logger.info(f"get_wind_info({location}) = {wind_info}")
    return wind_info


@mcp.tool()
async def get_sunrise_sunset(location: str) -> dict:
    """특정 지역의 일출/일몰 시간을 가져옵니다."""
    location = location.strip()

    # 가상의 일출/일몰 시간
    sunrise_hour = random.randint(5, 7)
    sunrise_minute = random.randint(0, 59)
    sunset_hour = random.randint(17, 19)
    sunset_minute = random.randint(0, 59)

    sunrise_sunset = {
        "location": location,
        "sunrise": f"{sunrise_hour:02d}:{sunrise_minute:02d}",
        "sunset": f"{sunset_hour:02d}:{sunset_minute:02d}",
        "day_length": f"{sunset_hour - sunrise_hour}시간 {sunset_minute - sunrise_minute}분",
        "date": datetime.now().strftime("%Y-%m-%d"),
        "timestamp": datetime.now().isoformat(),
    }

    logger.info(f"get_sunrise_sunset({location}) = {sunrise_sunset}")
    return sunrise_sunset


if __name__ == "__main__":
    # 환경변수에서 포트 가져오기 (.env 파일의 MCP_PORT 사용)
    import os

    port = int(os.getenv("MCP_PORT", "8005"))

    # 환경변수로 포트 설정
    os.environ["MCP_PORT"] = str(port)
    os.environ["MCP_HOST"] = "0.0.0.0"

    print(f"Weather MCP 서버를 포트 {port}에서 시작합니다...")

    # 서버 실행 (streamable HTTP)
    mcp.run(transport="streamable-http")

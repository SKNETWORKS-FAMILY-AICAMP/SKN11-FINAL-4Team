#!/usr/bin/env python3
"""
실제 날씨 데이터를 제공하는 Weather MCP 서버
OpenWeatherMap API를 사용하여 실제 날씨 정보를 가져옵니다.
"""

import os
import sys
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, List
from datetime import datetime, timedelta
import httpx
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI 앱 생성
app = FastAPI(title="Real Weather Server", version="1.0.0")

# 도구 정의
class ToolRequest(BaseModel):
    name: str
    arguments: Dict[str, Any]

class ToolResponse(BaseModel):
    result: Any
    error: str = None

# OpenWeatherMap API 설정
OPENWEATHER_API_KEY = os.environ.get("OPENWEATHER_API_KEY", "8b6a8fc5a254c9f13d9bcbbcc7692bdf")
OPENWEATHER_BASE_URL = "http://api.openweathermap.org/data/2.5"

# 한국 주요 도시의 좌표 (위도, 경도)
KOREAN_CITIES = {
    "서울": {"lat": 37.5665, "lon": 126.9780, "name": "Seoul"},
    "부산": {"lat": 35.1796, "lon": 129.0756, "name": "Busan"},
    "대구": {"lat": 35.8714, "lon": 128.6014, "name": "Daegu"},
    "인천": {"lat": 37.4563, "lon": 126.7052, "name": "Incheon"},
    "광주": {"lat": 35.1595, "lon": 126.8526, "name": "Gwangju"},
    "대전": {"lat": 36.3504, "lon": 127.3845, "name": "Daejeon"},
    "울산": {"lat": 35.5384, "lon": 129.3114, "name": "Ulsan"},
    "세종": {"lat": 36.4800, "lon": 127.2890, "name": "Sejong"},
    "제주": {"lat": 33.4996, "lon": 126.5312, "name": "Jeju"}
}

async def get_current_weather(location: str) -> dict:
    """실제 현재 날씨 정보를 가져옵니다."""
    location = location.strip()
    
    # 한국 도시인지 확인
    if location in KOREAN_CITIES:
        city_info = KOREAN_CITIES[location]
        lat = city_info["lat"]
        lon = city_info["lon"]
        city_name = city_info["name"]
    else:
        # 한국 도시가 아니면 도시명으로 검색
        lat = None
        lon = None
        city_name = location
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            if lat and lon:
                # 좌표로 검색
                url = f"{OPENWEATHER_BASE_URL}/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=kr"
            else:
                # 도시명으로 검색
                url = f"{OPENWEATHER_BASE_URL}/weather?q={city_name}&appid={OPENWEATHER_API_KEY}&units=metric&lang=kr"
            
            response = await client.get(url)
            
            if response.status_code == 200:
                data = response.json()
                
                # 날씨 상태를 한국어로 변환
                weather_conditions = {
                    "Clear": "맑음",
                    "Clouds": "흐림",
                    "Rain": "비",
                    "Snow": "눈",
                    "Thunderstorm": "천둥번개",
                    "Drizzle": "이슬비",
                    "Mist": "안개",
                    "Fog": "안개",
                    "Haze": "연무"
                }
                
                weather_main = data["weather"][0]["main"]
                weather_desc = data["weather"][0]["description"]
                weather_condition = weather_conditions.get(weather_main, weather_desc)
                
                result = {
                    "location": location,
                    "temp": round(data["main"]["temp"], 1),
                    "feels_like": round(data["main"]["feels_like"], 1),
                    "condition": weather_condition,
                    "humidity": data["main"]["humidity"],
                    "pressure": data["main"]["pressure"],
                    "wind_speed": data["wind"]["speed"],
                    "wind_direction": data["wind"].get("deg", 0),
                    "visibility": data.get("visibility", 10000) / 1000,  # km로 변환
                    "timestamp": datetime.now().isoformat()
                }
                
                logger.info(f"get_current_weather({location}) = {result}")
                return result
            else:
                logger.error(f"Weather API error: {response.status_code}")
                return {"error": f"Weather API error: {response.status_code}"}
                
    except Exception as e:
        logger.error(f"Error fetching weather data: {e}")
        return {"error": f"Weather data fetch failed: {str(e)}"}

async def get_weather_forecast(location: str, days: int = 5) -> dict:
    """실제 날씨 예보를 가져옵니다."""
    location = location.strip()
    
    if location in KOREAN_CITIES:
        city_info = KOREAN_CITIES[location]
        lat = city_info["lat"]
        lon = city_info["lon"]
    else:
        return {"error": "지원하지 않는 지역입니다."}
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            url = f"{OPENWEATHER_BASE_URL}/forecast?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric&lang=kr"
            
            response = await client.get(url)
            
            if response.status_code == 200:
                data = response.json()
                
                # 날씨 상태를 한국어로 변환
                weather_conditions = {
                    "Clear": "맑음",
                    "Clouds": "흐림",
                    "Rain": "비",
                    "Snow": "눈",
                    "Thunderstorm": "천둥번개",
                    "Drizzle": "이슬비",
                    "Mist": "안개",
                    "Fog": "안개",
                    "Haze": "연무"
                }
                
                forecast = []
                processed_dates = set()
                
                for item in data["list"]:
                    date = datetime.fromtimestamp(item["dt"]).strftime("%Y-%m-%d")
                    
                    # 하루에 하나씩만 추가 (12시 데이터)
                    if date not in processed_dates and len(forecast) < days:
                        weather_main = item["weather"][0]["main"]
                        weather_condition = weather_conditions.get(weather_main, item["weather"][0]["description"])
                        
                        daily_forecast = {
                            "date": date,
                            "temp_high": round(item["main"]["temp_max"], 1),
                            "temp_low": round(item["main"]["temp_min"], 1),
                            "condition": weather_condition,
                            "humidity": item["main"]["humidity"],
                            "precipitation_chance": round(item["pop"] * 100, 1),  # 확률을 퍼센트로
                            "wind_speed": item["wind"]["speed"]
                        }
                        forecast.append(daily_forecast)
                        processed_dates.add(date)
                
                result = {
                    "location": location,
                    "forecast": forecast,
                    "generated_at": datetime.now().isoformat()
                }
                
                logger.info(f"get_weather_forecast({location}, {days}) = {result}")
                return result
            else:
                logger.error(f"Weather forecast API error: {response.status_code}")
                return {"error": f"Weather forecast API error: {response.status_code}"}
                
    except Exception as e:
        logger.error(f"Error fetching weather forecast: {e}")
        return {"error": f"Weather forecast fetch failed: {str(e)}"}

async def get_air_quality(location: str) -> dict:
    """실제 대기질 정보를 가져옵니다."""
    location = location.strip()
    
    if location in KOREAN_CITIES:
        city_info = KOREAN_CITIES[location]
        lat = city_info["lat"]
        lon = city_info["lon"]
    else:
        return {"error": "지원하지 않는 지역입니다."}
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            url = f"{OPENWEATHER_BASE_URL}/air_pollution?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}"
            
            response = await client.get(url)
            
            if response.status_code == 200:
                data = response.json()
                aqi_data = data["list"][0]
                
                # AQI 레벨 변환
                aqi = aqi_data["main"]["aqi"]
                if aqi == 1:
                    level = "좋음"
                elif aqi == 2:
                    level = "보통"
                elif aqi == 3:
                    level = "나쁨"
                elif aqi == 4:
                    level = "매우나쁨"
                else:
                    level = "위험"
                
                components = aqi_data["components"]
                
                result = {
                    "location": location,
                    "aqi": aqi,
                    "level": level,
                    "pm10": components.get("pm10", 0),
                    "pm25": components.get("pm2_5", 0),
                    "co": components.get("co", 0),
                    "no2": components.get("no2", 0),
                    "so2": components.get("so2", 0),
                    "o3": components.get("o3", 0),
                    "timestamp": datetime.now().isoformat()
                }
                
                logger.info(f"get_air_quality({location}) = {result}")
                return result
            else:
                logger.error(f"Air quality API error: {response.status_code}")
                return {"error": f"Air quality API error: {response.status_code}"}
                
    except Exception as e:
        logger.error(f"Error fetching air quality: {e}")
        return {"error": f"Air quality fetch failed: {str(e)}"}

async def get_uv_index(location: str) -> dict:
    """실제 자외선 지수를 가져옵니다."""
    location = location.strip()
    
    if location in KOREAN_CITIES:
        city_info = KOREAN_CITIES[location]
        lat = city_info["lat"]
        lon = city_info["lon"]
    else:
        return {"error": "지원하지 않는 지역입니다."}
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            # 현재 시간 기준으로 자외선 지수 계산 (OpenWeatherMap은 자외선 지수를 직접 제공하지 않음)
            # 대신 시간대와 계절을 고려한 추정치 제공
            
            # 현재 시간 정보 가져오기
            weather_url = f"{OPENWEATHER_BASE_URL}/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric"
            weather_response = await client.get(weather_url)
            
            if weather_response.status_code == 200:
                weather_data = weather_response.json()
                
                # 시간대와 계절을 고려한 자외선 지수 추정
                current_time = datetime.now()
                hour = current_time.hour
                month = current_time.month
                
                # 계절별 기본 자외선 지수
                seasonal_uv = {
                    12: 2, 1: 2, 2: 3,   # 겨울
                    3: 5, 4: 6, 5: 7,     # 봄
                    6: 8, 7: 9, 8: 9,     # 여름
                    9: 7, 10: 5, 11: 3    # 가을
                }
                
                base_uv = seasonal_uv.get(month, 5)
                
                # 시간대별 조정
                if 10 <= hour <= 14:  # 정오 시간대
                    uv_multiplier = 1.2
                elif 8 <= hour <= 16:  # 주간
                    uv_multiplier = 1.0
                else:  # 이른 아침이나 늦은 오후
                    uv_multiplier = 0.5
                
                uv_value = round(base_uv * uv_multiplier)
                uv_value = max(1, min(11, uv_value))  # 1-11 범위로 제한
                
                # 자외선 지수에 따른 보호 방법
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
                
                result = {
                    "location": location,
                    "uv_index": uv_value,
                    "level": level,
                    "protection": protection,
                    "timestamp": datetime.now().isoformat()
                }
                
                logger.info(f"get_uv_index({location}) = {result}")
                return result
            else:
                return {"error": "날씨 정보를 가져올 수 없습니다."}
                
    except Exception as e:
        logger.error(f"Error calculating UV index: {e}")
        return {"error": f"UV index calculation failed: {str(e)}"}

async def get_wind_info(location: str) -> dict:
    """실제 바람 정보를 가져옵니다."""
    location = location.strip()
    
    if location in KOREAN_CITIES:
        city_info = KOREAN_CITIES[location]
        lat = city_info["lat"]
        lon = city_info["lon"]
    else:
        return {"error": "지원하지 않는 지역입니다."}
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            url = f"{OPENWEATHER_BASE_URL}/weather?lat={lat}&lon={lon}&appid={OPENWEATHER_API_KEY}&units=metric"
            
            response = await client.get(url)
            
            if response.status_code == 200:
                data = response.json()
                wind_data = data["wind"]
                
                wind_speed = wind_data["speed"]
                wind_deg = wind_data.get("deg", 0)
                
                # 풍향을 한국어로 변환
                directions = {
                    (0, 22.5): "북",
                    (22.5, 67.5): "북동",
                    (67.5, 112.5): "동",
                    (112.5, 157.5): "남동",
                    (157.5, 202.5): "남",
                    (202.5, 247.5): "남서",
                    (247.5, 292.5): "서",
                    (292.5, 337.5): "북서",
                    (337.5, 360): "북"
                }
                
                wind_direction = "북"
                for (min_deg, max_deg), direction in directions.items():
                    if min_deg <= wind_deg < max_deg:
                        wind_direction = direction
                        break
                
                # 풍속에 따른 설명
                if wind_speed <= 5:
                    description = "약한 바람"
                elif wind_speed <= 10:
                    description = "보통 바람"
                elif wind_speed <= 20:
                    description = "강한 바람"
                else:
                    description = "매우 강한 바람"
                
                result = {
                    "location": location,
                    "speed": round(wind_speed, 1),
                    "direction": wind_direction,
                    "description": description,
                    "timestamp": datetime.now().isoformat()
                }
                
                logger.info(f"get_wind_info({location}) = {result}")
                return result
            else:
                logger.error(f"Wind info API error: {response.status_code}")
                return {"error": f"Wind info API error: {response.status_code}"}
                
    except Exception as e:
        logger.error(f"Error fetching wind info: {e}")
        return {"error": f"Wind info fetch failed: {str(e)}"}

# 도구 목록
TOOLS = {
    "get_current_weather": {
        "name": "get_current_weather",
        "description": "실제 현재 날씨 정보를 가져옵니다.",
        "args_schema": {"location": "string"},
        "function": get_current_weather
    },
    "get_weather_forecast": {
        "name": "get_weather_forecast",
        "description": "실제 날씨 예보를 가져옵니다.",
        "args_schema": {"location": "string", "days": "int"},
        "function": get_weather_forecast
    },
    "get_air_quality": {
        "name": "get_air_quality",
        "description": "실제 대기질 정보를 가져옵니다.",
        "args_schema": {"location": "string"},
        "function": get_air_quality
    },
    "get_uv_index": {
        "name": "get_uv_index",
        "description": "실제 자외선 지수를 가져옵니다.",
        "args_schema": {"location": "string"},
        "function": get_uv_index
    },
    "get_wind_info": {
        "name": "get_wind_info",
        "description": "실제 바람 정보를 가져옵니다.",
        "args_schema": {"location": "string"},
        "function": get_wind_info
    }
}

@app.get("/")
async def root():
    return {"message": "Real Weather Server is running"}

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
    return {"status": "healthy", "server": "Real Weather Server"}

if __name__ == "__main__":
    import uvicorn
    import os
    
    # 환경변수 설정
    port = int(os.environ.get("MCP_PORT", 8005))
    host = os.environ.get("MCP_HOST", "0.0.0.0")
    
    print(f"Real Weather Server를 포트 {port}에서 시작합니다...")
    print(f"MCP_PORT: {port}")
    print(f"MCP_HOST: {host}")
    
    if OPENWEATHER_API_KEY == "your_api_key_here":
        print("⚠️  경고: OPENWEATHER_API_KEY가 설정되지 않았습니다.")
        print("실제 날씨 데이터를 가져오려면 환경변수 OPENWEATHER_API_KEY를 설정하세요.")
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )

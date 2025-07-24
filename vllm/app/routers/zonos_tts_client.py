"""
Zonos TTS 클라이언트
독립 서비스로 실행되는 Zonos TTS와 통신
"""

import os
import httpx
import logging
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import FileResponse, StreamingResponse
from typing import Optional
import tempfile
from datetime import datetime
import asyncio

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/zonos",
    tags=["tts"]
)

# Zonos TTS 서비스 URL
ZONOS_SERVICE_URL = os.getenv('ZONOS_SERVICE_URL', 'http://localhost:8002')

async def check_zonos_health():
    """Zonos 서비스 상태 확인"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{ZONOS_SERVICE_URL}/", timeout=5.0)
            return response.status_code == 200
    except:
        return False

@router.post("/tts", response_class=FileResponse)
async def text_to_speech(
    text: str = Form(...),
    voice_preset: Optional[str] = Form("romeo"),
    speed: Optional[float] = Form(1.0)
):
    """텍스트를 음성으로 변환 (독립 서비스 호출)"""
    
    # Zonos 서비스 상태 확인
    if not await check_zonos_health():
        raise HTTPException(
            status_code=503,
            detail="Zonos TTS 서비스가 응답하지 않습니다. 서비스가 실행 중인지 확인해주세요."
        )
    
    try:
        # Zonos 서비스에 요청
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{ZONOS_SERVICE_URL}/generate",
                json={
                    "text": text,
                    "voice_preset": voice_preset,
                    "speed": speed
                },
                timeout=30.0  # 긴 텍스트를 위한 타임아웃
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Zonos 서비스 오류: {response.text}"
                )
            
            # 임시 파일로 저장
            with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
                tmp_file.write(response.content)
                output_path = tmp_file.name
            
            return FileResponse(
                output_path,
                media_type='audio/wav',
                filename=f'speech_{datetime.now().strftime("%Y%m%d_%H%M%S")}.wav'
            )
            
    except httpx.TimeoutException:
        raise HTTPException(
            status_code=504,
            detail="Zonos TTS 서비스 타임아웃. 텍스트가 너무 길거나 서비스가 과부하 상태입니다."
        )
    except Exception as e:
        logger.error(f"Zonos TTS 클라이언트 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/status")
async def get_zonos_status():
    """Zonos 서비스 상태 조회"""
    try:
        async with httpx.AsyncClient() as client:
            # 상태 조회
            status_response = await client.get(f"{ZONOS_SERVICE_URL}/", timeout=5.0)
            
            # GPU 정보 조회
            gpu_response = await client.get(f"{ZONOS_SERVICE_URL}/gpu-info", timeout=5.0)
            
            return {
                "service_url": ZONOS_SERVICE_URL,
                "health": status_response.json() if status_response.status_code == 200 else None,
                "gpu_info": gpu_response.json() if gpu_response.status_code == 200 else None
            }
    except Exception as e:
        return {
            "service_url": ZONOS_SERVICE_URL,
            "health": None,
            "gpu_info": None,
            "error": str(e)
        }

@router.post("/tts/stream")
async def text_to_speech_stream(
    text: str = Form(...),
    voice_preset: Optional[str] = Form("romeo"),
    speed: Optional[float] = Form(1.0)
):
    """텍스트를 음성으로 변환 (스트리밍)"""
    
    if not await check_zonos_health():
        raise HTTPException(
            status_code=503,
            detail="Zonos TTS 서비스가 응답하지 않습니다."
        )
    
    try:
        async def stream_response():
            async with httpx.AsyncClient() as client:
                async with client.stream(
                    'POST',
                    f"{ZONOS_SERVICE_URL}/generate",
                    json={
                        "text": text,
                        "voice_preset": voice_preset,
                        "speed": speed
                    },
                    timeout=30.0
                ) as response:
                    async for chunk in response.aiter_bytes():
                        yield chunk
        
        return StreamingResponse(
            stream_response(),
            media_type='audio/wav',
            headers={
                'Content-Disposition': f'attachment; filename="speech_{datetime.now().strftime("%Y%m%d_%H%M%S")}.wav"'
            }
        )
        
    except Exception as e:
        logger.error(f"Zonos TTS 스트리밍 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))
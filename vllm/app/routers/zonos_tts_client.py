"""
Zonos TTS 클라이언트
독립 서비스로 실행되는 Zonos TTS와 통신
"""

import os
import httpx
import logging
from fastapi import APIRouter, HTTPException, UploadFile, File, Form, BackgroundTasks
from fastapi.responses import FileResponse, StreamingResponse
from typing import Optional, List, Dict, Any
from pydantic import BaseModel
import tempfile
from datetime import datetime
import asyncio
import uuid

logger = logging.getLogger(__name__)

# Pydantic 모델 정의
class ZonosTTSResponse(BaseModel):
    task_id: str
    status: str
    message: str
    file_url: Optional[str] = None
    file_path: Optional[str] = None
    error_message: Optional[str] = None

class ZonosTTSWithVoiceRequest(BaseModel):
    text: str
    voice_data_base64: str
    language: str = "ko"
    speaking_rate: float = 22.0
    pitch_std: float = 40.0
    cfg_scale: float = 4.0
    emotion: List[float] = [0.3077, 0.0256, 0.0256, 0.0256, 0.0256, 0.0256, 0.2564, 0.3077]
    output_filename: Optional[str] = None
    upload_to_s3: bool = False
    s3_folder_prefix: str = "zonos-tts"
    s3_public_read: bool = False
    async_mode: bool = True

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

@router.post("/generate_tts_with_voice", response_model=ZonosTTSResponse)
async def generate_tts_with_voice(
    request: ZonosTTSWithVoiceRequest,
    background_tasks: BackgroundTasks
):
    """음성 클로닝을 사용한 비동기 TTS 생성"""
    
    # Zonos 서비스가 실행 중인지 확인
    if not await check_zonos_health():
        # Zonos가 독립 서비스로 실행되지 않는 경우, 기존 방식으로 폴백
        logger.warning("Zonos 독립 서비스가 응답하지 않습니다. 기존 방식으로 처리합니다.")
        
        # 기존 zonos_tts_async 라우터로 리다이렉트
        from app.routers import zonos_tts_async
        if hasattr(zonos_tts_async, 'generate_tts_with_voice_async'):
            return await zonos_tts_async.generate_tts_with_voice_async(background_tasks, request)
        else:
            raise HTTPException(
                status_code=503,
                detail="Zonos TTS 서비스를 사용할 수 없습니다."
            )
    
    try:
        # 작업 ID 생성
        task_id = str(uuid.uuid4())
        
        # Zonos 독립 서비스에 요청
        async with httpx.AsyncClient() as client:
            # 음성 데이터와 함께 TTS 생성 요청
            response = await client.post(
                f"{ZONOS_SERVICE_URL}/generate_with_voice",
                json={
                    "text": request.text,
                    "voice_data_base64": request.voice_data_base64,
                    "language": 'ko',
                    "speaking_rate": request.speaking_rate,
                    "pitch_std": request.pitch_std,
                    "cfg_scale": request.cfg_scale,
                    "emotion": request.emotion,
                    "output_filename": request.output_filename
                },
                timeout=60.0  # 음성 클로닝은 시간이 걸릴 수 있음
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Zonos 서비스 오류: {response.text}"
                )
            
            result = response.json()
            
            # S3 업로드가 필요한 경우
            if request.upload_to_s3:
                # TODO: S3 업로드 로직 구현
                logger.warning("S3 업로드는 아직 구현되지 않았습니다.")
            
            return ZonosTTSResponse(
                task_id=task_id,
                status="completed",
                message="음성 생성 완료",
                file_path=result.get("file_path"),
                file_url=result.get("file_url")
            )
            
    except httpx.TimeoutException:
        return ZonosTTSResponse(
            task_id=task_id,
            status="failed",
            message="음성 생성 시간 초과",
            error_message="Zonos TTS 서비스가 응답하지 않습니다."
        )
    except Exception as e:
        logger.error(f"Zonos TTS with voice 오류: {e}")
        return ZonosTTSResponse(
            task_id=task_id,
            status="failed",
            message="음성 생성 실패",
            error_message=str(e)
        )
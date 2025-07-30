"""
RunPod Serverless를 사용한 TTS 라우터
"""
import uuid
import logging
from typing import Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, HTTPException, BackgroundTasks
from pydantic import BaseModel, Field

from app.utils.runpod_client import get_runpod_client, RunPodEndpoint
from app.utils.cache_manager import get_cache_manager

logger = logging.getLogger(__name__)
router = APIRouter()

# 미리 정의된 감정 벡터
PREDEFINED_EMOTIONS = {
    "neutral": [0.3077, 0.0256, 0.0256, 0.0256, 0.0256, 0.0256, 0.2564, 0.3077],
    "happy": [0.0256, 0.5897, 0.0256, 0.0256, 0.0256, 0.0256, 0.0256, 0.3077],
    "sad": [0.0256, 0.0256, 0.5897, 0.0256, 0.0256, 0.0256, 0.0256, 0.3077],
    "angry": [0.0256, 0.0256, 0.0256, 0.5897, 0.0256, 0.0256, 0.0256, 0.3077],
    "fearful": [0.0256, 0.0256, 0.0256, 0.0256, 0.5897, 0.0256, 0.0256, 0.3077],
    "disgusted": [0.0256, 0.0256, 0.0256, 0.0256, 0.0256, 0.5897, 0.0256, 0.3077],
    "surprised": [0.0256, 0.0256, 0.0256, 0.0256, 0.0256, 0.0256, 0.5897, 0.3077],
    "contempt": [0.0256, 0.0256, 0.0256, 0.0256, 0.0256, 0.0256, 0.0256, 0.8718]
}

class RunPodTTSRequest(BaseModel):
    text: str
    language: str = "ko"
    speaking_rate: float = 22.0
    pitch_std: float = 40.0
    cfg_scale: float = 4.0
    emotion: list[float] = Field(default=PREDEFINED_EMOTIONS["neutral"])
    emotion_name: Optional[str] = None
    voice_data_base64: Optional[str] = None
    async_mode: bool = True

class RunPodTTSResponse(BaseModel):
    task_id: str
    status: str
    message: str
    job_id: Optional[str] = None
    result: Optional[Dict[str, Any]] = None

@router.post("/generate_tts_runpod", response_model=RunPodTTSResponse)
async def generate_tts_runpod(
    request: RunPodTTSRequest,
    background_tasks: BackgroundTasks
):
    """RunPod Serverless를 사용한 TTS 생성"""
    # 감정 이름으로 벡터 설정
    if request.emotion_name and request.emotion_name in PREDEFINED_EMOTIONS:
        request.emotion = PREDEFINED_EMOTIONS[request.emotion_name]
    
    # 작업 ID 생성
    task_id = str(uuid.uuid4())
    
    # RunPod 클라이언트
    runpod_client = get_runpod_client()
    
    # 입력 데이터 준비
    input_data = {
        "text": request.text,
        "language": request.language,
        "speaking_rate": request.speaking_rate,
        "pitch_std": request.pitch_std,
        "cfg_scale": request.cfg_scale,
        "emotion": request.emotion
    }
    
    if request.voice_data_base64:
        input_data["voice_data_base64"] = request.voice_data_base64
    
    try:
        if request.async_mode:
            # 비동기 실행
            result = await runpod_client.run_async(
                endpoint=RunPodEndpoint.TTS,
                input_data=input_data,
                webhook_url=f"https://your-backend.com/api/webhook/tts/{task_id}"
            )
            
            # 캐시에 작업 정보 저장
            cache_manager = get_cache_manager()
            await cache_manager.set_async(
                f"tts_task:{task_id}",
                {
                    "task_id": task_id,
                    "job_id": result["id"],
                    "status": "pending",
                    "created_at": datetime.utcnow().isoformat()
                },
                expire=3600  # 1시간
            )
            
            return RunPodTTSResponse(
                task_id=task_id,
                status="pending",
                message="TTS 생성 작업이 시작되었습니다.",
                job_id=result["id"]
            )
        else:
            # 동기 실행 (완료까지 대기)
            result = await runpod_client.run_sync(
                endpoint=RunPodEndpoint.TTS,
                input_data=input_data,
                timeout=60
            )
            
            if result["status"] == "COMPLETED":
                return RunPodTTSResponse(
                    task_id=task_id,
                    status="completed",
                    message="TTS 생성이 완료되었습니다.",
                    result=result["output"]
                )
            else:
                raise HTTPException(
                    status_code=500,
                    detail=f"TTS 생성 실패: {result.get('error', 'Unknown error')}"
                )
    
    except Exception as e:
        logger.error(f"RunPod TTS 생성 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/tts_status_runpod/{task_id}")
async def get_tts_status_runpod(task_id: str):
    """RunPod TTS 작업 상태 조회"""
    cache_manager = get_cache_manager()
    task_info = await cache_manager.get_async(f"tts_task:{task_id}")
    
    if not task_info:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
    
    # RunPod에서 상태 조회
    runpod_client = get_runpod_client()
    try:
        status = await runpod_client.get_status(
            endpoint=RunPodEndpoint.TTS,
            job_id=task_info["job_id"]
        )
        
        # 캐시 업데이트
        task_info["status"] = status["status"].lower()
        if status["status"] == "COMPLETED":
            task_info["result"] = status["output"]
        elif status["status"] == "FAILED":
            task_info["error"] = status.get("error", "Unknown error")
        
        await cache_manager.set_async(
            f"tts_task:{task_id}",
            task_info,
            expire=3600
        )
        
        return task_info
        
    except Exception as e:
        logger.error(f"상태 조회 오류: {e}")
        raise HTTPException(status_code=500, detail="상태 조회 실패")

@router.post("/webhook/tts/{task_id}")
async def tts_webhook(task_id: str, webhook_data: Dict[str, Any]):
    """RunPod 웹훅 처리"""
    cache_manager = get_cache_manager()
    task_info = await cache_manager.get_async(f"tts_task:{task_id}")
    
    if task_info:
        # 작업 상태 업데이트
        task_info["status"] = webhook_data["status"].lower()
        if webhook_data["status"] == "COMPLETED":
            task_info["result"] = webhook_data["output"]
        elif webhook_data["status"] == "FAILED":
            task_info["error"] = webhook_data.get("error", "Unknown error")
        
        task_info["updated_at"] = datetime.utcnow().isoformat()
        
        await cache_manager.set_async(
            f"tts_task:{task_id}",
            task_info,
            expire=3600
        )
        
        logger.info(f"웹훅 처리 완료: task_id={task_id}, status={webhook_data['status']}")
    
    return {"status": "ok"}
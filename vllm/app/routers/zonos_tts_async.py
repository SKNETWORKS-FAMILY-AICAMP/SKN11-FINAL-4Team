import asyncio
import logging
import os
import uuid
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import concurrent.futures
import httpx

import torch
import torchaudio
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, validator
import aiofiles

from zonos.model import Zonos
from zonos.conditioning import make_cond_dict
from app.utils.async_s3_utils import get_async_s3_manager, initialize_async_s3_manager

logger = logging.getLogger(__name__)

router = APIRouter()

# Zonos 모델 전역 변수
zonos_model = None
device = None
zonos_initialization_attempted = False  # 초기화 시도 추적

# 비동기 작업 상태 추적 (Legacy - will be migrated to cache manager)
task_status: Dict[str, Dict[str, Any]] = {}

# ThreadPoolExecutor for CPU-bound tasks (managed)
executor = None
executor_lock = asyncio.Lock()

async def get_executor():
    """Get or create ThreadPoolExecutor instance (thread-safe)"""
    global executor
    async with executor_lock:
        if executor is None:
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
    return executor

async def shutdown_executor():
    """Properly shutdown the ThreadPoolExecutor"""
    global executor
    async with executor_lock:
        if executor is not None:
            executor.shutdown(wait=True)
            executor = None

# 웹훅 URL 설정 (환경 변수에서 가져오거나 기본값 사용)
# 백엔드가 HTTPS로 실행되고 있으므로 HTTPS 사용
WEBHOOK_URL = os.getenv('TTS_WEBHOOK_URL', 'https://localhost:8000/api/v1/tts/webhook/tts-complete')

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

class ZonosTTSRequest(BaseModel):
    text: str
    language: str = "ko"
    speaking_rate: float = 22.0
    pitch_std: float = 40.0
    cfg_scale: float = 4.0
    emotion: list[float] = Field(default=[0.3077, 0.0256, 0.0256, 0.0256, 0.0256, 0.0256, 0.2564, 0.3077], description="8차원 감정 벡터")
    emotion_name: Optional[str] = Field(default=None, description="미리 정의된 감정 이름 (neutral, happy, sad, angry, fearful, disgusted, surprised, contempt)")
    output_filename: Optional[str] = None
    upload_to_s3: bool = False
    s3_folder_prefix: str = "zonos-tts"
    s3_public_read: bool = False
    async_mode: bool = True  # 비동기 모드 플래그
    
    @validator('emotion')
    def validate_emotion(cls, v):
        if len(v) != 8:
            raise ValueError("emotion은 8개의 float 값으로 구성되어야 합니다.")
        if not all(0 <= x <= 1 for x in v):
            raise ValueError("emotion 값은 0과 1 사이여야 합니다.")
        return v
    
    @validator('emotion', pre=False, always=True)
    def set_emotion_from_name(cls, v, values):
        emotion_name = values.get('emotion_name')
        if emotion_name and emotion_name in PREDEFINED_EMOTIONS:
            return PREDEFINED_EMOTIONS[emotion_name]
        return v

class ZonosTTSWithVoiceRequest(BaseModel):
    text: str
    language: str = "ko"
    speaking_rate: float = 22.0
    pitch_std: float = 40.0
    cfg_scale: float = 4.0
    emotion: list[float] = Field(default=[0.3077, 0.0256, 0.0256, 0.0256, 0.0256, 0.0256, 0.2564, 0.3077], description="8차원 감정 벡터")
    emotion_name: Optional[str] = Field(default=None, description="미리 정의된 감정 이름")
    voice_data_base64: str  # Base64 인코딩된 음성 데이터
    output_filename: Optional[str] = None
    upload_to_s3: bool = False
    s3_folder_prefix: str = "zonos-tts"
    s3_public_read: bool = False
    async_mode: bool = True
    
    @validator('emotion')
    def validate_emotion(cls, v):
        if len(v) != 8:
            raise ValueError("emotion은 8개의 float 값으로 구성되어야 합니다.")
        if not all(0 <= x <= 1 for x in v):
            raise ValueError("emotion 값은 0과 1 사이여야 합니다.")
        return v
    
    @validator('emotion', pre=False, always=True)
    def set_emotion_from_name(cls, v, values):
        emotion_name = values.get('emotion_name')
        if emotion_name and emotion_name in PREDEFINED_EMOTIONS:
            return PREDEFINED_EMOTIONS[emotion_name]
        return v

class SimpleTTSRequest(BaseModel):
    text: str
    language: str = "ko"
    speaking_rate: float = 22.0
    pitch_std: float = 40.0
    cfg_scale: float = 4.0
    emotion: list[float] = Field(default=[0.3077, 0.0256, 0.0256, 0.0256, 0.0256, 0.0256, 0.2564, 0.3077], description="8차원 감정 벡터")
    emotion_name: Optional[str] = Field(default=None, description="미리 정의된 감정 이름")
    
    @validator('emotion')
    def validate_emotion(cls, v):
        if len(v) != 8:
            raise ValueError("emotion은 8개의 float 값으로 구성되어야 합니다.")
        if not all(0 <= x <= 1 for x in v):
            raise ValueError("emotion 값은 0과 1 사이여야 합니다.")
        return v
    
    @validator('emotion', pre=False, always=True)
    def set_emotion_from_name(cls, v, values):
        emotion_name = values.get('emotion_name')
        if emotion_name and emotion_name in PREDEFINED_EMOTIONS:
            return PREDEFINED_EMOTIONS[emotion_name]
        return v

class ZonosTTSResponse(BaseModel):
    task_id: str
    status: str
    message: str
    audio_path: Optional[str] = None
    s3_info: Optional[Dict[str, Any]] = None

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: int
    message: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: str
    updated_at: str

def initialize_zonos_model():
    """Zonos 모델 초기화 (싱글톤 패턴)"""
    global zonos_model, device, zonos_initialization_attempted
    
    # 이미 초기화 시도했으면 스킵 (성공 여부와 관계없이)
    if zonos_initialization_attempted:
        if zonos_model is not None:
            logger.info("ℹ️ Zonos 모델이 이미 초기화되어 있습니다.")
        else:
            logger.info("ℹ️ Zonos 모델 초기화가 이미 시도되었습니다.")
        return zonos_model is not None
    
    # 초기화 시도 플래그 설정
    zonos_initialization_attempted = True
    
    try:
        # 환경 변수에서 TTS GPU ID 가져오기 (기본값: 1)
        tts_gpu_id = int(os.getenv('TTS_GPU_ID', '1'))
        
        # GPU 설정 - 환경 변수 기반
        if torch.cuda.is_available():
            # CUDA_VISIBLE_DEVICES 설정으로 격리된 환경에서 실행
            if 'CUDA_VISIBLE_DEVICES' in os.environ:
                # 격리된 환경에서는 항상 device 0을 사용
                torch.cuda.set_device(0)
                device = torch.device("cuda:0")
                logger.info(f"🔧 Zonos 모델 초기화 중... (격리된 GPU 환경, 디바이스: cuda:0)")
                logger.info(f"📍 CUDA_VISIBLE_DEVICES: {os.environ['CUDA_VISIBLE_DEVICES']}")
            else:
                # 격리되지 않은 환경에서는 지정된 GPU 사용
                torch.cuda.set_device(tts_gpu_id)
                device = torch.device(f"cuda:{tts_gpu_id}")
                logger.info(f"🔧 Zonos 모델 초기화 중... (디바이스: cuda:{tts_gpu_id})")
            logger.info(f"✅ GPU {tts_gpu_id} 할당 (전체 GPU 수: {torch.cuda.device_count()})")
        else:
            device = torch.device("cpu")
            logger.warning("⚠️ CUDA를 사용할 수 없습니다. CPU를 사용합니다.")
        
        zonos_model = Zonos.from_pretrained("Zyphra/Zonos-v0.1-transformer", device=device)
        logger.info("✅ Zonos 모델 초기화 완료")
        return True
    except Exception as e:
        logger.error(f"❌ Zonos 모델 초기화 실패: {e}")
        zonos_model = None  # 실패 시 None으로 설정
        return False

@router.on_event("startup")
async def startup_event():
    """라우터 시작 시 모델 초기화"""
    loop = asyncio.get_event_loop()
    await loop.run_in_executor(executor, initialize_zonos_model)

def generate_tts_sync(
    text: str,
    speaker_embedding,
    language: str,
    speaking_rate: float,
    pitch_std: float,
    cfg_scale: float,
    emotion: list[float] = [0.3077, 0.0256, 0.0256, 0.0256, 0.0256, 0.0256, 0.2564, 0.3077]
) -> torch.Tensor:
    """동기 TTS 생성 함수 (CPU-bound 작업)"""
    # 조건 딕셔너리 생성
    cond_dict = make_cond_dict(
        text=text,
        speaker=speaker_embedding,
        language=language,
        speaking_rate=speaking_rate,
        emotion = emotion,
        pitch_std=pitch_std
    )
    
    # 조건 준비
    conditioning = zonos_model.prepare_conditioning(cond_dict)
    
    # 코드 생성
    codes = zonos_model.generate(
        conditioning, 
        cfg_scale=cfg_scale,
        disable_torch_compile=True,
        progress_bar=False
    )
    
    # 오디오 디코드
    wavs = zonos_model.autoencoder.decode(codes)
    
    return wavs[0]


async def send_webhook_notification(
    task_id: str,
    status: str,
    s3_url: Optional[str] = None,
    s3_key: Optional[str] = None,
    duration: Optional[float] = None,
    file_size: Optional[int] = None,
    error_message: Optional[str] = None
):
    """웹훅으로 작업 완료 알림을 전송"""
    try:
        webhook_data = {
            "task_id": task_id,
            "status": status,
            "s3_url": s3_url,
            "s3_key": s3_key,
            "duration": duration,
            "file_size": file_size,
            "error_message": error_message
        }
        
        async with httpx.AsyncClient(verify=False) as client:
            response = await client.post(
                WEBHOOK_URL,
                json=webhook_data,
                timeout=10.0
            )
            
            if response.status_code == 200:
                logger.info(f"✅ 웹훅 전송 성공: task_id={task_id}, status={status}")
            else:
                logger.error(f"❌ 웹훅 전송 실패: status_code={response.status_code}, response={response.text}")
                
    except Exception as e:
        logger.error(f"❌ 웹훅 전송 중 오류 발생: {str(e)}")


async def process_tts_task(
    task_id: str,
    request: ZonosTTSRequest
):
    """백그라운드에서 TTS 작업 처리 (JSON 전용)"""
    try:
        # 작업 상태 업데이트
        task_status[task_id]["status"] = "processing"
        task_status[task_id]["progress"] = 10
        task_status[task_id]["updated_at"] = datetime.utcnow().isoformat()
        
        # 임시 디렉토리 생성
        temp_dir = Path("/tmp/zonos_tts")
        temp_dir.mkdir(exist_ok=True)
        
        # 기본 스피커 임베딩 사용 (음성 클로닝 없음)
        speaker = None
        
        task_status[task_id]["progress"] = 30
        task_status[task_id]["updated_at"] = datetime.utcnow().isoformat()
        
        # TTS 생성 (CPU-bound 작업을 비동기로)
        loop = asyncio.get_event_loop()
        wav_output = await loop.run_in_executor(
            executor,
            generate_tts_sync,
            request.text,
            speaker,
            request.language,
            request.speaking_rate,
            request.pitch_std,
            request.cfg_scale,
            request.emotion
        )
        
        task_status[task_id]["progress"] = 70
        task_status[task_id]["updated_at"] = datetime.utcnow().isoformat()
        
        # 출력 파일명 설정
        if request.output_filename:
            output_filename = request.output_filename
        else:
            output_filename = f"zonos_tts_{task_id}.wav"
        
        output_path = temp_dir / output_filename
        
        # 오디오 저장
        await loop.run_in_executor(
            executor,
            torchaudio.save,
            str(output_path),
            wav_output.cpu(),
            zonos_model.autoencoder.sampling_rate
        )
        
        logger.info(f"✅ TTS 생성 완료: {output_path}")
        task_status[task_id]["progress"] = 90
        task_status[task_id]["updated_at"] = datetime.utcnow().isoformat()
        
        # S3 업로드 처리
        s3_info = None
        if request.upload_to_s3:
            try:
                s3_manager = await get_async_s3_manager()
                if not s3_manager.bucket_name:
                    logger.error("S3 bucket name is not configured")
                    raise ValueError("S3 bucket name is not configured")
                
                # 메타데이터 생성
                # S3 메타데이터는 ASCII만 지원하므로 non-ASCII 텍스트는 제외하거나 인코딩
                metadata = {
                    "text_length": str(len(request.text)),
                    "language": request.language,
                    "speaking_rate": str(request.speaking_rate),
                    "pitch_std": str(request.pitch_std),
                    "cfg_scale": str(request.cfg_scale),
                    "emotion": str(request.emotion),
                    "generated_by": "zonos-tts-async",
                    "task_id": task_id
                }
                
                # S3에 비동기 업로드
                async with aiofiles.open(str(output_path), 'rb') as f:
                    file_data = await f.read()
                
                s3_info = await s3_manager.upload_file_from_bytes(
                    file_data=file_data,
                    object_name=output_filename,
                    folder_prefix=request.s3_folder_prefix,
                    metadata=metadata,
                    public_read=request.s3_public_read
                )
                
                logger.info(f"✅ S3 업로드 완료: {s3_info['key']}")
                
                # 웹훅 전송
                await send_webhook_notification(
                    task_id=task_id,
                    status="completed",
                    s3_url=s3_info.get('url'),
                    s3_key=s3_info.get('key'),
                    duration=None,  # TODO: 실제 오디오 길이 계산 필요
                    file_size=len(file_data)
                )
                
                # S3 업로드 성공 시 로컬 파일 삭제
                try:
                    Path(output_path).unlink()
                    logger.info(f"🗑️ 로컬 파일 삭제 완료: {output_path}")
                except Exception as e:
                    logger.warning(f"로컬 파일 삭제 실패: {e}")
                
            except Exception as e:
                logger.error(f"⚠️ S3 업로드 실패 (로컬 파일은 생성됨): {e}")
        
        # 작업 완료
        task_status[task_id]["status"] = "completed"
        task_status[task_id]["progress"] = 100
        task_status[task_id]["message"] = "TTS 생성이 완료되었습니다."
        
        # S3 업로드 성공 시 로컬 경로 제외
        if s3_info:
            task_status[task_id]["result"] = {
                "audio_path": None,  # S3에 업로드되어 로컬 파일 삭제됨
                "s3_info": s3_info
            }
        else:
            task_status[task_id]["result"] = {
                "audio_path": str(output_path),
                "s3_info": None
            }
        task_status[task_id]["updated_at"] = datetime.utcnow().isoformat()
        
    except Exception as e:
        logger.error(f"❌ TTS 작업 실패 (task_id: {task_id}): {e}")
        task_status[task_id]["status"] = "failed"
        task_status[task_id]["error"] = str(e)
        task_status[task_id]["updated_at"] = datetime.utcnow().isoformat()
        
        # 실패 웹훅 전송
        await send_webhook_notification(
            task_id=task_id,
            status="failed",
            error_message=str(e)
        )

@router.post("/generate_tts", response_model=ZonosTTSResponse)
async def generate_tts_async(
    background_tasks: BackgroundTasks,
    request: ZonosTTSRequest
):
    """비동기 TTS 생성 (JSON 전용)"""
    # 모델이 초기화되지 않았으면 다시 시도
    if zonos_model is None:
        logger.warning("⚠️ Zonos 모델이 초기화되지 않았습니다. 초기화 시도 중...")
        success = await asyncio.get_event_loop().run_in_executor(executor, initialize_zonos_model)
        if not success:
            raise HTTPException(status_code=500, detail="Zonos 모델 초기화에 실패했습니다. 서버 로그를 확인하세요.")
    
    # 작업 ID 생성
    task_id = str(uuid.uuid4())
    
    # 작업 상태 초기화
    task_status[task_id] = {
        "status": "pending",
        "progress": 0,
        "message": "TTS 생성 작업이 대기 중입니다.",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "request": request.dict()
    }
    
    if request.async_mode:
        # 백그라운드 작업으로 처리
        background_tasks.add_task(
            process_tts_task,
            task_id,
            request
        )
        
        return ZonosTTSResponse(
            task_id=task_id,
            status="pending",
            message="TTS 생성 작업이 시작되었습니다. /task_status/{task_id}로 진행 상황을 확인하세요."
        )
    else:
        # 동기 모드 (즉시 처리)
        await process_tts_task(task_id, request)
        result = task_status[task_id]["result"]
        
        return ZonosTTSResponse(
            task_id=task_id,
            status="completed",
            message="TTS 생성이 완료되었습니다.",
            audio_path=result["audio_path"],
            s3_info=result["s3_info"]
        )

@router.get("/task_status/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """작업 상태 조회"""
    task = []
    for task_id_history, task in task_status.items():
        if task_id == task_id_history:
            task=task_status[task_id_history]
    if task == []:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
    
    
    return TaskStatusResponse(
        task_id=task_id,
        status=task["status"],
        progress=task.get("progress", 0),
        message=task.get("message", ""),
        result=task.get("result"),
        error=task.get("error"),
        created_at=task["created_at"],
        updated_at=task["updated_at"]
    )

@router.get("/tasks")
async def list_tasks(
    status: Optional[str] = None,
    limit: int = 10
):
    """작업 목록 조회"""
    tasks = []
    for task_id, task in task_status.items():
        if status is None or task["status"] == status:
            tasks.append({
                "task_id": task_id,
                "status": task["status"],
                "created_at": task["created_at"],
                "updated_at": task["updated_at"]
            })
    
    # 최신 작업부터 정렬
    tasks.sort(key=lambda x: x["updated_at"], reverse=True)
    
    return {
        "tasks": tasks[:limit],
        "total": len(tasks)
    }

@router.delete("/task/{task_id}")
async def delete_task(task_id: str):
    """작업 삭제"""
    task = []
    for task_id_history, task in task_status.items():
        if task_id == task_id_history:
            task=task_status[task_id_history]
    if task == []:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다.")
    
    # 완료된 작업만 삭제 가능
    if task["status"] not in ["completed", "failed"]:
        raise HTTPException(
            status_code=400,
            detail="진행 중인 작업은 삭제할 수 없습니다."
        )
    
    # 로컬 파일 삭제
    if task.get("result") and task["result"].get("audio_path"):
        try:
            Path(task["result"]["audio_path"]).unlink()
        except Exception as e:
            logger.warning(f"파일 삭제 실패: {e}")
    
    del task_status[task_id]
    
    return {"message": "작업이 삭제되었습니다."}

@router.get("/download_tts/{filename}")
async def download_tts(filename: str):
    """생성된 TTS 파일 다운로드"""
    file_path = Path(f"/tmp/zonos_tts/{filename}")
    
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="파일을 찾을 수 없습니다.")
    
    return FileResponse(
        path=str(file_path),
        media_type="audio/wav",
        filename=filename
    )

@router.post("/generate_tts_with_voice", response_model=ZonosTTSResponse)
async def generate_tts_with_voice_async(
    background_tasks: BackgroundTasks,
    request: ZonosTTSWithVoiceRequest
):
    """음성 클로닝을 사용한 비동기 TTS 생성 (Base64 인코딩된 음성 데이터 사용)"""
    # 모델이 초기화되지 않았으면 다시 시도
    if zonos_model is None:
        logger.warning("⚠️ Zonos 모델이 초기화되지 않았습니다. 초기화 시도 중...")
        success = await asyncio.get_event_loop().run_in_executor(executor, initialize_zonos_model)
        if not success:
            raise HTTPException(status_code=500, detail="Zonos 모델 초기화에 실패했습니다. 서버 로그를 확인하세요.")
    
    # 작업 ID 생성
    task_id = str(uuid.uuid4())
    
    # 작업 상태 초기화
    task_status[task_id] = {
        "status": "pending",
        "progress": 0,
        "message": "음성 클로닝 TTS 생성 작업이 대기 중입니다.",
        "created_at": datetime.utcnow().isoformat(),
        "updated_at": datetime.utcnow().isoformat(),
        "request": request.dict()
    }
    
    if request.async_mode:
        # 백그라운드 작업으로 처리
        background_tasks.add_task(
            process_tts_with_voice_task,
            task_id,
            request
        )
        
        return ZonosTTSResponse(
            task_id=task_id,
            status="pending",
            message="음성 클로닝 TTS 생성 작업이 시작되었습니다. /task_status/{task_id}로 진행 상황을 확인하세요."
        )
    else:
        # 동기 모드 (즉시 처리)
        await process_tts_with_voice_task(task_id, request)
        result = task_status[task_id]["result"]
        
        return ZonosTTSResponse(
            task_id=task_id,
            status="completed",
            message="음성 클로닝 TTS 생성이 완료되었습니다.",
            audio_path=result["audio_path"],
            s3_info=result["s3_info"]
        )

async def process_tts_with_voice_task(task_id: str, request: ZonosTTSWithVoiceRequest):
    """음성 클로닝 TTS 작업 처리 (백그라운드)"""
    try:
        import base64
        
        # 상태 업데이트
        task_status[task_id]["status"] = "processing"
        task_status[task_id]["progress"] = 10
        task_status[task_id]["message"] = "음성 파일 처리 중..."
        
        # 임시 디렉토리 생성
        temp_dir = Path("/tmp/zonos_tts")
        temp_dir.mkdir(exist_ok=True)
        
        # Base64 디코딩하여 음성 파일 생성
        voice_data = base64.b64decode(request.voice_data_base64)
        temp_voice_path = temp_dir / f"temp_voice_{uuid.uuid4()}.wav"
        
        async with aiofiles.open(temp_voice_path, "wb") as f:
            await f.write(voice_data)
        
        # ThreadPoolExecutor에서 실행
        loop = asyncio.get_event_loop()
        result = await loop.run_in_executor(
            executor,
            _generate_tts_with_voice_sync,
            str(temp_voice_path),
            request.text,
            request.language,
            request.speaking_rate,
            request.pitch_std,
            request.cfg_scale,
            request.emotion,
            request.output_filename
        )
        
        # 임시 파일 삭제
        temp_voice_path.unlink()
        
        output_path = result["output_path"]
        
        # S3 업로드 처리
        s3_info = None
        if request.upload_to_s3:
            try:
                s3_manager = await get_async_s3_manager()
                if not s3_manager.bucket_name:
                    logger.error("S3 bucket name is not configured")
                    raise ValueError("S3 bucket name is not configured")
                
                # 메타데이터 생성
                # S3 메타데이터는 ASCII만 지원하므로 non-ASCII 텍스트는 제외하거나 인코딩
                metadata = {
                    "text_length": str(len(request.text)),
                    "language": request.language,
                    "speaking_rate": str(request.speaking_rate),
                    "pitch_std": str(request.pitch_std),
                    "generated_by": "zonos-tts-with-voice-async"
                }
                
                # S3에 업로드
                s3_info = await s3_manager.upload_file(
                    file_path=str(output_path),
                    object_name=str(Path(output_path).name),
                    folder_prefix=request.s3_folder_prefix,
                    metadata=metadata,
                    public_read=request.s3_public_read
                )
                
                logger.info(f"✅ S3 업로드 완료: {s3_info['key']}")
                
                # 파일 크기 가져오기
                file_size = Path(output_path).stat().st_size if Path(output_path).exists() else None
                
                # 웹훅 전송
                await send_webhook_notification(
                    task_id=task_id,
                    status="completed",
                    s3_url=s3_info.get('url'),
                    s3_key=s3_info.get('key'),
                    duration=None,  # TODO: 실제 오디오 길이 계산 필요
                    file_size=file_size
                )
                
                # S3 업로드 성공 시 로컬 파일 삭제
                try:
                    Path(output_path).unlink()
                    logger.info(f"🗑️ 로컬 파일 삭제 완료: {output_path}")
                except Exception as e:
                    logger.warning(f"로컬 파일 삭제 실패: {e}")
                
            except Exception as e:
                logger.error(f"⚠️ S3 업로드 실패 (로컬 파일은 생성됨): {e}")
        
        # 작업 완료
        task_status[task_id]["status"] = "completed"
        task_status[task_id]["progress"] = 100
        task_status[task_id]["message"] = "음성 클로닝 TTS 생성이 완료되었습니다."
        
        # S3 업로드 성공 시 로컬 경로 제외
        if s3_info:
            task_status[task_id]["result"] = {
                "audio_path": None,  # S3에 업로드되어 로컬 파일 삭제됨
                "s3_info": s3_info
            }
        else:
            task_status[task_id]["result"] = {
                "audio_path": output_path,
                "s3_info": None
            }
        task_status[task_id]["updated_at"] = datetime.utcnow().isoformat()
        
    except Exception as e:
        logger.error(f"❌ 음성 클로닝 TTS 작업 실패 (task_id: {task_id}): {e}")
        task_status[task_id]["status"] = "failed"
        task_status[task_id]["error"] = str(e)
        task_status[task_id]["updated_at"] = datetime.utcnow().isoformat()
        
        # 실패 웹훅 전송
        await send_webhook_notification(
            task_id=task_id,
            status="failed",
            error_message=str(e)
        )

def _generate_tts_with_voice_sync(
    voice_path: str,
    text: str,
    language: str,
    speaking_rate: float,
    pitch_std: float,
    cfg_scale: float,
    emotion: list[float],
    output_filename: Optional[str]
) -> dict:
    """음성 클로닝 TTS 생성 (동기 함수)"""
    # 스피커 임베딩 생성
    wav, sampling_rate = torchaudio.load(voice_path)
    wav = wav.to(device)
    speaker = zonos_model.make_speaker_embedding(wav, sampling_rate)
    
    # 조건 딕셔너리 생성
    cond_dict = make_cond_dict(
        text=text,
        speaker=speaker,
        language=language,
        speaking_rate=speaking_rate,
        emotion=emotion,
        pitch_std=pitch_std
    )
    
    # 조건 준비
    conditioning = zonos_model.prepare_conditioning(cond_dict)
    
    # 코드 생성
    codes = zonos_model.generate(
        conditioning,
        cfg_scale=cfg_scale,
        disable_torch_compile=True,
        progress_bar=False
    )
    
    # 오디오 디코드
    wavs = zonos_model.autoencoder.decode(codes)
    
    # 출력 파일명 설정
    if not output_filename:
        output_filename = f"zonos_tts_voice_{uuid.uuid4()}.wav"
    
    output_path = f"/tmp/zonos_tts/{output_filename}"
    
    # 오디오 저장
    torchaudio.save(
        output_path,
        wavs[0].cpu(),
        zonos_model.autoencoder.sampling_rate
    )
    
    return {"output_path": output_path}

@router.post("/generate_tts_simple", response_model=ZonosTTSResponse)
async def generate_tts_simple(
    background_tasks: BackgroundTasks,
    request: SimpleTTSRequest
):
    """간단한 TTS 생성 (JSON 요청, 기본 설정 사용)"""
    full_request = ZonosTTSRequest(
        text=request.text,
        language=request.language,
        speaking_rate=request.speaking_rate,
        pitch_std=request.pitch_std,
        cfg_scale=request.cfg_scale,
        emotion=request.emotion
    )
    return await generate_tts_async(background_tasks, full_request)

@router.get("/emotions")
async def get_available_emotions():
    """사용 가능한 감정 목록 및 벡터 값 조회"""
    return {
        "emotions": PREDEFINED_EMOTIONS,
        "description": {
            "neutral": "중립적인 감정",
            "happy": "행복한 감정",
            "sad": "슬픈 감정",
            "angry": "화난 감정",
            "fearful": "두려운 감정",
            "disgusted": "역겨운 감정",
            "surprised": "놀란 감정",
            "contempt": "경멸하는 감정"
        },
        "vector_info": "각 감정은 8차원 벡터로 표현됩니다. [neutral, happy, sad, angry, fearful, disgusted, surprised, contempt]"
    }

@router.get("/zonos_status")
async def get_zonos_status():
    """Zonos 모델 상태 확인"""
    active_tasks = sum(1 for task in task_status.values() if task["status"] == "processing")
    pending_tasks = sum(1 for task in task_status.values() if task["status"] == "pending")
    
    return {
        
        "model_loaded": zonos_model is not None,
        "device": str(device) if device else None,
        "cuda_available": torch.cuda.is_available(),
        "active_tasks": active_tasks,
        "pending_tasks": pending_tasks,
        "total_tasks": len(task_status)
    }

class S3ConfigRequest(BaseModel):
    bucket_name: str
    region_name: str = "ap-northeast-2"
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None

@router.post("/configure_s3")
async def configure_s3(request: S3ConfigRequest):
    """S3 설정 구성"""
    try:
        s3_manager = initialize_async_s3_manager(
            bucket_name=request.bucket_name,
            region_name=request.region_name,
            aws_access_key_id=request.aws_access_key_id,
            aws_secret_access_key=request.aws_secret_access_key
        )
        
        # 연결 검증
        await s3_manager.validate_connection()
        
        return {
            "success": True,
            "message": "S3 설정이 완료되었습니다.",
            "bucket": request.bucket_name,
            "region": request.region_name
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"S3 설정 실패: {str(e)}")

@router.get("/s3_status")
async def get_s3_status():
    """S3 연결 상태 확인"""
    try:
        s3_manager = await get_async_s3_manager()
        await s3_manager.validate_connection()
        
        return {
            "connected": True,
            "bucket": s3_manager.bucket_name,
            "region": s3_manager.region_name
        }
    except Exception as e:
        return {
            "connected": False,
            "error": str(e)
        }

# 주기적으로 오래된 작업 정리
async def cleanup_old_tasks():
    """24시간 이상 된 완료/실패 작업 정리"""
    while True:
        try:
            current_time = datetime.utcnow()
            tasks_to_delete = []
            
            for task_id, task in task_status.items():
                if task["status"] in ["completed", "failed"]:
                    created_at = datetime.fromisoformat(task["created_at"])
                    if (current_time - created_at).total_seconds() > 86400:  # 24시간
                        tasks_to_delete.append(task_id)
            
            for task_id in tasks_to_delete:
                # 파일 삭제
                task = task_status[task_id]
                if task.get("result") and task["result"].get("audio_path"):
                    try:
                        Path(task["result"]["audio_path"]).unlink()
                    except (OSError, IOError) as e:
                        logger.warning(f"Failed to delete audio file {task['result']['audio_path']}: {e}")
                del task_status[task_id]
                
            if tasks_to_delete:
                logger.info(f"🧹 {len(tasks_to_delete)}개의 오래된 작업을 정리했습니다.")
                
        except Exception as e:
            logger.error(f"작업 정리 중 오류: {e}")
        
        # 1시간마다 실행
        await asyncio.sleep(3600)

@router.on_event("startup")
async def start_cleanup_task():
    """정리 작업 시작"""
    asyncio.create_task(cleanup_old_tasks())
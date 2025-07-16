import asyncio
import logging
import os
import uuid
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import concurrent.futures

import torch
import torchaudio
from fastapi import APIRouter, HTTPException, File, UploadFile, Form, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
import aiofiles

from zonos.model import Zonos
from zonos.conditioning import make_cond_dict
from app.utils.async_s3_utils import get_async_s3_manager, initialize_async_s3_manager

logger = logging.getLogger(__name__)

router = APIRouter()

# Zonos 모델 전역 변수
zonos_model = None
device = None

# 비동기 작업 상태 추적
task_status: Dict[str, Dict[str, Any]] = {}

# ThreadPoolExecutor for CPU-bound tasks
executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

class ZonosTTSRequest(BaseModel):
    text: str
    language: str = "ko"
    speaking_rate: float = 22.0
    pitch_std: float = 40.0
    cfg_scale: float = 4.0
    output_filename: Optional[str] = None
    upload_to_s3: bool = False
    s3_folder_prefix: str = "zonos-tts"
    s3_public_read: bool = False
    async_mode: bool = True  # 비동기 모드 플래그

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
    """Zonos 모델 초기화"""
    global zonos_model, device
    try:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        logger.info(f"🔧 Zonos 모델 초기화 중... (디바이스: {device})")
        
        zonos_model = Zonos.from_pretrained("Zyphra/Zonos-v0.1-transformer", device=device)
        logger.info("✅ Zonos 모델 초기화 완료")
        return True
    except Exception as e:
        logger.error(f"❌ Zonos 모델 초기화 실패: {e}")
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
    cfg_scale: float
) -> torch.Tensor:
    """동기 TTS 생성 함수 (CPU-bound 작업)"""
    # 조건 딕셔너리 생성
    cond_dict = make_cond_dict(
        text=text,
        speaker=speaker_embedding,
        language=language,
        speaking_rate=speaking_rate,
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

async def process_tts_task(
    task_id: str,
    request: ZonosTTSRequest,
    voice_data: Optional[bytes] = None
):
    """백그라운드에서 TTS 작업 처리"""
    try:
        # 작업 상태 업데이트
        task_status[task_id]["status"] = "processing"
        task_status[task_id]["progress"] = 10
        task_status[task_id]["updated_at"] = datetime.utcnow().isoformat()
        
        # 임시 디렉토리 생성
        temp_dir = Path("/tmp/zonos_tts")
        temp_dir.mkdir(exist_ok=True)
        
        # 스피커 임베딩 생성
        speaker = None
        if voice_data:
            temp_voice_path = temp_dir / f"temp_voice_{task_id}.wav"
            async with aiofiles.open(temp_voice_path, "wb") as f:
                await f.write(voice_data)
            
            # 동기 작업을 비동기로 실행
            loop = asyncio.get_event_loop()
            wav, sampling_rate = await loop.run_in_executor(
                executor,
                torchaudio.load,
                str(temp_voice_path)
            )
            wav = wav.to(device)
            speaker = await loop.run_in_executor(
                executor,
                zonos_model.make_speaker_embedding,
                wav,
                sampling_rate
            )
            
            # 임시 파일 삭제
            temp_voice_path.unlink()
        
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
            request.cfg_scale
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
                s3_manager = get_async_s3_manager()
                
                # 메타데이터 생성
                metadata = {
                    "text": request.text[:100],
                    "language": request.language,
                    "speaking_rate": str(request.speaking_rate),
                    "pitch_std": str(request.pitch_std),
                    "generated_by": "zonos-tts-async",
                    "task_id": task_id
                }
                
                # S3에 비동기 업로드
                async with aiofiles.open(output_path, 'rb') as f:
                    file_data = await f.read()
                
                s3_info = await s3_manager.upload_file_from_bytes(
                    file_data=file_data,
                    object_name=output_filename,
                    folder_prefix=request.s3_folder_prefix,
                    metadata=metadata,
                    public_read=request.s3_public_read
                )
                
                logger.info(f"✅ S3 업로드 완료: {s3_info['key']}")
                
            except Exception as e:
                logger.error(f"⚠️ S3 업로드 실패 (로컬 파일은 생성됨): {e}")
        
        # 작업 완료
        task_status[task_id]["status"] = "completed"
        task_status[task_id]["progress"] = 100
        task_status[task_id]["message"] = "TTS 생성이 완료되었습니다."
        task_status[task_id]["result"] = {
            "audio_path": str(output_path),
            "s3_info": s3_info
        }
        task_status[task_id]["updated_at"] = datetime.utcnow().isoformat()
        
    except Exception as e:
        logger.error(f"❌ TTS 작업 실패 (task_id: {task_id}): {e}")
        task_status[task_id]["status"] = "failed"
        task_status[task_id]["error"] = str(e)
        task_status[task_id]["updated_at"] = datetime.utcnow().isoformat()

@router.post("/generate_tts", response_model=ZonosTTSResponse)
async def generate_tts_async(
    background_tasks: BackgroundTasks,
    request: ZonosTTSRequest,
    voice_file: Optional[UploadFile] = File(None)
):
    """비동기 음성 클로닝을 사용한 TTS 생성"""
    if zonos_model is None:
        raise HTTPException(status_code=500, detail="Zonos 모델이 초기화되지 않았습니다.")
    
    # 작업 ID 생성
    task_id = str(uuid.uuid4())
    
    # 음성 파일 데이터 읽기
    voice_data = None
    if voice_file:
        voice_data = await voice_file.read()
    
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
            request,
            voice_data
        )
        
        return ZonosTTSResponse(
            task_id=task_id,
            status="pending",
            message="TTS 생성 작업이 시작되었습니다. /task_status/{task_id}로 진행 상황을 확인하세요."
        )
    else:
        # 동기 모드 (즉시 처리)
        await process_tts_task(task_id, request, voice_data)
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

@router.post("/generate_tts_simple")
async def generate_tts_simple(
    background_tasks: BackgroundTasks,
    text: str = Form(...)
):
    """간단한 TTS 생성 (기본 설정 사용)"""
    request = ZonosTTSRequest(text=text)
    return await generate_tts_async(background_tasks, request, None)

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
        s3_manager = get_async_s3_manager()
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
                    except:
                        pass
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
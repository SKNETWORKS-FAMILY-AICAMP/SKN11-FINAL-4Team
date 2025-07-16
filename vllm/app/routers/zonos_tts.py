import logging
import os
import uuid
from pathlib import Path
from typing import Optional, Dict, Any

import torch
import torchaudio
from fastapi import APIRouter, HTTPException, File, UploadFile, Form
from fastapi.responses import FileResponse
from pydantic import BaseModel

from zonos.model import Zonos
from zonos.conditioning import make_cond_dict
from app.utils.s3_utils import get_s3_manager, initialize_s3_manager

logger = logging.getLogger(__name__)

router = APIRouter()

# Zonos 모델 전역 변수
zonos_model = None
device = None

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

class ZonosTTSResponse(BaseModel):
    audio_path: str
    message: str
    s3_info: Optional[Dict[str, Any]] = None

class SimpleTTSRequest(BaseModel):
    text: str
    language: str = "ko"
    speaking_rate: float = 22.0
    pitch_std: float = 40.0
    cfg_scale: float = 4.0

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
    initialize_zonos_model()

@router.post("/generate_tts", response_model=ZonosTTSResponse)
async def generate_tts_with_voice_clone(
    request: ZonosTTSRequest,
    voice_file: Optional[UploadFile] = File(None)
):
    """음성 클로닝을 사용한 TTS 생성"""
    if zonos_model is None:
        if not initialize_zonos_model():
            raise HTTPException(status_code=500, detail="Zonos 모델 초기화에 실패했습니다.")
    
    try:
        # 임시 디렉토리 생성
        temp_dir = Path("/tmp/zonos_tts")
        temp_dir.mkdir(exist_ok=True)
        
        # 스피커 임베딩 생성
        if voice_file:
            # 업로드된 음성 파일 사용
            temp_voice_path = temp_dir / f"temp_voice_{uuid.uuid4()}.wav"
            with open(temp_voice_path, "wb") as f:
                f.write(await voice_file.read())
            
            wav, sampling_rate = torchaudio.load(str(temp_voice_path))
            wav = wav.to(device)
            speaker = zonos_model.make_speaker_embedding(wav, sampling_rate)
            
            # 임시 파일 삭제
            temp_voice_path.unlink()
        else:
            # 기본 스피커 임베딩 사용 (빈 텐서)
            speaker = None
        
        # 조건 딕셔너리 생성
        cond_dict = make_cond_dict(
            text=request.text,
            speaker=speaker,
            language=request.language,
            speaking_rate=request.speaking_rate,
            pitch_std=request.pitch_std
        )
        
        # 조건 준비
        logger.info(f"Preparing conditioning with cfg_scale={request.cfg_scale}")
        conditioning = zonos_model.prepare_conditioning(cond_dict)
        
        # 코드 생성
        logger.info("Generating audio codes...")
        codes = zonos_model.generate(
            conditioning, 
            cfg_scale=request.cfg_scale, 
            disable_torch_compile=True,
            progress_bar=False  # 서버 환경에서는 progress bar 비활성화
        )
        
        # 오디오 디코드
        logger.info("Decoding audio...")
        wavs = zonos_model.autoencoder.decode(codes)
        
        # 출력 파일명 설정
        if request.output_filename:
            output_filename = request.output_filename
        else:
            output_filename = f"zonos_tts_{uuid.uuid4()}.wav"
        
        output_path = temp_dir / output_filename
        
        # 오디오 저장
        torchaudio.save(
            str(output_path), 
            wavs[0].cpu(), 
            zonos_model.autoencoder.sampling_rate
        )
        
        logger.info(f"✅ TTS 생성 완료: {output_path}")
        
        # S3 업로드 처리
        s3_info = None
        if request.upload_to_s3:
            try:
                s3_manager = get_s3_manager()
                
                # 메타데이터 생성
                metadata = {
                    "text": request.text[:100],  # 텍스트 일부만 메타데이터로 저장
                    "language": request.language,
                    "speaking_rate": str(request.speaking_rate),
                    "pitch_std": str(request.pitch_std),
                    "generated_by": "zonos-tts"
                }
                
                # S3에 업로드
                s3_info = s3_manager.upload_file(
                    file_path=str(output_path),
                    object_name=output_filename,
                    folder_prefix=request.s3_folder_prefix,
                    metadata=metadata,
                    public_read=request.s3_public_read
                )
                
                logger.info(f"✅ S3 업로드 완료: {s3_info['key']}")
                
            except Exception as e:
                logger.error(f"⚠️ S3 업로드 실패 (로컬 파일은 생성됨): {e}")
                # S3 업로드 실패해도 로컬 파일 경로는 반환
        
        return ZonosTTSResponse(
            audio_path=str(output_path),
            message="TTS 생성이 완료되었습니다.",
            s3_info=s3_info
        )
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"❌ TTS 생성 실패: {e}\n{error_detail}")
        
        # 더 구체적인 에러 메시지 제공
        if "cfg_scale" in str(e):
            raise HTTPException(
                status_code=400, 
                detail="cfg_scale은 1.0이 될 수 없습니다. 1.0보다 크거나 작은 값을 사용하세요. (권장: 2.0 ~ 5.0)"
            )
        elif "CUDA" in str(e) or "cuda" in str(e):
            raise HTTPException(
                status_code=500, 
                detail=f"CUDA 관련 오류가 발생했습니다. GPU 메모리나 드라이버를 확인하세요: {str(e)}"
            )
        else:
            raise HTTPException(status_code=500, detail=f"TTS 생성 실패: {str(e)}")

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

@router.post("/generate_tts_simple", response_model=ZonosTTSResponse)
async def generate_tts_simple(request: SimpleTTSRequest):
    """간단한 TTS 생성 (JSON 요청, 기본 설정 사용)"""
    # SimpleTTSRequest를 ZonosTTSRequest로 변환
    full_request = ZonosTTSRequest(
        text=request.text,
        language=request.language,
        speaking_rate=request.speaking_rate,
        pitch_std=request.pitch_std,
        cfg_scale=request.cfg_scale
    )
    return await generate_tts_with_voice_clone(full_request, None)

@router.get("/zonos_status")
async def get_zonos_status():
    """Zonos 모델 상태 확인"""
    return {
        "model_loaded": zonos_model is not None,
        "device": str(device) if device else None,
        "available": torch.cuda.is_available()
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
        s3_manager = initialize_s3_manager(
            bucket_name=request.bucket_name,
            region_name=request.region_name,
            aws_access_key_id=request.aws_access_key_id,
            aws_secret_access_key=request.aws_secret_access_key
        )
        
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
        s3_manager = get_s3_manager()
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
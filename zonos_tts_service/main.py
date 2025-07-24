"""
Zonos TTS 독립 서비스
별도 프로세스로 실행되어 GPU 격리를 보장
"""

import os
import sys
import torch
import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from typing import Optional
import tempfile
import logging
from datetime import datetime
import traceback

# 환경 변수 로드
from dotenv import load_dotenv
load_dotenv()

# GPU 격리 설정 - 프로세스 시작 시점에 설정
tts_gpu_id = os.getenv('TTS_GPU_ID', '1')
os.environ['CUDA_VISIBLE_DEVICES'] = tts_gpu_id

# 이제 torch를 import하면 지정된 GPU만 보임
import torch
from zonos.tts import Zonos

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = FastAPI(title="Zonos TTS Service", version="1.0.0")

# 전역 변수
zonos_model = None

class TTSRequest(BaseModel):
    text: str
    voice_preset: Optional[str] = "romeo"
    speed: Optional[float] = 1.0

@app.on_event("startup")
async def startup_event():
    """서비스 시작 시 모델 초기화"""
    global zonos_model
    
    try:
        logger.info(f"🎵 Zonos TTS Service 시작...")
        logger.info(f"📍 물리적 GPU {tts_gpu_id} 사용 (CUDA_VISIBLE_DEVICES={os.environ['CUDA_VISIBLE_DEVICES']})")
        
        if torch.cuda.is_available():
            # 격리된 환경에서는 항상 device 0
            device = torch.device("cuda:0")
            logger.info(f"✅ GPU 사용 가능. 논리적 GPU 0 사용 (물리적 GPU {tts_gpu_id})")
            logger.info(f"🔧 사용 가능한 GPU 수: {torch.cuda.device_count()}")
            logger.info(f"🔧 GPU 이름: {torch.cuda.get_device_name(0)}")
            
            # GPU 메모리 사용률 제한
            memory_fraction = float(os.getenv('TTS_GPU_MEMORY_UTILIZATION', '0.3'))
            torch.cuda.set_per_process_memory_fraction(memory_fraction, device=0)
            logger.info(f"💾 GPU 메모리 사용률 제한: {memory_fraction * 100}%")
        else:
            device = torch.device("cpu")
            logger.warning("⚠️ GPU를 사용할 수 없습니다. CPU 모드로 실행합니다.")
        
        # Zonos 모델 로드
        logger.info("🔄 Zonos 모델 로딩 중...")
        zonos_model = Zonos.from_pretrained("Zyphra/Zonos-v0.1-transformer", device=device)
        logger.info("✅ Zonos 모델 로드 완료!")
        
    except Exception as e:
        logger.error(f"❌ Zonos 모델 초기화 실패: {e}")
        logger.error(traceback.format_exc())
        # 서비스는 계속 실행되도록 함

@app.get("/")
async def root():
    """헬스 체크"""
    return {
        "service": "Zonos TTS Service",
        "status": "running" if zonos_model is not None else "model_not_loaded",
        "gpu": tts_gpu_id,
        "cuda_available": torch.cuda.is_available()
    }

@app.post("/generate")
async def generate_speech(request: TTSRequest):
    """음성 생성 엔드포인트"""
    if zonos_model is None:
        raise HTTPException(status_code=503, detail="모델이 로드되지 않았습니다.")
    
    try:
        logger.info(f"🎤 음성 생성 요청: {len(request.text)} 글자")
        
        # 임시 파일 생성
        with tempfile.NamedTemporaryFile(delete=False, suffix='.wav') as tmp_file:
            output_path = tmp_file.name
        
        # 음성 생성
        zonos_model.tts(
            text=request.text,
            voice_preset=request.voice_preset,
            output_path=output_path,
            speed=request.speed
        )
        
        logger.info(f"✅ 음성 생성 완료: {output_path}")
        
        # 파일 응답
        return FileResponse(
            output_path,
            media_type='audio/wav',
            filename=f'speech_{datetime.now().strftime("%Y%m%d_%H%M%S")}.wav'
        )
        
    except Exception as e:
        logger.error(f"❌ 음성 생성 실패: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/gpu-info")
async def gpu_info():
    """GPU 정보 조회"""
    if torch.cuda.is_available():
        return {
            "cuda_available": True,
            "device_count": torch.cuda.device_count(),
            "current_device": torch.cuda.current_device(),
            "device_name": torch.cuda.get_device_name(0),
            "memory_allocated": f"{torch.cuda.memory_allocated(0) / 1024**2:.2f} MB",
            "memory_reserved": f"{torch.cuda.memory_reserved(0) / 1024**2:.2f} MB",
            "physical_gpu_id": tts_gpu_id
        }
    else:
        return {"cuda_available": False}

if __name__ == "__main__":
    # 독립 실행
    port = int(os.getenv('TTS_SERVICE_PORT', '8002'))
    uvicorn.run(app, host="0.0.0.0", port=port)
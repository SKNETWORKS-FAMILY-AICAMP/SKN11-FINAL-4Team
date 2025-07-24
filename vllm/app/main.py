import logging
import os
import dotenv
import traceback
import subprocess
import sys
import signal
import asyncio
import atexit

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core import startup_event
from app.routers import lora, generation, finetuning, speech, qa_generation, backend_utils, zonos_tts_client

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 환경 변수 로드
dotenv.load_dotenv()

# Zonos TTS 프로세스 전역 변수
zonos_process = None

async def start_zonos_tts_service():
    """Zonos TTS 서비스를 별도 프로세스로 시작"""
    global zonos_process
    
    try:
        # Zonos TTS 서비스가 이미 실행 중인지 확인
        import httpx
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get("http://localhost:8002/", timeout=2.0)
                if response.status_code == 200:
                    logger.info("✅ Zonos TTS 서비스가 이미 실행 중입니다.")
                    return
            except:
                pass
        
        # GPU 설정
        tts_gpu_id = os.getenv('TTS_GPU_ID', '1')
        
        # Zonos TTS 서비스 시작
        logger.info(f"🎵 Zonos TTS 서비스 시작 중... (GPU {tts_gpu_id})")
        
        # Python 경로 가져오기
        python_path = sys.executable
        
        # 환경 변수 설정
        env = os.environ.copy()
        env['CUDA_VISIBLE_DEVICES'] = tts_gpu_id
        env['TTS_GPU_ID'] = tts_gpu_id
        
        # zonos_tts_service 경로
        zonos_service_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "..", "zonos_tts_service", "main.py")
        
        # 프로세스 시작
        zonos_process = subprocess.Popen(
            [python_path, zonos_service_path],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            preexec_fn=os.setsid if os.name != 'nt' else None
        )
        
        # 서비스가 시작될 때까지 대기
        await asyncio.sleep(5)
        
        # 서비스 상태 확인
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get("http://localhost:8002/", timeout=5.0)
                if response.status_code == 200:
                    logger.info("✅ Zonos TTS 서비스가 성공적으로 시작되었습니다.")
                else:
                    raise Exception("Zonos TTS 서비스 응답 오류")
            except Exception as e:
                logger.error(f"❌ Zonos TTS 서비스 시작 실패: {e}")
                if zonos_process:
                    zonos_process.terminate()
                    zonos_process = None
                raise
                
    except Exception as e:
        logger.error(f"❌ Zonos TTS 서비스 시작 중 오류: {e}")
        logger.error(traceback.format_exc())

def stop_zonos_tts_service():
    """Zonos TTS 서비스 종료"""
    global zonos_process
    
    if zonos_process:
        try:
            logger.info("🛑 Zonos TTS 서비스 종료 중...")
            if os.name != 'nt':
                os.killpg(os.getpgid(zonos_process.pid), signal.SIGTERM)
            else:
                zonos_process.terminate()
            zonos_process.wait(timeout=5)
            logger.info("✅ Zonos TTS 서비스가 종료되었습니다.")
        except Exception as e:
            logger.error(f"❌ Zonos TTS 서비스 종료 실패: {e}")
            if zonos_process:
                zonos_process.kill()
        finally:
            zonos_process = None

# 프로그램 종료 시 Zonos TTS 서비스도 함께 종료
atexit.register(stop_zonos_tts_service)

# FastAPI 앱 생성
app = FastAPI(
    title="vLLM LoRA Influencer API", 
    version="1.0.0",
    description="vLLM 엔진을 사용한 LoRA 파인튜닝 및 추론 API"
)

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.on_event("startup")
async def on_startup():
    logger.info("🚀 FastAPI 서버 시작 중...")
    try:
        # Zonos TTS 서비스 자동 시작
        await start_zonos_tts_service()
        
        # vLLM 코어 초기화
        await startup_event()
        logger.info("✅ FastAPI 서버 초기화 완료")
    except Exception as e:
        logger.error(f"❌ FastAPI 서버 초기화 실패: {e}")
        # 서버는 계속 실행하되 초기화 실패를 로그에 남김

@app.on_event("shutdown")
async def on_shutdown():
    """서버 종료 시 정리 작업"""
    logger.info("🛑 FastAPI 서버 종료 중...")
    stop_zonos_tts_service()

@app.get("/")
async def root():
    return {"message": "vLLM LoRA Influencer API가 실행 중입니다!"}

@app.get("/health")
async def health_check():
    """서버 상태 확인 엔드포인트"""
    from app.core import engine, finetuning_queue, speech_generator, tokenizer
    
    status = "ok"
    components = {
        "engine": engine is not None,
        "tokenizer": tokenizer is not None,
        "finetuning_queue": finetuning_queue is not None,
        "speech_generator": speech_generator is not None
    }
    
    if not all(components.values()):
        status = "initializing"
    
    return {
        "status": status,
        "message": "vLLM LoRA Influencer API 서버가 정상적으로 실행 중입니다.",
        "components": components
    }

# 전역 예외 핸들러
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    logger.error(f"❌ 글로벌 예외 발생 - URL: {request.url}")
    logger.error(f"❌ 예외 타입: {type(exc).__name__}")
    logger.error(f"❌ 예외 메시지: {str(exc)}")
    logger.error(f"❌ 전체 스택 트레이스: {traceback.format_exc()}")
    
    return JSONResponse(
        status_code=500,
        content={
            "detail": f"서버 내부 오류: {str(exc)}",
            "type": type(exc).__name__,
            "url": str(request.url)
        }
    )

# 라우터 등록
app.include_router(lora.router, prefix="/lora", tags=["LoRA Adapters"])
app.include_router(generation.router, tags=["Generation"])
app.include_router(finetuning.router, tags=["FineTuning"])
app.include_router(speech.router, prefix="/speech", tags=["Speech Generator"])
app.include_router(qa_generation.router, prefix="/qa", tags=["QA Generation"])
app.include_router(backend_utils.router, prefix="/api/v1", tags=["Backend Utils"])
app.include_router(zonos_tts_client.router, prefix="/zonos", tags=["Zonos TTS Client"])

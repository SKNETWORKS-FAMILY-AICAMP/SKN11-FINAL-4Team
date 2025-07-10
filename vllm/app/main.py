import logging
import os
import dotenv
import traceback

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core import startup_event
from app.routers import lora, generation, finetuning, speech, qa_generation, backend_utils

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# 환경 변수 로드
dotenv.load_dotenv()

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
        await startup_event()
        logger.info("✅ FastAPI 서버 초기화 완료")
    except Exception as e:
        logger.error(f"❌ FastAPI 서버 초기화 실패: {e}")
        # 서버는 계속 실행하되 초기화 실패를 로그에 남김

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

import asyncio
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import os

# .env 파일 로드
load_dotenv()

from app.api.v1.api import api_router
from app.database import init_database
from app.services.mcp_server_manager import mcp_server_manager

# 로깅 설정
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    # 시작 시 실행
    logger.info("🚀 애플리케이션을 시작합니다...")

    # 데이터베이스 초기화
    init_database()
    logger.info("✅ 데이터베이스 초기화 완료")

    # MCP 서버들을 시작
    try:
        await mcp_server_manager.start_all_servers()
        logger.info("✅ MCP 서버들 시작 완료")
    except Exception as e:
        logger.error(f"❌ MCP 서버 시작 실패: {e}")

    yield

    # 종료 시 실행
    logger.info("🛑 애플리케이션을 종료합니다...")

    # MCP 서버들 중지
    await mcp_server_manager.stop_all_servers()
    logger.info("✅ MCP 서버들 종료 완료")


# FastAPI 애플리케이션 생성
app = FastAPI(
    title="AI Influencer Platform API",
    description="AI 인플루언서 플랫폼 백엔드 API",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 프로덕션에서는 특정 도메인으로 제한
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 라우터 등록
app.include_router(api_router, prefix="/api/v1")


@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "message": "AI Influencer Platform API",
        "version": "1.0.0",
        "status": "running",
    }


@app.get("/health")
async def health_check():
    """헬스 체크 엔드포인트"""
    return {"status": "healthy"}

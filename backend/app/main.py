from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.middleware.base import BaseHTTPMiddleware
import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from app.core.config import settings
from app.database import init_database, test_database_connection
from app.api.v1.api import api_router
from app.services.startup_service import run_startup_tasks
from app.services.batch_monitor import start_batch_monitoring, stop_batch_monitoring
from app.services.scheduler_service import scheduler_service

# 세션 정리 서비스 - 비동기로 수정 완료
from app.services.session_cleanup_service import (
    start_session_cleanup_service,
    stop_session_cleanup_service,
)

# 로깅 설정
if settings.DEBUG:
    # 개발 환경에서는 더 상세한 로깅
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s",
        handlers=[
            logging.StreamHandler(),  # 콘솔 출력
        ],
    )
    # SQLAlchemy 로그 비활성화 (디버깅 시 불편함)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
    logging.getLogger("app").setLevel(logging.DEBUG)
else:
    # 프로덕션 환경에서는 기존 설정 유지
    logging.basicConfig(
        level=getattr(logging, settings.LOG_LEVEL), format=settings.LOG_FORMAT
    )

logger = logging.getLogger(__name__)

# 기타 외부 라이브러리 로그 비활성화
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.pool").setLevel(logging.WARNING)
logging.getLogger("sqlalchemy.dialects").setLevel(logging.WARNING)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """애플리케이션 생명주기 관리"""
    # 시작 시 실행
    logger.info("🚀 Starting AIMEX API Server...")

    # MCP 서버 자동 실행 (데이터베이스에서 로드)
    try:
        from app.services.mcp_server_manager import get_mcp_server_manager

        # 데이터베이스 기반 MCP 서버 매니저 가져오기
        mcp_manager = get_mcp_server_manager()

        # 모든 서버 시작
        await mcp_manager.start_all_servers()
        logger.info("✅ 데이터베이스의 모든 MCP 서버 자동 실행 완료")

    except Exception as e:
        logger.error(f"❌ MCP 서버 자동 실행 실패: {e}")

    # 데이터베이스 연결 테스트
    if not test_database_connection():
        logger.error("❌ Database connection failed")
        raise Exception("Database connection failed")

    # 시작시 작업 실행 (QA 데이터 있지만 파인튜닝 시작 안된 작업들 자동 재시작)
    try:
        await run_startup_tasks()
    except Exception as e:
        logger.warning(f"⚠️ Startup tasks failed, but continuing: {e}")

    # 배치 모니터링 시작 (폴링 모드인 경우)
    try:
        await start_batch_monitoring()
        logger.info(f"🔄 배치 모니터링 모드: {settings.OPENAI_MONITORING_MODE}")
    except Exception as e:
        logger.warning(f"⚠️ Batch monitoring failed to start, but continuing: {e}")

    # 스케줄러 서비스 시작
    try:
        await scheduler_service.start()
        logger.info("📅 스케줄러 서비스 시작 완료")
    except Exception as e:
        logger.warning(f"⚠️ Scheduler service failed to start, but continuing: {e}")

    # 세션 정리 서비스 활성화 (비동기 수정 완료)
    try:
        await start_session_cleanup_service()
        logger.info("🧹 세션 정리 서비스 시작 완료")
    except Exception as e:
        logger.warning(
            f"⚠️ Session cleanup service failed to start, but continuing: {e}"
        )

    logger.info("✅ AIMEX API Server ready")

    yield

    # 종료 시 실행
    logger.info("🛑 Shutting down AIMEX API Server...")

    # MCP 서버들 중지
    try:
        from app.services.mcp_server_manager import mcp_server_manager

        await mcp_server_manager.stop_all_servers()
        logger.info("✅ 모든 MCP 서버가 정상적으로 중지되었습니다")
    except Exception as e:
        logger.error(f"❌ MCP 서버 중지 중 오류: {e}")

    # 배치 모니터링 중지
    try:
        await stop_batch_monitoring()
        logger.info("✅ 배치 모니터링이 정상적으로 중지되었습니다")
    except Exception as e:
        logger.error(f"❌ 배치 모니터링 중지 중 오류: {e}")

    # 스케줄러 서비스 중지
    try:
        await scheduler_service.stop()
        logger.info("✅ 스케줄러 서비스가 정상적으로 중지되었습니다")
    except Exception as e:
        logger.error(f"❌ 스케줄러 서비스 중지 중 오류: {e}")

    # 세션 정리 서비스 활성화 (비동기 수정 완료)
    try:
        await stop_session_cleanup_service()
        logger.info("✅ 세션 정리 서비스가 정상적으로 중지되었습니다")
    except Exception as e:
        logger.error(f"❌ 세션 정리 서비스 중지 중 오류: {e}")


# FastAPI 애플리케이션 생성
app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description="AI Influencer Model Management System API",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
    # 타임아웃 설정 추가
    timeout=300,  # 5분
)

# CORS 미들웨어 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.BACKEND_CORS_ORIGINS if not settings.DEBUG else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400,  # CORS preflight 캐시 24시간
)

# 신뢰할 수 있는 호스트 미들웨어 (보안 강화)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["*"])


# 파일 업로드 크기 제한 미들웨어
class FileSizeMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, max_size: int = 50 * 1024 * 1024):  # 50MB
        super().__init__(app)
        self.max_size = max_size

    async def dispatch(self, request: Request, call_next):
        if request.method == "POST" and "multipart/form-data" in request.headers.get(
            "content-type", ""
        ):
            content_length = request.headers.get("content-length")
            if content_length and int(content_length) > self.max_size:
                return JSONResponse(
                    status_code=413,
                    content={
                        "detail": f"File too large. Maximum size is {self.max_size} bytes"
                    },
                )

        response = await call_next(request)
        return response


# app.add_middleware(FileSizeMiddleware)  # 임시 비활성화


# 요청 로깅 미들웨어
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """요청/응답 로깅"""
    start_time = time.time()

    # 요청 로깅
    client_host = request.client.host if request.client else "unknown"
    logger.info(f"📥 {request.method} {request.url.path} - {client_host}")

    response = await call_next(request)

    # 응답 로깅
    process_time = time.time() - start_time
    logger.info(
        f"📤 {request.method} {request.url.path} - {response.status_code} ({process_time:.3f}s)"
    )

    return response


# 예외 처리 핸들러
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """HTTP 예외 처리"""
    logger.error(f"HTTP Exception: {exc.status_code} - {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": "HTTP Error",
            "status_code": exc.status_code,
            "detail": exc.detail,
            "path": request.url.path,
        },
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """요청 검증 예외 처리"""
    logger.error(f"Validation Error: {exc.errors()}")
    return JSONResponse(
        status_code=422,
        content={
            "error": "Validation Error",
            "detail": exc.errors(),
            "path": request.url.path,
        },
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """일반 예외 처리"""
    logger.error(f"Unexpected Error: {str(exc)}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "detail": "An unexpected error occurred",
            "path": request.url.path,
        },
    )


# 헬스 체크 엔드포인트
@app.get("/health")
async def health_check():
    """서버 상태 확인"""
    try:
        # 데이터베이스 연결 확인
        db_healthy = test_database_connection()

        return {
            "status": "healthy" if db_healthy else "unhealthy",
            "database": "connected" if db_healthy else "disconnected",
            "timestamp": time.time(),
            "version": settings.VERSION,
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "error": str(e), "timestamp": time.time()},
        )


# 루트 엔드포인트
@app.get("")
async def root():
    """루트 엔드포인트"""
    logger.info("🏠 루트 엔드포인트 접근")
    return {
        "message": "Welcome to AIMEX API",
        "version": settings.VERSION,
        "docs": "/docs" if settings.DEBUG else "Documentation disabled in production",
        "health": "/health",
    }


# 개발용 로그 테스트 엔드포인트
@app.get("/test-logs")
async def test_logs():
    """로그 테스트 엔드포인트"""
    logger.debug("🔍 DEBUG 레벨 로그 테스트")
    logger.info("ℹ️ INFO 레벨 로그 테스트")
    logger.warning("⚠️ WARNING 레벨 로그 테스트")
    logger.error("❌ ERROR 레벨 로그 테스트")

    return {
        "message": "로그 테스트 완료",
        "debug_mode": settings.DEBUG,
        "log_level": settings.LOG_LEVEL,
    }


# API 라우터 등록
app.include_router(api_router, prefix=settings.API_V1_STR)
# S3 전용 이미지 서빙 (로컬 uploads 디렉토리 제거)
# app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

# 버전 없는 라우터 추가 (하위 호환성)
from app.api.v1.endpoints.auth import router as auth_router

app.include_router(auth_router, prefix="/api/auth", tags=["Authentication (Legacy)"])


# 개발 환경에서만 추가 정보 출력
if settings.DEBUG:

    @app.on_event("startup")
    async def startup_event():
        """개발 환경 시작 이벤트"""
        logger.info("🔧 Development mode enabled")
        logger.info(f"📚 API Documentation: {settings.BACKEND_CORS_ORIGINS[0]}/docs")
        logger.info(f"🔍 ReDoc: {settings.BACKEND_CORS_ORIGINS[0]}/redoc")
        logger.info(f"💚 Health Check: {settings.BACKEND_CORS_ORIGINS[0]}/health")

        # 챗봇 옵션이 활성화된 인플루언서들의 vLLM 어댑터 자동 로드
        try:
            from app.database import get_db
            from app.services.startup_service import (
                load_adapters_for_chat_enabled_influencers,
            )

            db = next(get_db())
            await load_adapters_for_chat_enabled_influencers(db)
        except Exception as e:
            logger.warning(f"⚠️ 시작 시 챗봇 인플루언서 어댑터 로드 실패: {str(e)}")

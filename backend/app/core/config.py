from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import List, Optional
import secrets

class Settings(BaseSettings):
    # model_config는 .env 파일을 읽도록 설정합니다.
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding='utf-8', extra='allow')

    # API 설정
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "AIMEX API"
    VERSION: str = "1.0.0"
    DEBUG: bool = False

    # 데이터베이스 설정
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20
    DATABASE_POOL_TIMEOUT: int = 30

    # 보안 설정
    SECRET_KEY: str = secrets.token_urlsafe(32)
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days

    # CORS 설정
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "https://localhost:3000",
        "http://127.0.0.1:3000",
        "https://localhost:3001",
    ]

    # 외부 서비스 API 키
    OPENAI_API_KEY: Optional[str] = None
    RUNPOD_API_KEY: Optional[str] = None
    RUNPOD_TEMPLATE_ID: Optional[str] = None
    RUNPOD_VOLUME_ID: Optional[str] = None
    
    # RunPod 기타 설정
    RUNPOD_CUSTOM_TEMPLATE_ID: Optional[str] = None
    RUNPOD_GPU_TYPE: str = "NVIDIA_RTX_4090"
    RUNPOD_MAX_WORKERS: int = 1
    RUNPOD_IDLE_TIMEOUT: int = 300
    
    # AWS S3 설정
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "ap-northeast-2"
    S3_BUCKET_NAME: Optional[str] = None
    S3_ENABLED: bool = True

    # 소셜 로그인 설정
    GOOGLE_CLIENT_ID: Optional[str] = None
    GOOGLE_CLIENT_SECRET: Optional[str] = None

    # VLLM 서버 설정
    VLLM_ENABLED: bool = False
    VLLM_HOST: str = "localhost"
    VLLM_PORT: int = 8000
    VLLM_TIMEOUT: int = 300
    VLLM_SERVER_URL: Optional[str] = None
    VLLM_BASE_URL: Optional[str] = None

    @model_validator(mode='after')
    def compute_vllm_base_url(self) -> 'Settings':
        if self.VLLM_ENABLED:
            if self.VLLM_SERVER_URL:
                self.VLLM_BASE_URL = self.VLLM_SERVER_URL
            else:
                self.VLLM_BASE_URL = f"http://{self.VLLM_HOST}:{self.VLLM_PORT}"
        else:
            self.VLLM_BASE_URL = None
        return self

# 설정 인스턴스 생성
settings = Settings()

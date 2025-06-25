from pydantic_settings import BaseSettings
from typing import Optional, List
import os
from dotenv import load_dotenv

load_dotenv()


class Settings(BaseSettings):
    # API 설정
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "AIMEX API"
    VERSION: str = "1.0.0"

    # 데이터베이스 설정
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "mysql+pymysql://root:password@localhost:3306/AIMEX_MAIN"
    )

    # 보안 설정
    SECRET_KEY: str = os.getenv(
        "SECRET_KEY", "your-secret-key-here-change-in-production"
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    # CORS 설정
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",  # Next.js frontend
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ]

    # 허깅페이스 설정
    HUGGINGFACE_API_URL: str = "https://api.huggingface.co"

    class Config:
        env_file = ".env"


settings = Settings()

#!/usr/bin/env python3
"""
vLLM FastAPI 서버 실행 스크립트
"""
import os
import uvicorn
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

def main():
    """FastAPI 서버 실행"""
    host = os.getenv("FASTAPI_HOST", "0.0.0.0")
    port = int(os.getenv("FASTAPI_PORT", "8000"))
    
    print(f"🚀 vLLM FastAPI 서버 시작: {host}:{port}")
    
    uvicorn.run(
        "main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
        access_log=True
    )

if __name__ == "__main__":
    main()
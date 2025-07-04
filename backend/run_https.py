import uvicorn
from app.main import app

if __name__ == "__main__":
    # HTTPS로 실행 (개발 환경용 self-signed certificate)
    uvicorn.run(
        "app.main:app", 
        host="localhost", 
        port=8000, 
        reload=False, 
        log_level="info",
        ssl_keyfile="../frontend/certificates/key.pem",   # 인증서 키 파일
        ssl_certfile="../frontend/certificates/cert.pem"   # 인증서 파일
    )

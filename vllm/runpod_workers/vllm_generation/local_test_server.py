"""
로컬 테스트를 위한 RunPod Mock 서버
"""
import asyncio
import json
import logging
import time
from typing import Dict, Any
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel
import uvicorn

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# FastAPI 앱
app = FastAPI(title="vLLM Worker Local Test Server")

# 요청 모델
class GenerationRequest(BaseModel):
    prompt: str = None
    messages: list = None
    system_message: str = "당신은 도움이 되는 AI 어시스턴트입니다."
    influencer_name: str = None
    temperature: float = 0.7
    max_tokens: int = 512
    top_p: float = 0.9
    top_k: int = 50
    repetition_penalty: float = 1.1
    stop_sequences: list = None
    lora_adapter: Any = None
    hf_token: str = None
    stream: bool = False
    n: int = 1

# 전역 변수로 worker 함수 저장
worker_handler = None
worker_sync_handler = None
worker_stream_handler = None

def load_worker():
    """워커 모듈 로드"""
    global worker_handler, worker_sync_handler, worker_stream_handler
    
    try:
        # generation_worker 모듈 임포트
        import generation_worker
        
        # 핸들러 함수 가져오기
        worker_handler = generation_worker.handler
        worker_sync_handler = generation_worker.sync_handler
        worker_stream_handler = generation_worker.stream_handler
        
        logger.info("✅ 워커 모듈 로드 완료")
        return True
    except Exception as e:
        logger.error(f"❌ 워커 모듈 로드 실패: {e}")
        return False

@app.on_event("startup")
async def startup_event():
    """서버 시작 시 워커 로드"""
    if not load_worker():
        logger.error("워커를 로드할 수 없습니다. 서버를 종료합니다.")
        exit(1)

@app.get("/")
async def root():
    """루트 엔드포인트"""
    return {
        "message": "vLLM Worker Local Test Server",
        "endpoints": {
            "/generate": "동기 텍스트 생성",
            "/generate/async": "비동기 텍스트 생성 (멀티 요청)",
            "/generate/stream": "스트리밍 텍스트 생성",
            "/test": "테스트 요청 전송"
        }
    }

@app.post("/generate")
async def generate(request: GenerationRequest):
    """동기 텍스트 생성 엔드포인트"""
    try:
        # RunPod 형식으로 변환
        job = {
            "input": request.dict()
        }
        
        logger.info(f"📥 동기 생성 요청: {request.prompt or request.messages}")
        
        # 워커 핸들러 호출
        result = worker_sync_handler(job)
        
        return JSONResponse(content=result)
        
    except Exception as e:
        logger.error(f"❌ 생성 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate/async")
async def generate_async(request: GenerationRequest):
    """비동기 텍스트 생성 엔드포인트 (멀티 요청 지원)"""
    try:
        # RunPod 형식으로 변환
        job = {
            "input": request.dict()
        }
        
        logger.info(f"📥 비동기 생성 요청: {request.prompt or request.messages}")
        
        # 워커 핸들러 호출 (멀티 vLLM)
        result = worker_handler(job)
        
        return JSONResponse(content=result)
        
    except Exception as e:
        logger.error(f"❌ 생성 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/generate/stream")
async def generate_stream(request: GenerationRequest):
    """스트리밍 텍스트 생성 엔드포인트"""
    try:
        # 스트리밍 강제 설정
        request.stream = True
        
        # RunPod 형식으로 변환
        job = {
            "input": request.dict()
        }
        
        logger.info(f"📥 스트리밍 생성 요청: {request.prompt or request.messages}")
        
        # 워커 스트림 핸들러 호출
        result = worker_stream_handler(job)
        
        # 스트리밍 ID 반환
        return JSONResponse(content=result)
        
    except Exception as e:
        logger.error(f"❌ 스트리밍 생성 오류: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/test")
async def test():
    """테스트 요청 전송"""
    test_requests = [
        # 1. 베이스 모델 테스트
        {
            "prompt": "인공지능의 미래에 대해 설명해주세요.",
            "max_tokens": 100,
            "temperature": 0.7
        },
        
        # 2. 채팅 형식 테스트
        {
            "messages": [
                {"role": "system", "content": "당신은 친절한 AI 어시스턴트입니다."},
                {"role": "user", "content": "Python으로 피보나치 수열을 구현하는 방법을 알려주세요."}
            ],
            "max_tokens": 200,
            "temperature": 0.5
        },
        
        # 3. 인플루언서 모드 테스트
        {
            "prompt": "오늘 날씨가 정말 좋네요!",
            "influencer_name": "긍정적인 친구",
            "system_message": "당신은 항상 긍정적이고 밝은 에너지를 가진 친구입니다.",
            "max_tokens": 150,
            "temperature": 0.8
        },
        
        # 4. LoRA 어댑터 테스트 (존재하는 경우)
        {
            "prompt": "머신러닝과 딥러닝의 차이점을 설명해주세요.",
            "lora_adapter": "hf://example/test-adapter",  # 실제 어댑터로 변경 필요
            "max_tokens": 200,
            "temperature": 0.6
        }
    ]
    
    results = []
    
    for i, test_req in enumerate(test_requests):
        try:
            logger.info(f"\n{'='*50}")
            logger.info(f"테스트 {i+1}: {test_req.get('prompt', test_req.get('messages'))}")
            
            request = GenerationRequest(**test_req)
            
            # 동기 생성 호출
            job = {"input": request.dict()}
            result = worker_sync_handler(job)
            
            results.append({
                "test_number": i + 1,
                "request": test_req,
                "result": result
            })
            
            if result.get("status") == "success":
                logger.info(f"✅ 테스트 {i+1} 성공")
                logger.info(f"생성된 텍스트: {result.get('generated_text')[:100]}...")
            else:
                logger.error(f"❌ 테스트 {i+1} 실패: {result.get('error')}")
                
        except Exception as e:
            logger.error(f"❌ 테스트 {i+1} 오류: {e}")
            results.append({
                "test_number": i + 1,
                "request": test_req,
                "error": str(e)
            })
    
    return {
        "total_tests": len(test_requests),
        "results": results
    }

@app.get("/health")
async def health():
    """헬스체크 엔드포인트"""
    return {"status": "healthy", "timestamp": time.time()}

if __name__ == "__main__":
    # 서버 실행
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
import asyncio
import logging
import os
import uuid
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime
import concurrent.futures
import httpx
import multiprocessing as mp
from multiprocessing import Queue, Process
import signal
import sys

import torch
from sentence_transformers import SentenceTransformer
from fastapi import APIRouter, HTTPException, BackgroundTasks
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field, validator
import aiofiles

# 멀티프로세싱 시작 방식 설정
mp.set_start_method('spawn', force=True)

logger = logging.getLogger(__name__)

router = APIRouter()

# 임베딩 모델 전역 변수
embedding_model = None
embedding_device = None
embedding_initialization_attempted = False

# 멀티프로세싱 관련 전역 변수
embedding_process = None
embedding_request_queue = None
embedding_response_queue = None

# 비동기 작업 상태 추적
task_status: Dict[str, Dict[str, Any]] = {}

# ThreadPoolExecutor for CPU-bound tasks (managed)
executor = None
executor_lock = asyncio.Lock()

async def get_executor():
    """Get or create ThreadPoolExecutor instance (thread-safe)"""
    global executor
    async with executor_lock:
        if executor is None:
            executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)
    return executor

async def shutdown_executor():
    """Properly shutdown the ThreadPoolExecutor"""
    global executor
    async with executor_lock:
        if executor is not None:
            executor.shutdown(wait=True)
            executor = None

class EmbeddingRequest(BaseModel):
    """임베딩 요청 모델"""
    texts: List[str]
    model_name: Optional[str] = "BAAI/bge-m3"
    device: Optional[str] = None
    batch_size: Optional[int] = 32

class EmbeddingResponse(BaseModel):
    """임베딩 응답 모델"""
    embeddings: List[List[float]]
    dimension: int
    model_name: str
    device: str
    batch_size: int

def embedding_worker_process(request_queue: Queue, response_queue: Queue):
    """임베딩 모델 워커 프로세스"""
    def signal_handler(signum, frame):
        logger.info("🛑 임베딩 워커 프로세스 종료 신호 수신")
        sys.exit(0)
    
    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)
    
    # GPU 1 전용 환경 설정
    rag_gpu_id = int(os.getenv('RAG_GPU_ID', '1'))
    
    # 부모 프로세스의 CUDA_VISIBLE_DEVICES를 무시하고 새로 설정
    if 'CUDA_VISIBLE_DEVICES' in os.environ:
        logger.info(f"⚠️ 부모 프로세스의 CUDA_VISIBLE_DEVICES={os.environ['CUDA_VISIBLE_DEVICES']} 무시")
    
    os.environ['CUDA_VISIBLE_DEVICES'] = str(rag_gpu_id)
    
    logger.info(f"🔍 임베딩 워커 시작")
    logger.info(f"🖥️ CUDA_VISIBLE_DEVICES={os.environ['CUDA_VISIBLE_DEVICES']} (물리적 GPU {rag_gpu_id})")
    logger.info(f"📍 RAG 임베딩은 GPU {rag_gpu_id}번에서 실행됩니다")
    
    # 이 프로세스 내에서 torch와 SentenceTransformer 임포트
    import torch
    from sentence_transformers import SentenceTransformer
    
    # GPU 설정 확인
    if torch.cuda.is_available():
        logger.info(f"✅ CUDA 사용 가능 - GPU 개수: {torch.cuda.device_count()}")
        logger.info(f"🖥️ 현재 GPU 디바이스: cuda:{torch.cuda.current_device()}")
        logger.info(f"📊 GPU 이름: {torch.cuda.get_device_name(0)}")
    else:
        logger.error("❌ CUDA를 사용할 수 없습니다!")
    
    # 모델 초기화
    try:
        if torch.cuda.is_available():
            # CUDA 초기화 전에 디바이스 설정
            torch.cuda.set_device(0)  # 격리된 환경에서는 항상 0
            device = torch.device("cuda:0")
            logger.info(f"🔧 임베딩 워커 초기화 중... (격리된 GPU {rag_gpu_id}, 디바이스: cuda:0)")
            
            # CUDA 메모리 정리
            torch.cuda.empty_cache()
        else:
            device = torch.device("cpu")
            logger.warning("⚠️ CUDA를 사용할 수 없습니다. CPU를 사용합니다.")
        
        # 토크나이저 병렬화 비활성화
        os.environ['TOKENIZERS_PARALLELISM'] = 'false'
        
        embedding_model = SentenceTransformer("BAAI/bge-m3", device=device)
        logger.info("✅ 임베딩 워커 모델 초기화 완료")
    except Exception as e:
        logger.error(f"❌ 임베딩 워커 모델 초기화 실패: {e}")
        return
    
    # 요청 처리 루프
    while True:
        try:
            # 요청 대기
            request = request_queue.get()
            
            if request is None:  # 종료 신호
                break
            
            task_type = request['type']
            task_id = request['task_id']
            
            try:
                if task_type == 'generate_embeddings':
                    # 임베딩 생성
                    texts = request['texts']
                    batch_size = request.get('batch_size', 32)
                    
                    embeddings = embedding_model.encode(
                        texts,
                        batch_size=batch_size,
                        show_progress_bar=False,
                        convert_to_numpy=True
                    )
                    
                    response_queue.put({
                        'task_id': task_id,
                        'status': 'success',
                        'embeddings': embeddings.tolist(),
                        'dimension': embedding_model.get_sentence_embedding_dimension(),
                        'model_name': "BAAI/bge-m3",
                        'device': str(device),
                        'batch_size': batch_size
                    })
                    
            except Exception as e:
                logger.error(f"❌ 임베딩 생성 실패: {e}")
                response_queue.put({
                    'task_id': task_id,
                    'status': 'error',
                    'error': str(e)
                })
                
        except Exception as e:
            logger.error(f"❌ 임베딩 워커 프로세스 오류: {e}")
            break
    
    logger.info("🛑 임베딩 워커 프로세스 종료")

def initialize_embedding_multiprocessing():
    """임베딩 멀티프로세싱 초기화"""
    global embedding_process, embedding_request_queue, embedding_response_queue
    
    if embedding_process is None:
        # 환경 변수 설정
        os.environ['TOKENIZERS_PARALLELISM'] = 'false'
        
        embedding_request_queue = Queue()
        embedding_response_queue = Queue()
        
        embedding_process = Process(
            target=embedding_worker_process,
            args=(embedding_request_queue, embedding_response_queue)
        )
        embedding_process.start()
        
        logger.info("✅ 임베딩 멀티프로세싱 환경 초기화 완료")
    else:
        logger.info("임베딩 멀티프로세싱이 이미 실행 중입니다.")

def initialize_embedding_model(model_name: str = "BAAI/bge-m3", device: str = None):
    """임베딩 모델 초기화 (멀티프로세싱 방식)"""
    global embedding_model, embedding_device, embedding_initialization_attempted
    
    if embedding_initialization_attempted:
        logger.info("✅ 임베딩 모델 초기화가 이미 시도되었습니다.")
        return
    
    embedding_initialization_attempted = True
    
    # 멀티프로세싱 초기화
    initialize_embedding_multiprocessing()
    
    # 메인 프로세스에서는 CUDA를 초기화하지 않음
    # 실제 GPU 설정은 워커 프로세스에서 처리됨
    embedding_device = "cuda:0"  # 워커 프로세스 내부에서의 논리적 디바이스
    logger.info(f"🔄 임베딩 모델 초기화 완료 (멀티프로세싱 방식): {model_name}")

@router.post("/embed", response_model=EmbeddingResponse)
async def generate_embeddings(request: EmbeddingRequest):
    """텍스트를 임베딩으로 변환 (멀티프로세싱 방식)"""
    global embedding_process, embedding_request_queue, embedding_response_queue
    
    try:
        # 모델이 초기화되지 않았으면 초기화
        if embedding_process is None:
            initialize_embedding_model(request.model_name)
        
        # 요청 데이터 준비
        task_id = str(uuid.uuid4())
        request_data = {
            'type': 'generate_embeddings',
            'task_id': task_id,
            'texts': request.texts,
            'batch_size': request.batch_size or 32
        }
        
        # 워커 프로세스에 요청 전송
        embedding_request_queue.put(request_data)
        
        # 응답 대기
        response = embedding_response_queue.get()
        
        if response['status'] == 'success':
            logger.info(f"✅ 임베딩 생성 완료: {len(response['embeddings'])}개")
            return EmbeddingResponse(**response)
        else:
            logger.error(f"❌ 임베딩 생성 실패: {response.get('error', 'Unknown error')}")
            raise HTTPException(status_code=500, detail=f"임베딩 생성 실패: {response.get('error', 'Unknown error')}")
        
    except Exception as e:
        logger.error(f"❌ 임베딩 생성 중 오류: {e}")
        raise HTTPException(status_code=500, detail=f"임베딩 생성 실패: {str(e)}")

@router.post("/embed/batch")
async def batch_embedding(request: EmbeddingRequest):
    """배치 임베딩 생성 (대용량 처리용) - 멀티프로세싱 방식"""
    global embedding_process, embedding_request_queue, embedding_response_queue
    
    try:
        # 모델이 초기화되지 않았으면 초기화
        if embedding_process is None:
            initialize_embedding_model(request.model_name)
        
        # 요청 데이터 준비
        task_id = str(uuid.uuid4())
        request_data = {
            'type': 'generate_embeddings',
            'task_id': task_id,
            'texts': request.texts,
            'batch_size': request.batch_size or 32
        }
        
        # 워커 프로세스에 요청 전송
        embedding_request_queue.put(request_data)
        
        # 응답 대기
        response = embedding_response_queue.get()
        
        if response['status'] == 'success':
            logger.info(f"✅ 배치 임베딩 생성 완료: {len(response['embeddings'])}개")
            return EmbeddingResponse(**response)
        else:
            logger.error(f"❌ 배치 임베딩 생성 실패: {response.get('error', 'Unknown error')}")
            raise HTTPException(status_code=500, detail=f"배치 임베딩 생성 실패: {response.get('error', 'Unknown error')}")
        
    except Exception as e:
        logger.error(f"❌ 배치 임베딩 생성 중 오류: {e}")
        raise HTTPException(status_code=500, detail=f"배치 임베딩 생성 실패: {str(e)}")

@router.get("/embed/info")
async def get_embedding_info():
    """임베딩 모델 정보 조회"""
    global embedding_device
    
    if embedding_process is None:
        raise HTTPException(status_code=404, detail="임베딩 모델이 초기화되지 않았습니다.")
    
    return {
        "model_name": "BAAI/bge-m3",
        "device": embedding_device or "cuda:0",
        "dimension": 1024,  # BGE-M3 임베딩 차원
        "max_seq_length": 512,
        "is_initialized": True,
        "process_mode": "multiprocessing"
    }

@router.post("/embed/health")
async def embedding_health_check():
    """임베딩 모델 상태 확인"""
    global embedding_process
    
    if embedding_process is None:
        return {"status": "not_initialized", "message": "임베딩 모델이 초기화되지 않았습니다."}
    
    try:
        # 간단한 테스트 요청
        test_request = {
            'type': 'generate_embeddings',
            'task_id': 'health_check',
            'texts': ['테스트'],
            'batch_size': 1
        }
        
        embedding_request_queue.put(test_request)
        response = embedding_response_queue.get(timeout=10)
        
        if response['status'] == 'success':
            return {"status": "healthy", "message": "임베딩 모델이 정상 작동 중입니다."}
        else:
            return {"status": "error", "message": f"임베딩 모델 오류: {response.get('error', 'Unknown error')}"}
            
    except Exception as e:
        return {"status": "error", "message": f"임베딩 모델 상태 확인 실패: {str(e)}"}

# startup 이벤트 제거 - main.py에서 명시적으로 초기화
# @router.on_event("startup")
# async def startup_event():
#     """서버 시작 시 임베딩 모델 초기화"""
#     logger.info("🔄 임베딩 모델 멀티프로세싱 초기화 시작...")
#     initialize_embedding_model()
#     logger.info("✅ 임베딩 모델 멀티프로세싱 초기화 완료")

@router.on_event("shutdown")
async def shutdown_event():
    """서버 종료 시 정리"""
    global embedding_process, embedding_request_queue
    
    if embedding_process is not None:
        logger.info("🛑 임베딩 워커 프로세스 종료 중...")
        embedding_request_queue.put(None)  # 종료 신호
        embedding_process.join(timeout=5)
        embedding_process.terminate()
        embedding_process = None
        logger.info("✅ 임베딩 워커 프로세스 종료 완료")
    
    await shutdown_executor() 
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import torch
import logging
from sentence_transformers import SentenceTransformer
import numpy as np
import os

logger = logging.getLogger(__name__)

router = APIRouter()

# 임베딩 모델 전역 변수
embedding_model = None
embedding_device = None

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

def initialize_embedding_model(model_name: str = "BAAI/bge-m3", device: str = None):
    """임베딩 모델 초기화"""
    global embedding_model, embedding_device
    
    if embedding_model is not None:
        logger.info("✅ 임베딩 모델이 이미 초기화되어 있습니다.")
        return
    
    # 디바이스 설정 - RAG는 GPU 1 직접 사용
    if device is None:
        if torch.cuda.is_available():
            # RAG 전용 GPU 1 직접 사용
            device = "cuda:1"  # 직접 GPU 1 지정
            logger.info("🔧 RAG 임베딩 모델 GPU 1 직접 사용")
        else:
            device = "cpu"
    
    embedding_device = device
    logger.info(f"🔄 임베딩 모델 초기화 중... (모델: {model_name}, 디바이스: {device})")
    
    try:
        embedding_model = SentenceTransformer(model_name, device=device)
        logger.info(f"✅ 임베딩 모델 초기화 완료: {model_name} (디바이스: {device})")
    except Exception as e:
        logger.error(f"❌ 임베딩 모델 초기화 실패: {str(e)}")
        raise Exception(f"임베딩 모델 초기화 실패: {str(e)}")

@router.post("/embed", response_model=EmbeddingResponse)
async def generate_embeddings(request: EmbeddingRequest):
    """텍스트를 임베딩으로 변환"""
    global embedding_model, embedding_device
    
    try:
        # 모델이 초기화되지 않았으면 초기화
        if embedding_model is None:
            # 요청된 디바이스가 없으면 GPU 1 직접 사용
            device = request.device if request.device else "cuda:1"
            initialize_embedding_model(request.model_name, device)
        
        # 디바이스 변경이 필요한 경우
        if request.device and request.device != embedding_device:
            logger.info(f"🔄 임베딩 모델 디바이스 변경: {embedding_device} → {request.device}")
            initialize_embedding_model(request.model_name, request.device)
        
        logger.info(f"🔄 {len(request.texts)}개 텍스트 임베딩 생성 중... (디바이스: {embedding_device})")
        
        # 임베딩 생성
        embeddings = embedding_model.encode(
            request.texts,
            batch_size=request.batch_size,
            show_progress_bar=True,
            convert_to_numpy=True
        )
        
        # numpy 배열을 리스트로 변환
        embeddings_list = embeddings.tolist()
        
        logger.info(f"✅ 임베딩 생성 완료: {len(embeddings_list)}개")
        
        return EmbeddingResponse(
            embeddings=embeddings_list,
            dimension=embedding_model.get_sentence_embedding_dimension(),
            model_name=request.model_name,
            device=embedding_device,
            batch_size=request.batch_size
        )
        
    except Exception as e:
        logger.error(f"❌ 임베딩 생성 중 오류: {e}")
        raise HTTPException(status_code=500, detail=f"임베딩 생성 실패: {str(e)}")

@router.get("/embed/info")
async def get_embedding_info():
    """임베딩 모델 정보 조회"""
    global embedding_model, embedding_device
    
    if embedding_model is None:
        raise HTTPException(status_code=404, detail="임베딩 모델이 초기화되지 않았습니다.")
    
    return {
        "model_name": embedding_model.model_name,
        "device": embedding_device,
        "dimension": embedding_model.get_sentence_embedding_dimension(),
        "max_seq_length": embedding_model.max_seq_length,
        "is_initialized": True
    }

@router.post("/embed/health")
async def embedding_health_check():
    """임베딩 모델 상태 확인"""
    global embedding_model
    
    if embedding_model is None:
        return {"status": "not_initialized", "message": "임베딩 모델이 초기화되지 않았습니다."}
    
    try:
        # 간단한 테스트 임베딩 생성
        test_text = ["테스트"]
        test_embedding = embedding_model.encode(test_text)
        
        return {
            "status": "healthy",
            "message": "임베딩 모델이 정상적으로 작동 중입니다.",
            "test_embedding_shape": test_embedding.shape
        }
    except Exception as e:
        return {
            "status": "error",
            "message": f"임베딩 모델 오류: {str(e)}"
        }

@router.post("/embed/batch")
async def batch_embedding(request: EmbeddingRequest):
    """배치 임베딩 생성 (대용량 처리용)"""
    global embedding_model
    
    if embedding_model is None:
        # 요청된 디바이스가 없으면 GPU 1 사용
        device = request.device if request.device else "cuda:1"
        initialize_embedding_model(request.model_name, device)
    
    try:
        logger.info(f"🔄 배치 임베딩 생성 시작: {len(request.texts)}개 텍스트 (디바이스: {embedding_device})")
        
        # 배치 크기 조정
        batch_size = min(request.batch_size, 64)  # 최대 64개로 제한
        
        embeddings = []
        total_batches = (len(request.texts) + batch_size - 1) // batch_size
        
        for i in range(0, len(request.texts), batch_size):
            batch_texts = request.texts[i:i + batch_size]
            batch_embeddings = embedding_model.encode(
                batch_texts,
                batch_size=batch_size,
                show_progress_bar=False,
                convert_to_numpy=True
            )
            embeddings.extend(batch_embeddings.tolist())
            
            logger.info(f"📊 배치 진행률: {min(i + batch_size, len(request.texts))}/{len(request.texts)}")
        
        logger.info(f"✅ 배치 임베딩 생성 완료: {len(embeddings)}개")
        
        return EmbeddingResponse(
            embeddings=embeddings,
            dimension=embedding_model.get_sentence_embedding_dimension(),
            model_name=request.model_name,
            device=embedding_device,
            batch_size=request.batch_size
        )
        
    except Exception as e:
        logger.error(f"❌ 배치 임베딩 생성 중 오류: {e}")
        raise HTTPException(status_code=500, detail=f"배치 임베딩 생성 실패: {str(e)}") 
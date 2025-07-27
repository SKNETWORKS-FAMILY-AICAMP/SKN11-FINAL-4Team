"""
VLLM 서버의 GPU 기반 벡터 검색 API
CUDA를 활용한 고성능 벡터 검색 기능 제공
"""

import logging
import asyncio
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
import numpy as np
import torch
from pydantic import BaseModel

from app.core import get_embedding_model, get_device

logger = logging.getLogger(__name__)


@dataclass
class VectorChunk:
    """벡터 청크 데이터"""
    id: str
    text: str
    embedding: List[float]
    metadata: Dict[str, Any]


class VectorSearchRequest(BaseModel):
    """벡터 검색 요청 모델"""
    query: str
    top_k: int = 5
    similarity_threshold: float = 0.5


class VectorStoreRequest(BaseModel):
    """벡터 저장 요청 모델"""
    chunks: List[Dict[str, Any]]  # [{"id": str, "text": str, "metadata": dict}]


class VectorSearchResponse(BaseModel):
    """벡터 검색 응답 모델"""
    results: List[Dict[str, Any]]
    query_embedding: List[float]
    total_found: int


class VectorStoreResponse(BaseModel):
    """벡터 저장 응답 모델"""
    stored_count: int
    total_chunks: int
    success: bool


class GPUVectorStore:
    """GPU 기반 벡터 스토어"""
    
    def __init__(self):
        self.chunks: List[VectorChunk] = []
        self.embeddings_tensor: Optional[torch.Tensor] = None
        self.device = get_device()
        self.embedding_model = None
        self._initialize_embedding_model()
    
    def _initialize_embedding_model(self):
        """임베딩 모델 초기화"""
        try:
            self.embedding_model = get_embedding_model()
            logger.info(f"✅ GPU 임베딩 모델 초기화 완료: {self.device}")
        except Exception as e:
            logger.error(f"❌ 임베딩 모델 초기화 실패: {e}")
    
    async def _generate_embeddings(self, texts: List[str]) -> List[List[float]]:
        """텍스트에서 임베딩 생성"""
        try:
            if not self.embedding_model:
                raise RuntimeError("임베딩 모델이 초기화되지 않았습니다.")
            
            # GPU에서 임베딩 생성
            with torch.no_grad():
                embeddings = self.embedding_model.encode(texts, convert_to_tensor=True)
                embeddings = embeddings.to(self.device)
                
                # 정규화 (코사인 유사도용)
                embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)
                
                # CPU로 변환하여 반환
                embeddings_cpu = embeddings.cpu().numpy().tolist()
            
            logger.info(f"✅ {len(texts)}개 텍스트의 임베딩 생성 완료")
            return embeddings_cpu
            
        except Exception as e:
            logger.error(f"❌ 임베딩 생성 실패: {e}")
            return []
    
    async def store_chunks(self, chunks_data: List[Dict[str, Any]]) -> bool:
        """청크들을 GPU 벡터 스토어에 저장"""
        try:
            logger.info(f"💾 {len(chunks_data)}개 청크 저장 시작")
            
            # 텍스트 추출
            texts = [chunk["text"] for chunk in chunks_data]
            
            # GPU에서 임베딩 생성
            embeddings = await self._generate_embeddings(texts)
            
            if not embeddings:
                return False
            
            # VectorChunk 객체 생성
            new_chunks = []
            for i, chunk_data in enumerate(chunks_data):
                chunk = VectorChunk(
                    id=chunk_data["id"],
                    text=chunk_data["text"],
                    embedding=embeddings[i],
                    metadata=chunk_data.get("metadata", {})
                )
                new_chunks.append(chunk)
            
            # 기존 청크에 추가
            self.chunks.extend(new_chunks)
            
            # 임베딩 텐서 업데이트
            await self._update_embeddings_tensor()
            
            logger.info(f"✅ {len(new_chunks)}개 청크 저장 완료 (총 {len(self.chunks)}개)")
            return True
            
        except Exception as e:
            logger.error(f"❌ 청크 저장 실패: {e}")
            return False
    
    async def _update_embeddings_tensor(self):
        """임베딩 텐서 업데이트"""
        try:
            if not self.chunks:
                self.embeddings_tensor = None
                return
            
            # 모든 임베딩을 텐서로 변환
            embeddings_list = [chunk.embedding for chunk in self.chunks]
            embeddings_array = np.array(embeddings_list, dtype=np.float32)
            
            # GPU 텐서로 변환
            self.embeddings_tensor = torch.tensor(embeddings_array, device=self.device)
            
            logger.info(f"✅ 임베딩 텐서 업데이트 완료: {self.embeddings_tensor.shape}")
            
        except Exception as e:
            logger.error(f"❌ 임베딩 텐서 업데이트 실패: {e}")
    
    async def search_similar(self, query: str, top_k: int = 5, 
                           similarity_threshold: float = 0.5) -> List[Dict[str, Any]]:
        """GPU에서 유사한 벡터 검색"""
        try:
            if not self.chunks or self.embeddings_tensor is None:
                logger.warning("⚠️ 저장된 청크가 없습니다.")
                return []
            
            # 쿼리 임베딩 생성
            query_embeddings = await self._generate_embeddings([query])
            if not query_embeddings:
                return []
            
            query_embedding = query_embeddings[0]
            query_tensor = torch.tensor([query_embedding], device=self.device)
            
            # GPU에서 코사인 유사도 계산
            with torch.no_grad():
                similarities = torch.nn.functional.cosine_similarity(
                    query_tensor.unsqueeze(1), 
                    self.embeddings_tensor.unsqueeze(0), 
                    dim=2
                ).squeeze()
                
                # 유사도 임계값 필터링
                valid_indices = similarities >= similarity_threshold
                
                if not valid_indices.any():
                    logger.info(f"⚠️ 유사도 임계값({similarity_threshold})을 만족하는 결과가 없습니다.")
                    return []
                
                # 상위 k개 선택
                top_similarities, top_indices = torch.topk(
                    similarities[valid_indices], 
                    min(top_k, valid_indices.sum().item())
                )
                
                # 원본 인덱스로 변환
                original_indices = torch.where(valid_indices)[0][top_indices]
            
            # 결과 구성
            results = []
            for i, (idx, similarity) in enumerate(zip(original_indices, top_similarities)):
                chunk = self.chunks[idx.item()]
                results.append({
                    "rank": i + 1,
                    "text": chunk.text,
                    "similarity": similarity.item(),
                    "metadata": chunk.metadata,
                    "chunk_id": chunk.id
                })
            
            logger.info(f"🔍 GPU 벡터 검색 완료: {len(results)}개 결과 (임계값: {similarity_threshold})")
            return results
            
        except Exception as e:
            logger.error(f"❌ GPU 벡터 검색 실패: {e}")
            return []
    
    def get_stats(self) -> Dict[str, Any]:
        """벡터 스토어 통계"""
        return {
            "total_chunks": len(self.chunks),
            "embedding_dimension": len(self.chunks[0].embedding) if self.chunks else 0,
            "device": str(self.device),
            "tensor_shape": list(self.embeddings_tensor.shape) if self.embeddings_tensor is not None else None
        }
    
    def clear_store(self) -> bool:
        """벡터 스토어 정리"""
        try:
            self.chunks.clear()
            self.embeddings_tensor = None
            logger.info("✅ 벡터 스토어 정리 완료")
            return True
        except Exception as e:
            logger.error(f"❌ 벡터 스토어 정리 실패: {e}")
            return False


# 전역 벡터 스토어 인스턴스
_vector_store = None

def get_vector_store() -> GPUVectorStore:
    """전역 벡터 스토어 인스턴스 반환"""
    global _vector_store
    
    if _vector_store is None:
        _vector_store = GPUVectorStore()
    
    return _vector_store


# FastAPI 라우터
from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/vector", tags=["vector-search"])


@router.post("/store", response_model=VectorStoreResponse)
async def store_vectors(request: VectorStoreRequest):
    """벡터 청크들을 GPU 스토어에 저장"""
    try:
        vector_store = get_vector_store()
        success = await vector_store.store_chunks(request.chunks)
        
        return VectorStoreResponse(
            stored_count=len(request.chunks) if success else 0,
            total_chunks=len(request.chunks),
            success=success
        )
        
    except Exception as e:
        logger.error(f"❌ 벡터 저장 API 실패: {e}")
        raise HTTPException(status_code=500, detail=f"벡터 저장 실패: {str(e)}")


@router.post("/search", response_model=VectorSearchResponse)
async def search_vectors(request: VectorSearchRequest):
    """GPU에서 벡터 검색"""
    try:
        vector_store = get_vector_store()
        results = await vector_store.search_similar(
            query=request.query,
            top_k=request.top_k,
            similarity_threshold=request.similarity_threshold
        )
        
        # 쿼리 임베딩 생성 (응답용)
        query_embeddings = await vector_store._generate_embeddings([request.query])
        query_embedding = query_embeddings[0] if query_embeddings else []
        
        return VectorSearchResponse(
            results=results,
            query_embedding=query_embedding,
            total_found=len(results)
        )
        
    except Exception as e:
        logger.error(f"❌ 벡터 검색 API 실패: {e}")
        raise HTTPException(status_code=500, detail=f"벡터 검색 실패: {str(e)}")


@router.get("/stats")
async def get_vector_stats():
    """벡터 스토어 통계 조회"""
    try:
        vector_store = get_vector_store()
        return vector_store.get_stats()
        
    except Exception as e:
        logger.error(f"❌ 벡터 통계 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"통계 조회 실패: {str(e)}")


@router.delete("/clear")
async def clear_vector_store():
    """벡터 스토어 정리"""
    try:
        vector_store = get_vector_store()
        success = vector_store.clear_store()
        
        return {"success": success, "message": "벡터 스토어가 정리되었습니다." if success else "정리 실패"}
        
    except Exception as e:
        logger.error(f"❌ 벡터 스토어 정리 실패: {e}")
        raise HTTPException(status_code=500, detail=f"정리 실패: {str(e)}")


@router.get("/health")
async def vector_health_check():
    """벡터 검색 서비스 상태 확인"""
    try:
        vector_store = get_vector_store()
        stats = vector_store.get_stats()
        
        return {
            "status": "healthy",
            "device": stats["device"],
            "total_chunks": stats["total_chunks"],
            "embedding_model_loaded": vector_store.embedding_model is not None
        }
        
    except Exception as e:
        logger.error(f"❌ 벡터 서비스 상태 확인 실패: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        } 
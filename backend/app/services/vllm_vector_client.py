"""
VLLM 서버의 GPU 벡터 검색 API 클라이언트
CUDA 기반 고성능 벡터 검색 기능 사용
"""

import logging
import asyncio
from typing import List, Dict, Optional, Any
import httpx
from pydantic import BaseModel

from app.core.config import settings

logger = logging.getLogger(__name__)


class VectorChunkData(BaseModel):
    """벡터 청크 데이터"""
    id: str
    text: str
    metadata: Dict[str, Any]


class VectorSearchRequest(BaseModel):
    """벡터 검색 요청"""
    query: str
    top_k: int = 5
    similarity_threshold: float = 0.5


class VectorSearchResult(BaseModel):
    """벡터 검색 결과"""
    rank: int
    text: str
    similarity: float
    metadata: Dict[str, Any]
    chunk_id: str


class VectorSearchResponse(BaseModel):
    """벡터 검색 응답"""
    results: List[VectorSearchResult]
    query_embedding: List[float]
    total_found: int


class VectorStoreResponse(BaseModel):
    """벡터 저장 응답"""
    stored_count: int
    total_chunks: int
    success: bool


class VLLMVectorClient:
    """VLLM 서버의 GPU 벡터 검색 클라이언트"""
    
    def __init__(self, base_url: str = None):
        self.base_url = base_url or getattr(settings, 'VLLM_BASE_URL', 'http://localhost:8001')
        self.client = None
    
    async def __aenter__(self):
        """비동기 컨텍스트 매니저 진입"""
        self.client = httpx.AsyncClient(timeout=30.0)
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """비동기 컨텍스트 매니저 종료"""
        if self.client:
            await self.client.aclose()
    
    async def store_chunks(self, chunks: List[VectorChunkData]) -> bool:
        """청크들을 VLLM 서버의 GPU 벡터 스토어에 저장"""
        try:
            if not self.client:
                raise RuntimeError("클라이언트가 초기화되지 않았습니다.")
            
            # 요청 데이터 준비
            chunks_data = [
                {
                    "id": chunk.id,
                    "text": chunk.text,
                    "metadata": chunk.metadata
                }
                for chunk in chunks
            ]
            
            # VLLM 서버에 저장 요청
            response = await self.client.post(
                f"{self.base_url}/vector/store",
                json={"chunks": chunks_data}
            )
            response.raise_for_status()
            
            result = VectorStoreResponse(**response.json())
            
            if result.success:
                logger.info(f"✅ {result.stored_count}개 청크를 VLLM GPU 스토어에 저장 완료")
            else:
                logger.error(f"❌ 청크 저장 실패: {result.stored_count}/{result.total_chunks}")
            
            return result.success
            
        except Exception as e:
            logger.error(f"❌ VLLM 벡터 저장 실패: {e}")
            return False
    
    async def search_similar(self, query: str, top_k: int = 5, 
                           similarity_threshold: float = 0.5) -> List[VectorSearchResult]:
        """VLLM 서버에서 GPU 기반 벡터 검색"""
        try:
            if not self.client:
                raise RuntimeError("클라이언트가 초기화되지 않았습니다.")
            
            # 검색 요청
            request_data = VectorSearchRequest(
                query=query,
                top_k=top_k,
                similarity_threshold=similarity_threshold
            )
            
            response = await self.client.post(
                f"{self.base_url}/vector/search",
                json=request_data.dict()
            )
            response.raise_for_status()
            
            result = VectorSearchResponse(**response.json())
            
            logger.info(f"🔍 VLLM GPU 벡터 검색 완료: {len(result.results)}개 결과")
            return result.results
            
        except Exception as e:
            logger.error(f"❌ VLLM 벡터 검색 실패: {e}")
            return []
    
    async def get_stats(self) -> Dict[str, Any]:
        """벡터 스토어 통계 조회"""
        try:
            if not self.client:
                raise RuntimeError("클라이언트가 초기화되지 않았습니다.")
            
            response = await self.client.get(f"{self.base_url}/vector/stats")
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"❌ 벡터 통계 조회 실패: {e}")
            return {}
    
    async def clear_store(self) -> bool:
        """벡터 스토어 정리"""
        try:
            if not self.client:
                raise RuntimeError("클라이언트가 초기화되지 않았습니다.")
            
            response = await self.client.delete(f"{self.base_url}/vector/clear")
            response.raise_for_status()
            
            result = response.json()
            success = result.get("success", False)
            
            if success:
                logger.info("✅ VLLM 벡터 스토어 정리 완료")
            else:
                logger.error("❌ VLLM 벡터 스토어 정리 실패")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ 벡터 스토어 정리 실패: {e}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """벡터 검색 서비스 상태 확인"""
        try:
            if not self.client:
                raise RuntimeError("클라이언트가 초기화되지 않았습니다.")
            
            response = await self.client.get(f"{self.base_url}/vector/health")
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"❌ 벡터 서비스 상태 확인 실패: {e}")
            return {"status": "unhealthy", "error": str(e)}


# 편의 함수들
async def store_qa_chunks_to_vllm(qa_data: List[Dict], source_file: str = "document.pdf") -> bool:
    """QA 데이터를 VLLM GPU 벡터 스토어에 저장"""
    try:
        # VectorChunkData 객체 생성
        chunks = []
        for qa in qa_data:
            # 질문 청크
            question_chunk = VectorChunkData(
                id=f"{source_file}_q_{qa['chunk_id']}",
                text=qa["question"],
                metadata={
                    "type": "question",
                    "source": source_file,
                    "chunk_id": qa["chunk_id"],
                    "page": qa.get("page", 1)
                }
            )
            
            # 답변 청크
            answer_chunk = VectorChunkData(
                id=f"{source_file}_a_{qa['chunk_id']}",
                text=qa["answer"],
                metadata={
                    "type": "answer",
                    "source": source_file,
                    "chunk_id": qa["chunk_id"],
                    "page": qa.get("page", 1)
                }
            )
            
            chunks.extend([question_chunk, answer_chunk])
        
        # VLLM 클라이언트로 저장
        vllm_url = getattr(settings, 'VLLM_BASE_URL', 'http://localhost:8001')
        client = VLLMVectorClient(base_url=vllm_url)
        
        async with client:
            success = await client.store_chunks(chunks)
        
        return success
        
    except Exception as e:
        logger.error(f"❌ QA 데이터 VLLM 저장 실패: {e}")
        return False


async def search_similar_from_vllm(query: str, top_k: int = 5, 
                                 similarity_threshold: float = 0.5) -> List[VectorSearchResult]:
    """VLLM GPU 벡터 스토어에서 유사한 문서 검색"""
    try:
        vllm_url = getattr(settings, 'VLLM_BASE_URL', 'http://localhost:8001')
        client = VLLMVectorClient(base_url=vllm_url)
        
        async with client:
            results = await client.search_similar(
                query=query,
                top_k=top_k,
                similarity_threshold=similarity_threshold
            )
        
        return results
        
    except Exception as e:
        logger.error(f"❌ VLLM 벡터 검색 실패: {e}")
        return []


async def get_vllm_vector_stats() -> Dict[str, Any]:
    """VLLM 벡터 스토어 통계 조회"""
    try:
        vllm_url = getattr(settings, 'VLLM_BASE_URL', 'http://localhost:8001')
        client = VLLMVectorClient(base_url=vllm_url)
        
        async with client:
            stats = await client.get_stats()
        
        return stats
        
    except Exception as e:
        logger.error(f"❌ VLLM 벡터 통계 조회 실패: {e}")
        return {}


async def clear_vllm_vector_store() -> bool:
    """VLLM 벡터 스토어 정리"""
    try:
        vllm_url = getattr(settings, 'VLLM_BASE_URL', 'http://localhost:8001')
        client = VLLMVectorClient(base_url=vllm_url)
        
        async with client:
            success = await client.clear_store()
        
        return success
        
    except Exception as e:
        logger.error(f"❌ VLLM 벡터 스토어 정리 실패: {e}")
        return False


async def check_vllm_vector_health() -> Dict[str, Any]:
    """VLLM 벡터 검색 서비스 상태 확인"""
    try:
        vllm_url = getattr(settings, 'VLLM_BASE_URL', 'http://localhost:8001')
        client = VLLMVectorClient(base_url=vllm_url)
        
        async with client:
            health = await client.health_check()
        
        return health
        
    except Exception as e:
        logger.error(f"❌ VLLM 벡터 서비스 상태 확인 실패: {e}")
        return {"status": "unhealthy", "error": str(e)} 
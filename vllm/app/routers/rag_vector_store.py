import os
import json
import logging
from typing import List, Dict, Optional, Any
from pathlib import Path
from dataclasses import dataclass

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from sentence_transformers import SentenceTransformer
from pymilvus import MilvusClient, DataType, Collection
import numpy as np

# 로깅 설정
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rag", tags=["RAG Vector Store"])

# ============================================================================
# 설정 클래스들
# ============================================================================

@dataclass
class EmbeddingConfig:
    """임베딩 설정 클래스"""
    model_name: str = "BAAI/bge-m3"
    dimension: int = 1024  # BGE-M3 모델의 차원
    device: str = "cuda"
    batch_size: int = 32

@dataclass
class MilvusConfig:
    """Milvus 설정 클래스"""
    uri: str = "./milvus_rag.db"  # Milvus Lite용 로컬 DB 파일
    collection_name: str = "rag_chunks"
    index_type: str = "AUTOINDEX"
    metric_type: str = "COSINE"

# ============================================================================
# Pydantic 모델들
# ============================================================================

class TextChunkRequest(BaseModel):
    """텍스트 청크 요청 모델"""
    id: str
    text: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

class QAChunkRequest(BaseModel):
    """QA 청크 요청 모델"""
    question: str
    answer: str
    source: str = "document.pdf"
    page: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)

class StoreQARequest(BaseModel):
    """QA 데이터 저장 요청 모델"""
    qa_data: List[QAChunkRequest]
    source_file: str = "document.pdf"
    collection_name: Optional[str] = None

class SearchRequest(BaseModel):
    """검색 요청 모델"""
    query: str
    top_k: int = 5
    collection_name: Optional[str] = None

class SearchResponse(BaseModel):
    """검색 응답 모델"""
    results: List[Dict[str, Any]]
    total_found: int
    query: str

class CollectionInfoResponse(BaseModel):
    """컬렉션 정보 응답 모델"""
    collection_name: str
    total_chunks: int
    embedding_dimension: int
    metric_type: str

# ============================================================================
# 임베딩 모델 클래스
# ============================================================================

class HuggingFaceEmbedding:
    """HuggingFace 임베딩 모델"""
    
    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self.model = SentenceTransformer("BAAI/bge-m3", device=config.device)
        
    def encode(self, texts: List[str]) -> List[List[float]]:
        """텍스트 리스트를 임베딩으로 변환"""
        try:
            embeddings = self.model.encode(
                texts, 
                batch_size=self.config.batch_size,
                show_progress_bar=True,
                convert_to_numpy=True
            )
            return embeddings.tolist()
        except Exception as e:
            raise RuntimeError(f"임베딩 생성 중 오류 발생: {str(e)}")
    
    def get_dimension(self) -> int:
        """임베딩 차원 반환"""
        return self.model.get_sentence_embedding_dimension()

# ============================================================================
# Milvus 벡터 스토어 클래스
# ============================================================================

class MilvusVectorStore:
    """Milvus 벡터 스토어"""
    
    def __init__(self, config: MilvusConfig, embedding_dim: int):
        self.config = config
        self.embedding_dim = embedding_dim
        self.client = None
        self._connect()
        self._create_collection_if_not_exists()
    
    def _connect(self):
        """Milvus에 연결"""
        try:
            self.client = MilvusClient(uri=self.config.uri)
            logger.info(f"✅ Milvus 연결 성공: {self.config.uri}")
        except Exception as e:
            raise ConnectionError(f"Milvus 연결 실패: {str(e)}")
    
    def _create_collection_if_not_exists(self):
        """컬렉션이 없으면 생성"""
        try:
            if self.client.has_collection(collection_name=self.config.collection_name):
                logger.info(f"✅ 기존 컬렉션 사용: {self.config.collection_name}")
                return
            
            # 컬렉션 생성
            self.client.create_collection(
                collection_name=self.config.collection_name,
                dimension=self.embedding_dim,
                metric_type=self.config.metric_type,
                index_type=self.config.index_type
            )
            logger.info(f"✅ 새 컬렉션 생성: {self.config.collection_name}")
            
        except Exception as e:
            raise RuntimeError(f"컬렉션 생성 실패: {str(e)}")
    
    def insert_chunks(self, chunks: List[Dict]) -> bool:
        """텍스트 청크를 Milvus에 저장"""
        try:
            # 삽입
            result = self.client.insert(
                collection_name=self.config.collection_name,
                data=chunks
            )
            
            logger.info(f"✅ {len(chunks)}개 청크를 Milvus에 저장 완료")
            return True
            
        except Exception as e:
            logger.error(f"❌ Milvus 저장 실패: {str(e)}")
            return False
    
    def search(self, query_embedding: List[float], top_k: int = 5) -> List[Dict]:
        """유사한 텍스트 검색"""
        try:
            results = self.client.search(
                collection_name=self.config.collection_name,
                data=[query_embedding],
                limit=top_k,
                output_fields=["text", "source", "page", "question", "answer"]
            )
            
            return [
                {
                    "text": hit["entity"]["text"],
                    "source": hit["entity"]["source"],
                    "page": hit["entity"]["page"],
                    "question": hit["entity"].get("question", ""),
                    "answer": hit["entity"].get("answer", ""),
                    "score": hit["distance"]
                }
                for hit in results[0]
            ]
            
        except Exception as e:
            logger.error(f"❌ 검색 실패: {str(e)}")
            return []
    
    def delete_collection(self) -> bool:
        """컬렉션 삭제"""
        try:
            self.client.drop_collection(collection_name=self.config.collection_name)
            logger.info(f"✅ 컬렉션 삭제 완료: {self.config.collection_name}")
            return True
        except Exception as e:
            logger.error(f"❌ 컬렉션 삭제 실패: {str(e)}")
            return False
    
    def get_collection_info(self) -> Dict[str, Any]:
        """컬렉션 정보 조회"""
        try:
            if not self.client.has_collection(collection_name=self.config.collection_name):
                return {
                    "collection_name": self.config.collection_name,
                    "total_chunks": 0,
                    "embedding_dimension": self.embedding_dim,
                    "metric_type": self.config.metric_type
                }
            
            # 컬렉션 통계 조회
            stats = self.client.get_collection_stats(collection_name=self.config.collection_name)
            total_chunks = stats.get("row_count", 0)
            
            return {
                "collection_name": self.config.collection_name,
                "total_chunks": total_chunks,
                "embedding_dimension": self.embedding_dim,
                "metric_type": self.config.metric_type
            }
            
        except Exception as e:
            logger.error(f"❌ 컬렉션 정보 조회 실패: {str(e)}")
            return {
                "collection_name": self.config.collection_name,
                "total_chunks": 0,
                "embedding_dimension": self.embedding_dim,
                "metric_type": self.config.metric_type,
                "error": str(e)
            }

# ============================================================================
# 전역 인스턴스들
# ============================================================================

# 임베딩 모델 초기화
embedding_config = EmbeddingConfig(
    device="cuda" if os.getenv("CUDA_AVAILABLE", "false").lower() == "true" else "cpu"
)
embedding_model = HuggingFaceEmbedding(embedding_config)

# Milvus 벡터 스토어 초기화
milvus_config = MilvusConfig()
vector_store = MilvusVectorStore(milvus_config, embedding_model.get_dimension())

# ============================================================================
# API 엔드포인트들
# ============================================================================

@router.post("/store_qa_chunks", response_model=Dict[str, Any])
async def store_qa_chunks(request: StoreQARequest):
    """QA 데이터를 임베딩하여 벡터 스토어에 저장"""
    try:
        if not request.qa_data:
            raise HTTPException(status_code=400, detail="QA 데이터가 비어있습니다.")
        
        logger.info(f"🔄 QA 데이터 저장 시작: {len(request.qa_data)}개 항목")
        
        # 1. 텍스트 청크 준비
        chunks = []
        texts = []
        
        for i, qa in enumerate(request.qa_data):
            chunk_id = f"{request.source_file}_{i}"
            # 질문과 답변을 결합한 텍스트 생성
            combined_text = f"Q: {qa.question}\nA: {qa.answer}"
            
            chunk_data = {
                "id": i + 1,  # 정수 ID 사용 (1부터 시작)
                "text": combined_text,
                "source": qa.source,
                "page": qa.page,
                "question": qa.question,
                "answer": qa.answer,
                "original_id": chunk_id
            }
            
            chunks.append(chunk_data)
            texts.append(combined_text)
        
        # 2. 임베딩 생성
        logger.info(f"🔄 {len(texts)}개 텍스트 임베딩 생성 중...")
        embeddings = embedding_model.encode(texts)
        
        # 3. 임베딩을 청크에 할당
        for chunk, embedding in zip(chunks, embeddings):
            chunk["vector"] = embedding
        
        # 4. 벡터 스토어에 저장
        success = vector_store.insert_chunks(chunks)
        
        if success:
            logger.info(f"🎉 총 {len(chunks)}개 QA 쌍이 벡터 스토어에 저장되었습니다!")
            return {
                "success": True,
                "message": f"{len(chunks)}개 QA 쌍이 성공적으로 저장되었습니다.",
                "total_stored": len(chunks),
                "source_file": request.source_file
            }
        else:
            raise HTTPException(status_code=500, detail="벡터 스토어 저장에 실패했습니다.")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ QA 데이터 저장 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"저장 중 오류가 발생했습니다: {str(e)}")

@router.post("/search_similar", response_model=SearchResponse)
async def search_similar(request: SearchRequest):
    """유사한 텍스트 검색"""
    try:
        if not request.query.strip():
            raise HTTPException(status_code=400, detail="검색 쿼리가 비어있습니다.")
        
        logger.info(f"🔍 유사도 검색 시작: '{request.query}'")
        
        # 1. 쿼리 임베딩 생성
        query_embedding = embedding_model.encode([request.query])[0]
        
        # 2. 유사도 검색
        results = vector_store.search(query_embedding, request.top_k)
        
        logger.info(f"✅ 검색 완료: {len(results)}개 결과 반환")
        
        return SearchResponse(
            results=results,
            total_found=len(results),
            query=request.query
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 검색 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"검색 중 오류가 발생했습니다: {str(e)}")

@router.delete("/clear_collection")
async def clear_collection():
    """컬렉션 초기화"""
    try:
        success = vector_store.delete_collection()
        
        if success:
            return {
                "success": True,
                "message": "컬렉션이 성공적으로 삭제되었습니다."
            }
        else:
            raise HTTPException(status_code=500, detail="컬렉션 삭제에 실패했습니다.")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 컬렉션 삭제 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"삭제 중 오류가 발생했습니다: {str(e)}")

@router.get("/collection_info", response_model=CollectionInfoResponse)
async def get_collection_info():
    """컬렉션 정보 조회"""
    try:
        info = vector_store.get_collection_info()
        
        return CollectionInfoResponse(
            collection_name=info["collection_name"],
            total_chunks=info["total_chunks"],
            embedding_dimension=info["embedding_dimension"],
            metric_type=info["metric_type"]
        )
        
    except Exception as e:
        logger.error(f"❌ 컬렉션 정보 조회 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"정보 조회 중 오류가 발생했습니다: {str(e)}")

@router.post("/encode_text")
async def encode_text(texts: List[str]):
    """텍스트를 임베딩으로 변환"""
    try:
        if not texts:
            raise HTTPException(status_code=400, detail="텍스트 리스트가 비어있습니다.")
        
        logger.info(f"🔄 {len(texts)}개 텍스트 임베딩 생성 중...")
        
        embeddings = embedding_model.encode(texts)
        
        return {
            "success": True,
            "embeddings": embeddings,
            "dimension": embedding_model.get_dimension(),
            "total_encoded": len(embeddings)
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 임베딩 생성 중 오류: {str(e)}")
        raise HTTPException(status_code=500, detail=f"임베딩 생성 중 오류가 발생했습니다: {str(e)}")

@router.get("/health")
async def health_check():
    """헬스 체크"""
    try:
        # 임베딩 모델 테스트
        test_embedding = embedding_model.encode(["test"])[0]
        
        # Milvus 연결 테스트
        info = vector_store.get_collection_info()
        
        return {
            "status": "healthy",
            "embedding_model": embedding_config.model_name,
            "embedding_dimension": embedding_model.get_dimension(),
            "milvus_connected": True,
            "collection_info": info
        }
        
    except Exception as e:
        logger.error(f"❌ 헬스 체크 실패: {str(e)}")
        return {
            "status": "unhealthy",
            "error": str(e)
        } 
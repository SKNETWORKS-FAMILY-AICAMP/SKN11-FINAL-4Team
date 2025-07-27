"""
VLLM + Milvus 기반 벡터 스토어 서비스
auto_rag의 embed_store_vllm.py를 기반으로 프로젝트에 통합
"""

import os
import logging
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod
from pathlib import Path
import asyncio

from pymilvus import MilvusClient, DataType, Collection
import numpy as np

# Backend의 임베딩 클라이언트 import
from app.services.embedding_client import VLLMEmbeddingClient, generate_embeddings

logger = logging.getLogger(__name__)


@dataclass
class MilvusConfig:
    """Milvus 설정 클래스"""
    uri: str = "./milvus_rag.db"  # Milvus Lite용 로컬 DB 파일
    collection_name: str = "rag_chunks"
    index_type: str = "AUTOINDEX"
    metric_type: str = "COSINE"


@dataclass
class TextChunk:
    """텍스트 청크 데이터 클래스"""
    id: str
    text: str
    metadata: Dict[str, Any]
    embedding: Optional[List[float]] = None


class VectorStore(ABC):
    """벡터 스토어 인터페이스"""
    
    @abstractmethod
    def insert(self, chunks: List[TextChunk]) -> bool:
        pass
    
    @abstractmethod
    def search(self, query_embedding: List[float], top_k: int = 5) -> List[Dict]:
        pass
    
    @abstractmethod
    def delete_collection(self) -> bool:
        pass


class MilvusVectorStore(VectorStore):
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
    
    def insert(self, chunks: List[TextChunk]) -> bool:
        """텍스트 청크를 Milvus에 저장"""
        try:
            # 데이터 준비
            data = []
            for i, chunk in enumerate(chunks):
                data.append({
                    "id": i + 1,  # 정수 ID 사용 (1부터 시작)
                    "vector": chunk.embedding,
                    "text": chunk.text,
                    "source": chunk.metadata.get("source", "unknown"),
                    "page": chunk.metadata.get("page", 0),
                    "original_id": chunk.id  # 원본 ID는 별도 필드로 저장
                })
            
            # 삽입
            self.client.insert(
                collection_name=self.config.collection_name,
                data=data
            )
            
            logger.info(f"✅ {len(chunks)}개 청크를 Milvus에 저장 완료")
            return True
            
        except Exception as e:
            logger.error(f"❌ Milvus 삽입 실패: {e}")
            return False
    
    def search(self, query_embedding: List[float], top_k: int = 5) -> List[Dict]:
        """유사한 벡터 검색"""
        try:
            # 검색 실행
            results = self.client.search(
                collection_name=self.config.collection_name,
                data=[query_embedding],
                anns_field="vector",
                param={"metric_type": self.config.metric_type, "params": {"nprobe": 10}},
                limit=top_k,
                output_fields=["text", "source", "page", "original_id"]
            )
            
            # 결과 변환
            search_results = []
            for result in results[0]:  # 첫 번째 쿼리 결과
                search_results.append({
                    "text": result.entity.get("text", ""),
                    "score": result.score,
                    "metadata": {
                        "source": result.entity.get("source", "unknown"),
                        "page": result.entity.get("page", 0),
                        "original_id": result.entity.get("original_id", "")
                    }
                })
            
            logger.info(f"🔍 Milvus 검색 완료: {len(search_results)}개 결과")
            return search_results
            
        except Exception as e:
            logger.error(f"❌ Milvus 검색 실패: {e}")
            return []
    
    def delete_collection(self) -> bool:
        """컬렉션 삭제"""
        try:
            if self.client.has_collection(collection_name=self.config.collection_name):
                self.client.drop_collection(collection_name=self.config.collection_name)
                logger.info(f"✅ 컬렉션 삭제 완료: {self.config.collection_name}")
            return True
        except Exception as e:
            logger.error(f"❌ 컬렉션 삭제 실패: {e}")
            return False


class VLLMEmbeddingStore:
    """VLLM 서버와 연동된 Milvus 스토어"""
    
    def __init__(self, 
                 milvus_config: Optional[MilvusConfig] = None,
                 vllm_base_url: str = "http://localhost:8001"):
        
        self.milvus_config = milvus_config or MilvusConfig()
        self.vllm_base_url = vllm_base_url
        self.vector_store = None
        self.embedding_dim = None
        
        # 비동기 초기화
        asyncio.create_task(self._initialize_vector_store())
    
    def _initialize_vector_store(self):
        """벡터 스토어 초기화"""
        try:
            # 임시로 1024차원 사용 (BGE-M3)
            self.embedding_dim = 1024
            self.vector_store = MilvusVectorStore(self.milvus_config, self.embedding_dim)
            logger.info("✅ VLLM + Milvus 벡터 스토어 초기화 완료")
        except Exception as e:
            logger.error(f"❌ 벡터 스토어 초기화 실패: {e}")
    
    async def _get_embedding_dimension(self) -> int:
        """VLLM 서버에서 임베딩 차원 조회"""
        try:
            from app.services.embedding_client import get_embedding_client
            client = get_embedding_client()
            async with client:
                info = await client.get_embedding_info()
                return info.get("dimension", 1024)
        except Exception as e:
            logger.warning(f"⚠️ 임베딩 차원 조회 실패, 기본값 사용: {e}")
            return 1024
    
    async def store_qa_chunks(self, qa_data: List[Dict], source_file: str = "document.pdf") -> bool:
        """QA 데이터를 Milvus에 저장"""
        try:
            if not self.vector_store:
                logger.error("❌ 벡터 스토어가 초기화되지 않았습니다.")
                return False
            
            logger.info(f"💾 QA 데이터 저장 시작: {len(qa_data)}개")
            
            # 텍스트 추출
            texts = []
            for qa in qa_data:
                texts.append(qa["question"])
                texts.append(qa["answer"])
            
            # VLLM 서버에서 임베딩 생성
            embeddings = await generate_embeddings(texts)
            
            # TextChunk 객체 생성
            chunks = []
            chunk_index = 0
            
            for qa in qa_data:
                # 질문 청크
                question_chunk = TextChunk(
                    id=f"{source_file}_q_{qa['chunk_id']}",
                    text=qa["question"],
                    metadata={
                        "type": "question",
                        "source": source_file,
                        "chunk_id": qa["chunk_id"],
                        "page": qa.get("page", 1)
                    },
                    embedding=embeddings[chunk_index]
                )
                
                # 답변 청크
                answer_chunk = TextChunk(
                    id=f"{source_file}_a_{qa['chunk_id']}",
                    text=qa["answer"],
                    metadata={
                        "type": "answer",
                        "source": source_file,
                        "chunk_id": qa["chunk_id"],
                        "page": qa.get("page", 1)
                    },
                    embedding=embeddings[chunk_index + 1]
                )
                
                chunks.extend([question_chunk, answer_chunk])
                chunk_index += 2
            
            # Milvus에 저장
            success = self.vector_store.insert(chunks)
            
            if success:
                logger.info(f"✅ QA 데이터 저장 완료: {len(chunks)}개 청크")
            else:
                logger.error("❌ QA 데이터 저장 실패")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ QA 데이터 저장 실패: {e}")
            return False
    
    async def search_similar(self, query: str, top_k: int = 5) -> List[Dict]:
        """유사한 문서 검색"""
        try:
            if not self.vector_store:
                logger.error("❌ 벡터 스토어가 초기화되지 않았습니다.")
                return []
            
            # 쿼리 임베딩 생성
            query_embeddings = await generate_embeddings([query])
            query_embedding = query_embeddings[0]
            
            # Milvus에서 검색
            results = self.vector_store.search(query_embedding, top_k)
            
            logger.info(f"🔍 검색 완료: {len(results)}개 결과")
            return results
            
        except Exception as e:
            logger.error(f"❌ 검색 실패: {e}")
            return []
    
    def clear_collection(self) -> bool:
        """컬렉션 정리"""
        try:
            if self.vector_store:
                return self.vector_store.delete_collection()
            return False
        except Exception as e:
            logger.error(f"❌ 컬렉션 정리 실패: {e}")
            return False
    
    async def health_check(self) -> Dict[str, Any]:
        """상태 확인"""
        try:
            # VLLM 서버 상태 확인
            from app.services.vllm_client import vllm_health_check
            vllm_healthy = await vllm_health_check()
            
            # Milvus 상태 확인
            milvus_healthy = self.vector_store is not None
            
            return {
                "vllm_server": "healthy" if vllm_healthy else "unhealthy",
                "milvus_store": "healthy" if milvus_healthy else "unhealthy",
                "overall": "healthy" if (vllm_healthy and milvus_healthy) else "unhealthy"
            }
        except Exception as e:
            logger.error(f"❌ 상태 확인 실패: {e}")
            return {
                "vllm_server": "unknown",
                "milvus_store": "unknown",
                "overall": "unhealthy"
            }


# 전역 인스턴스
_vllm_milvus_store = None

def get_vllm_milvus_store() -> VLLMEmbeddingStore:
    """전역 VLLM + Milvus 스토어 인스턴스 반환"""
    global _vllm_milvus_store
    
    if _vllm_milvus_store is None:
        from app.core.config import settings
        vllm_url = getattr(settings, 'VLLM_BASE_URL', 'http://localhost:8001')
        _vllm_milvus_store = VLLMEmbeddingStore(vllm_base_url=vllm_url)
    
    return _vllm_milvus_store 
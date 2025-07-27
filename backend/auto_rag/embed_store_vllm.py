import os
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod
from pathlib import Path
import asyncio
import logging

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
            result = self.client.insert(
                collection_name=self.config.collection_name,
                data=data
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
                output_fields=["text", "source", "page"]
            )
            
            return [
                {
                    "text": hit["entity"]["text"],
                    "source": hit["entity"]["source"],
                    "page": hit["entity"]["page"],
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

class VLLMEmbeddingStore:
    """VLLM 서버 기반 임베딩 스토어"""
    
    def __init__(self, 
                 milvus_config: Optional[MilvusConfig] = None,
                 vllm_base_url: str = "http://localhost:8001"):
        
        self.milvus_config = milvus_config or MilvusConfig()
        self.vllm_base_url = vllm_base_url
        
        # VLLM 임베딩 클라이언트 초기화
        self.embedding_client = VLLMEmbeddingClient(base_url=vllm_base_url)
        
        # 벡터 스토어 초기화 (차원은 VLLM에서 가져옴)
        self.vector_store = None
        self._initialize_vector_store()
    
    def _initialize_vector_store(self):
        """벡터 스토어 초기화 (비동기로 임베딩 차원 가져오기)"""
        try:
            # 기본 차원으로 초기화 (나중에 업데이트)
            embedding_dim = 1024  # BGE-M3 기본 차원
            self.vector_store = MilvusVectorStore(self.milvus_config, embedding_dim)
            logger.info("✅ 벡터 스토어 초기화 완료")
        except Exception as e:
            logger.error(f"❌ 벡터 스토어 초기화 실패: {e}")
            raise
    
    async def _get_embedding_dimension(self) -> int:
        """VLLM 서버에서 임베딩 차원 가져오기"""
        try:
            info = await self.embedding_client.get_embedding_info()
            return info.get("dimension", 1024)
        except Exception as e:
            logger.warning(f"⚠️ 임베딩 차원 조회 실패, 기본값 사용: {e}")
            return 1024
    
    async def store_qa_chunks(self, qa_data: List[Dict], source_file: str = "document.pdf") -> bool:
        """QA 데이터를 임베딩하여 벡터 스토어에 저장"""
        try:
            # 1. 텍스트 청크 준비
            chunks = []
            texts = []
            
            for i, qa in enumerate(qa_data):
                chunk_id = f"{source_file}_{i}"
                # 질문과 답변을 결합한 텍스트 생성
                combined_text = f"Q: {qa['question']}\nA: {qa['answer']}"
                
                chunk = TextChunk(
                    id=chunk_id,
                    text=combined_text,
                    metadata={
                        "source": source_file,
                        "page": qa.get("source_page", 0),
                        "question": qa["question"],
                        "answer": qa["answer"]
                    }
                )
                
                chunks.append(chunk)
                texts.append(combined_text)
            
            # 2. VLLM 서버에서 임베딩 생성
            logger.info(f"🔄 VLLM 서버에서 {len(texts)}개 텍스트 임베딩 생성 중...")
            embeddings = await generate_embeddings(texts)
            
            # 3. 임베딩을 청크에 할당
            for chunk, embedding in zip(chunks, embeddings):
                chunk.embedding = embedding
            
            # 4. 벡터 스토어에 저장
            success = self.vector_store.insert(chunks)
            
            if success:
                logger.info(f"🎉 총 {len(chunks)}개 QA 쌍이 벡터 스토어에 저장되었습니다!")
            
            return success
            
        except Exception as e:
            logger.error(f"❌ 저장 중 오류 발생: {str(e)}")
            return False
    
    async def search_similar(self, query: str, top_k: int = 5) -> List[Dict]:
        """유사한 텍스트 검색"""
        try:
            # VLLM 서버에서 쿼리 임베딩 생성
            query_embeddings = await generate_embeddings([query])
            query_embedding = query_embeddings[0]
            
            # 유사도 검색
            results = self.vector_store.search(query_embedding, top_k)
            
            return results
            
        except Exception as e:
            logger.error(f"❌ 검색 중 오류 발생: {str(e)}")
            return []
    
    def clear_collection(self) -> bool:
        """컬렉션 초기화"""
        return self.vector_store.delete_collection()
    
    async def health_check(self) -> Dict[str, Any]:
        """VLLM 임베딩 서버 상태 확인"""
        try:
            return await self.embedding_client.health_check()
        except Exception as e:
            logger.error(f"❌ VLLM 임베딩 서버 상태 확인 실패: {e}")
            return {"status": "error", "message": str(e)}

# 기존 함수와의 호환성을 위한 래퍼 함수
async def store_to_milvus_vllm(qa_chunks: List[str], source_file: str = "document.pdf"):
    """
    VLLM 서버를 사용하는 기존 함수와 호환성을 위한 래퍼 함수
    """
    # qa_chunks가 문자열 리스트인 경우 Dict 형태로 변환
    if qa_chunks and isinstance(qa_chunks[0], str):
        qa_data = [
            {
                "question": f"이 내용은 무엇에 대한 것인가요?",
                "answer": chunk,
                "source_page": 1
            }
            for chunk in qa_chunks
        ]
    else:
        qa_data = qa_chunks
    
    # VLLM 임베딩 스토어 생성 및 저장
    store = VLLMEmbeddingStore()
    success = await store.store_qa_chunks(qa_data, source_file)
    
    if success:
        return store
    else:
        raise RuntimeError("VLLM 벡터 스토어 저장 실패") 
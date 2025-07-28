"""
RAG 임베딩 서비스
auto_rag/embed_store.py를 backend/services로 이동
"""

import os
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from abc import ABC, abstractmethod
from pathlib import Path

from sentence_transformers import SentenceTransformer
from pymilvus import MilvusClient, DataType, Collection
import numpy as np


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
    uri: str = "./rag_data/vectorstore.db"
    collection_name: str = "rag_documents"
    metric_type: str = "COSINE"
    index_type: str = "IVF_FLAT"


class TextChunk:
    """텍스트 청크 클래스"""
    def __init__(self, text: str, metadata: Dict[str, Any] = None):
        self.id = str(hash(text))  # 간단한 ID 생성
        self.text = text
        self.metadata = metadata or {}
        self.embedding = None


class HuggingFaceEmbedding:
    """HuggingFace 임베딩 모델"""
    
    def __init__(self, config: EmbeddingConfig):
        self.config = config
        self.model = None
        self._load_model()
    
    def _load_model(self):
        """모델 로드"""
        try:
            self.model = SentenceTransformer(
                self.config.model_name,
                device=self.config.device
            )
            print(f"✅ 임베딩 모델 로드 성공: {self.config.model_name}")
        except Exception as e:
            raise RuntimeError(f"임베딩 모델 로드 실패: {str(e)}")
    
    def encode_text(self, text: str) -> List[float]:
        """텍스트를 임베딩으로 변환"""
        try:
            embedding = self.model.encode(text)
            return embedding.tolist()
        except Exception as e:
            raise RuntimeError(f"텍스트 인코딩 실패: {str(e)}")
    
    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        """배치로 텍스트를 임베딩으로 변환"""
        try:
            embeddings = self.model.encode(texts)
            return embeddings.tolist()
        except Exception as e:
            raise RuntimeError(f"배치 인코딩 실패: {str(e)}")


class VectorStore(ABC):
    """벡터 스토어 추상 클래스"""
    
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
            print(f"✅ Milvus 연결 성공: {self.config.uri}")
        except Exception as e:
            raise ConnectionError(f"Milvus 연결 실패: {str(e)}")
    
    def _create_collection_if_not_exists(self):
        """컬렉션이 없으면 생성"""
        try:
            if self.client.has_collection(collection_name=self.config.collection_name):
                print(f"✅ 기존 컬렉션 사용: {self.config.collection_name}")
                return
            
            # 컬렉션 생성
            self.client.create_collection(
                collection_name=self.config.collection_name,
                dimension=self.embedding_dim,
                metric_type=self.config.metric_type,
                index_type=self.config.index_type
            )
            print(f"✅ 새 컬렉션 생성: {self.config.collection_name}")
            
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
            
            print(f"✅ Milvus에 {len(chunks)}개 청크 저장 완료")
            return True
            
        except Exception as e:
            print(f"❌ Milvus 저장 실패: {str(e)}")
            return False
    
    def search(self, query_embedding: List[float], top_k: int = 5) -> List[Dict]:
        """유사도 검색"""
        try:
            results = self.client.search(
                collection_name=self.config.collection_name,
                data=[query_embedding],
                limit=top_k,
                output_fields=["text", "source", "page", "original_id"]
            )
            
            # 결과 포맷팅
            formatted_results = []
            for result in results:
                for hit in result:
                    formatted_results.append({
                        "text": hit.entity.get("text", ""),
                        "source": hit.entity.get("source", "unknown"),
                        "page": hit.entity.get("page", 0),
                        "score": hit.score,
                        "id": hit.entity.get("original_id", "")
                    })
            
            return formatted_results
            
        except Exception as e:
            print(f"❌ Milvus 검색 실패: {str(e)}")
            return []
    
    def delete_collection(self) -> bool:
        """컬렉션 삭제"""
        try:
            if self.client.has_collection(collection_name=self.config.collection_name):
                self.client.drop_collection(collection_name=self.config.collection_name)
                print(f"✅ 컬렉션 삭제 완료: {self.config.collection_name}")
            return True
        except Exception as e:
            print(f"❌ 컬렉션 삭제 실패: {str(e)}")
            return False


class EmbeddingStore:
    """임베딩 스토어 통합 관리"""
    
    def __init__(self, embedding_config: EmbeddingConfig, milvus_config: MilvusConfig):
        self.embedding_model = HuggingFaceEmbedding(embedding_config)
        self.vector_store = MilvusVectorStore(milvus_config, embedding_config.dimension)
    
    def store_qa_chunks(self, qa_data: List[Dict], source_file: str) -> bool:
        """QA 데이터를 벡터 스토어에 저장"""
        try:
            # QA 데이터를 TextChunk로 변환
            chunks = []
            for qa in qa_data:
                # 질문과 답변을 결합
                combined_text = f"질문: {qa.get('question', '')}\n답변: {qa.get('answer', '')}"
                
                chunk = TextChunk(
                    text=combined_text,
                    metadata={
                        "source": source_file,
                        "question": qa.get('question', ''),
                        "answer": qa.get('answer', ''),
                        "page": qa.get('page', 0)
                    }
                )
                
                # 임베딩 생성
                chunk.embedding = self.embedding_model.encode_text(combined_text)
                chunks.append(chunk)
            
            # 벡터 스토어에 저장
            return self.vector_store.insert(chunks)
            
        except Exception as e:
            print(f"❌ QA 청크 저장 실패: {str(e)}")
            return False
    
    def search_similar(self, query: str, top_k: int = 5) -> List[Dict]:
        """유사도 검색"""
        try:
            # 쿼리 임베딩 생성
            query_embedding = self.embedding_model.encode_text(query)
            
            # 벡터 검색
            results = self.vector_store.search(query_embedding, top_k)
            
            return results
            
        except Exception as e:
            print(f"❌ 유사도 검색 실패: {str(e)}")
            return []
    
    def clear_collection(self) -> bool:
        """컬렉션 초기화"""
        return self.vector_store.delete_collection() 
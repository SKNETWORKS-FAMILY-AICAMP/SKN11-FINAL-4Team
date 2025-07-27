import os
import json
import logging
import asyncio
from typing import List, Dict, Optional, Any
from pathlib import Path
from dataclasses import dataclass

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ============================================================================
# 설정 클래스들
# ============================================================================

@dataclass
class RAGConfig:
    """RAG 설정 클래스"""
    vllm_base_url: str = "http://localhost:8000"
    embedding_model: str = "BAAI/bge-m3"
    search_top_k: int = 3
    score_threshold: float = 0.7
    max_context_length: int = 2000

# ============================================================================
# Pydantic 모델들
# ============================================================================

class QAChunk(BaseModel):
    """QA 청크 모델"""
    question: str
    answer: str
    source: str = "document.pdf"
    page: int = 0
    metadata: Dict[str, Any] = {}

class StoreQARequest(BaseModel):
    """QA 데이터 저장 요청 모델"""
    qa_data: List[QAChunk]
    source_file: str = "document.pdf"

class SearchRequest(BaseModel):
    """검색 요청 모델"""
    query: str
    top_k: int = 3

class SearchResult(BaseModel):
    """검색 결과 모델"""
    text: str
    score: float
    source: str
    page: int
    question: str = ""
    answer: str = ""

class SearchResponse(BaseModel):
    """검색 응답 모델"""
    results: List[SearchResult]
    total_found: int
    query: str

# ============================================================================
# RAG 서비스 클래스
# ============================================================================

class RAGService:
    """RAG 서비스 클래스 - VLLM 서버와 통신"""
    
    def __init__(self, config: Optional[RAGConfig] = None):
        self.config = config or RAGConfig()
        self.client = httpx.AsyncClient(timeout=30.0)
        
    async def __aenter__(self):
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def _make_request(self, method: str, endpoint: str, data: Optional[Dict] = None) -> Dict:
        """VLLM 서버에 요청 보내기"""
        url = f"{self.config.vllm_base_url}{endpoint}"
        
        try:
            if method.upper() == "GET":
                response = await self.client.get(url)
            elif method.upper() == "POST":
                response = await self.client.post(url, json=data)
            elif method.upper() == "DELETE":
                response = await self.client.delete(url)
            else:
                raise ValueError(f"지원하지 않는 HTTP 메서드: {method}")
            
            response.raise_for_status()
            return response.json()
            
        except httpx.HTTPStatusError as e:
            logger.error(f"HTTP 오류 {e.response.status_code}: {e.response.text}")
            raise
        except httpx.RequestError as e:
            logger.error(f"요청 오류: {e}")
            raise
        except Exception as e:
            logger.error(f"예상치 못한 오류: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """VLLM 서버의 RAG 헬스 체크"""
        try:
            return await self._make_request("GET", "/rag/health")
        except Exception as e:
            logger.error(f"RAG 헬스 체크 실패: {e}")
            return {"status": "unhealthy", "error": str(e)}
    
    async def store_qa_chunks(self, qa_data: List[QAChunk], source_file: str = "document.pdf") -> Dict[str, Any]:
        """QA 데이터를 VLLM 서버의 Milvus에 저장"""
        try:
            request_data = {
                "qa_data": [qa.dict() for qa in qa_data],
                "source_file": source_file
            }
            
            result = await self._make_request("POST", "/rag/store_qa_chunks", request_data)
            logger.info(f"✅ QA 데이터 저장 완료: {len(qa_data)}개 항목")
            return result
            
        except Exception as e:
            logger.error(f"❌ QA 데이터 저장 실패: {e}")
            raise
    
    async def search_similar(self, query: str, top_k: int = 3) -> SearchResponse:
        """유사한 텍스트 검색"""
        try:
            request_data = {
                "query": query,
                "top_k": top_k
            }
            
            result = await self._make_request("POST", "/rag/search_similar", request_data)
            
            # SearchResult 객체로 변환
            search_results = [
                SearchResult(
                    text=item["text"],
                    score=item["score"],
                    source=item["source"],
                    page=item["page"],
                    question=item.get("question", ""),
                    answer=item.get("answer", "")
                )
                for item in result["results"]
            ]
            
            return SearchResponse(
                results=search_results,
                total_found=result["total_found"],
                query=result["query"]
            )
            
        except Exception as e:
            logger.error(f"❌ 검색 실패: {e}")
            raise
    
    async def clear_collection(self) -> Dict[str, Any]:
        """컬렉션 초기화"""
        try:
            result = await self._make_request("DELETE", "/rag/clear_collection")
            logger.info("✅ 컬렉션 초기화 완료")
            return result
            
        except Exception as e:
            logger.error(f"❌ 컬렉션 초기화 실패: {e}")
            raise
    
    async def get_collection_info(self) -> Dict[str, Any]:
        """컬렉션 정보 조회"""
        try:
            return await self._make_request("GET", "/rag/collection_info")
        except Exception as e:
            logger.error(f"❌ 컬렉션 정보 조회 실패: {e}")
            raise
    
    async def encode_text(self, texts: List[str]) -> Dict[str, Any]:
        """텍스트를 임베딩으로 변환"""
        try:
            result = await self._make_request("POST", "/rag/encode_text", texts)
            return result
            
        except Exception as e:
            logger.error(f"❌ 텍스트 인코딩 실패: {e}")
            raise

# ============================================================================
# 고급 RAG 검색 기능
# ============================================================================

class AdvancedRAGService(RAGService):
    """고급 RAG 서비스 - 필터링, 재랭킹 등 포함"""
    
    async def search_with_filters(self, 
                                query: str, 
                                top_k: int = 3,
                                min_score: float = 0.7,
                                allowed_sources: Optional[List[str]] = None) -> SearchResponse:
        """필터가 적용된 검색"""
        try:
            # 기본 검색 수행
            search_response = await self.search_similar(query, top_k * 2)  # 더 많이 검색
            
            # 점수 필터링
            filtered_results = [
                result for result in search_response.results 
                if result.score >= min_score
            ]
            
            # 출처 필터링
            if allowed_sources:
                filtered_results = [
                    result for result in filtered_results
                    if result.source in allowed_sources
                ]
            
            # 중복 제거 (간단한 텍스트 유사도 기반)
            unique_results = self._remove_duplicates(filtered_results)
            
            # 최종 결과 개수 조정
            final_results = unique_results[:top_k]
            
            return SearchResponse(
                results=final_results,
                total_found=len(final_results),
                query=query
            )
            
        except Exception as e:
            logger.error(f"❌ 고급 검색 실패: {e}")
            raise
    
    def _remove_duplicates(self, results: List[SearchResult], similarity_threshold: float = 0.9) -> List[SearchResult]:
        """중복 제거"""
        if not results:
            return results
        
        unique_results = [results[0]]
        
        for result in results[1:]:
            is_duplicate = False
            for existing in unique_results:
                similarity = self._calculate_text_similarity(result.text, existing.text)
                if similarity > similarity_threshold:
                    is_duplicate = True
                    break
            
            if not is_duplicate:
                unique_results.append(result)
        
        return unique_results
    
    def _calculate_text_similarity(self, text1: str, text2: str) -> float:
        """간단한 텍스트 유사도 계산"""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)
    
    async def get_context_for_query(self, query: str, top_k: int = 3) -> str:
        """쿼리에 대한 컨텍스트 생성"""
        try:
            search_response = await self.search_similar(query, top_k)
            
            if not search_response.results:
                return ""
            
            # 컨텍스트 조합
            context_parts = []
            for result in search_response.results:
                context_parts.append(f"출처: {result.source} (페이지 {result.page})")
                context_parts.append(f"질문: {result.question}")
                context_parts.append(f"답변: {result.answer}")
                context_parts.append("---")
            
            context = "\n".join(context_parts).strip()
            
            # 최대 길이 제한
            if len(context) > self.config.max_context_length:
                context = context[:self.config.max_context_length] + "..."
            
            return context
            
        except Exception as e:
            logger.error(f"❌ 컨텍스트 생성 실패: {e}")
            return ""

# ============================================================================
# 팩토리 함수
# ============================================================================

def create_rag_service(vllm_base_url: Optional[str] = None) -> RAGService:
    """RAG 서비스 생성"""
    config = RAGConfig()
    if vllm_base_url:
        config.vllm_base_url = vllm_base_url
    
    return RAGService(config)

def create_advanced_rag_service(vllm_base_url: Optional[str] = None) -> AdvancedRAGService:
    """고급 RAG 서비스 생성"""
    config = RAGConfig()
    if vllm_base_url:
        config.vllm_base_url = vllm_base_url
    
    return AdvancedRAGService(config)

# ============================================================================
# 사용 예시
# ============================================================================

async def example_usage():
    """사용 예시"""
    async with create_advanced_rag_service() as rag_service:
        # 헬스 체크
        health = await rag_service.health_check()
        print(f"RAG 서비스 상태: {health}")
        
        # QA 데이터 저장
        qa_data = [
            QAChunk(
                question="파이썬이란 무엇인가요?",
                answer="파이썬은 높은 가독성과 간결한 문법을 가진 프로그래밍 언어입니다.",
                source="python_guide.pdf",
                page=1
            ),
            QAChunk(
                question="머신러닝이란?",
                answer="머신러닝은 컴퓨터가 데이터로부터 학습하여 예측하는 기술입니다.",
                source="ml_intro.pdf",
                page=2
            )
        ]
        
        store_result = await rag_service.store_qa_chunks(qa_data, "sample_documents.pdf")
        print(f"저장 결과: {store_result}")
        
        # 검색
        search_result = await rag_service.search_similar("프로그래밍 언어에 대해 알려주세요", 3)
        print(f"검색 결과: {search_result}")
        
        # 컨텍스트 생성
        context = await rag_service.get_context_for_query("파이썬에 대해 알려주세요")
        print(f"컨텍스트: {context}")

if __name__ == "__main__":
    asyncio.run(example_usage()) 
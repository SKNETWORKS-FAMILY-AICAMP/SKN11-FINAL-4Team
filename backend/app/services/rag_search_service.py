"""
RAG 검색 서비스
auto_rag/rag_search.py를 backend/services로 이동
"""

import os
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from enum import Enum
from abc import ABC, abstractmethod
import logging

from .rag_embedding_service import EmbeddingStore, EmbeddingConfig, MilvusConfig

logger = logging.getLogger(__name__)


class SearchStrategy(Enum):
    """검색 전략"""
    VECTOR = "vector"
    KEYWORD = "keyword"
    HYBRID = "hybrid"


@dataclass
class SearchConfig:
    """검색 설정"""
    strategy: SearchStrategy = SearchStrategy.VECTOR
    top_k: int = 5
    min_score: float = 0.7
    include_context: bool = True


class SearchResult:
    """검색 결과 클래스"""
    def __init__(self, text: str, score: float, source: str, metadata: Dict[str, Any] = None):
        self.text = text
        self.score = score
        self.source = source
        self.metadata = metadata or {}
        self.rank = 0


class RAGSearcher:
    """RAG 검색기"""
    
    def __init__(self, embedding_store: EmbeddingStore, config: SearchConfig = None):
        self.embedding_store = embedding_store
        self.config = config or SearchConfig()
        self.reranker = None  # 향후 재랭커 추가 가능
    
    def search(self, query: str, top_k: int = None, min_score: float = None) -> List[SearchResult]:
        """검색 실행"""
        try:
            # 설정 병합
            top_k = top_k or self.config.top_k
            min_score = min_score or self.config.min_score
            
            # 벡터 검색 수행
            raw_results = self.embedding_store.search_similar(query, top_k)
            
            # SearchResult 객체로 변환
            search_results = self._convert_to_search_results(raw_results)
            
            # 점수 필터링
            filtered_results = [r for r in search_results if r.score >= min_score]
            
            # 랭킹 정보 업데이트
            for i, result in enumerate(filtered_results):
                result.rank = i + 1
            
            logger.info(f"✅ 검색 완료: {len(filtered_results)}개 결과 반환")
            return filtered_results
            
        except Exception as e:
            logger.error(f"❌ 검색 중 오류 발생: {str(e)}")
            return []
    
    def _convert_to_search_results(self, raw_results: List[Dict]) -> List[SearchResult]:
        """원시 검색 결과를 SearchResult 객체로 변환"""
        search_results = []
        
        for result in raw_results:
            # 텍스트에서 질문과 답변 분리
            text = result['text']
            question, answer = self._extract_qa_from_text(text)
            
            search_result = SearchResult(
                text=text,
                score=result['score'],
                source=result['source'],
                metadata={
                    'question': question,
                    'answer': answer,
                    'page': result.get('page', 0),
                    'id': result.get('id', '')
                }
            )
            search_results.append(search_result)
        
        return search_results
    
    def _extract_qa_from_text(self, text: str) -> tuple[str, str]:
        """텍스트에서 질문과 답변 추출"""
        try:
            if "질문:" in text and "답변:" in text:
                parts = text.split("답변:")
                if len(parts) == 2:
                    question_part = parts[0].replace("질문:", "").strip()
                    answer_part = parts[1].strip()
                    return question_part, answer_part
            
            # 기본값: 전체 텍스트를 답변으로 처리
            return "", text
        except Exception:
            return "", text


def retrieve_relevant_chunks(query: str, embedding_store: EmbeddingStore, top_k: int = 3) -> List[Dict]:
    """관련 청크 검색 (간단한 래퍼 함수)"""
    searcher = RAGSearcher(embedding_store)
    results = searcher.search(query, top_k)
    
    # Dict 형태로 변환
    chunks = []
    for result in results:
        chunks.append({
            'text': result.text,
            'score': result.score,
            'source': result.source,
            'metadata': result.metadata
        })
    
    return chunks 
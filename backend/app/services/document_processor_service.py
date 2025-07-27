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
class DocumentProcessorConfig:
    """문서 처리 설정 클래스"""
    vllm_base_url: str = "http://localhost:8000"
    min_paragraph_length: int = 30
    max_qa_pairs: int = 100
    chunk_size: int = 1000
    chunk_overlap: int = 200

# ============================================================================
# Pydantic 모델들
# ============================================================================

class DocumentChunk(BaseModel):
    """문서 청크 모델"""
    text: str
    page: int
    chunk_id: str
    metadata: Dict[str, Any] = {}

class QARequest(BaseModel):
    """QA 생성 요청 모델"""
    chunks: List[DocumentChunk]
    max_qa_pairs: int = 50
    system_prompt: str = "다음 텍스트에서 질문과 답변 쌍을 생성해주세요."

class QAResponse(BaseModel):
    """QA 생성 응답 모델"""
    qa_pairs: List[Dict[str, str]]
    total_generated: int
    source_chunks: List[str]

# ============================================================================
# 문서 처리 서비스 클래스
# ============================================================================

class DocumentProcessorService:
    """문서 처리 서비스 클래스 - VLLM 서버와 통신"""
    
    def __init__(self, config: Optional[DocumentProcessorConfig] = None):
        self.config = config or DocumentProcessorConfig()
        self.client = httpx.AsyncClient(timeout=60.0)  # 문서 처리는 시간이 오래 걸릴 수 있음
        
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
    
    async def generate_qa_from_chunks(self, 
                                    chunks: List[DocumentChunk], 
                                    max_qa_pairs: int = 50,
                                    system_prompt: str = None) -> QAResponse:
        """문서 청크에서 QA 쌍 생성"""
        try:
            if not chunks:
                raise ValueError("문서 청크가 비어있습니다.")
            
            # 시스템 프롬프트 설정
            if not system_prompt:
                system_prompt = (
                    "다음 텍스트에서 유용한 질문과 답변 쌍을 생성해주세요. "
                    "질문은 텍스트의 내용을 잘 이해할 수 있도록 구체적으로 작성하고, "
                    "답변은 텍스트의 정보를 정확하게 반영해야 합니다."
                )
            
            request_data = {
                "chunks": [chunk.dict() for chunk in chunks],
                "max_qa_pairs": max_qa_pairs,
                "system_prompt": system_prompt
            }
            
            logger.info(f"🔄 QA 생성 시작: {len(chunks)}개 청크, 최대 {max_qa_pairs}개 QA 쌍")
            
            result = await self._make_request("POST", "/qa/generate_from_chunks", request_data)
            
            qa_response = QAResponse(
                qa_pairs=result["qa_pairs"],
                total_generated=result["total_generated"],
                source_chunks=result["source_chunks"]
            )
            
            logger.info(f"✅ QA 생성 완료: {qa_response.total_generated}개 QA 쌍 생성")
            return qa_response
            
        except Exception as e:
            logger.error(f"❌ QA 생성 실패: {e}")
            raise
    
    async def process_document_file(self, 
                                  file_path: str,
                                  max_qa_pairs: int = 100) -> QAResponse:
        """문서 파일을 처리하여 QA 쌍 생성"""
        try:
            if not os.path.exists(file_path):
                raise FileNotFoundError(f"파일을 찾을 수 없습니다: {file_path}")
            
            # 파일 확장자 확인
            file_ext = Path(file_path).suffix.lower()
            if file_ext != '.pdf':
                raise ValueError(f"지원하지 않는 파일 형식입니다: {file_ext}")
            
            logger.info(f"📄 문서 처리 시작: {file_path}")
            
            # 문서를 청크로 분할
            chunks = await self._split_document_into_chunks(file_path)
            
            # QA 쌍 생성
            qa_response = await self.generate_qa_from_chunks(
                chunks, 
                max_qa_pairs,
                system_prompt=(
                    "다음 문서에서 유용한 질문과 답변 쌍을 생성해주세요. "
                    "질문은 문서의 핵심 내용을 잘 이해할 수 있도록 구체적으로 작성하고, "
                    "답변은 문서의 정보를 정확하게 반영해야 합니다. "
                    "각 QA 쌍은 독립적이고 유용한 정보를 제공해야 합니다."
                )
            )
            
            return qa_response
            
        except Exception as e:
            logger.error(f"❌ 문서 처리 실패: {e}")
            raise
    
    async def _split_document_into_chunks(self, file_path: str) -> List[DocumentChunk]:
        """문서를 청크로 분할"""
        try:
            # VLLM 서버의 문서 분할 API 호출
            request_data = {
                "file_path": file_path,
                "chunk_size": self.config.chunk_size,
                "chunk_overlap": self.config.chunk_overlap,
                "min_paragraph_length": self.config.min_paragraph_length
            }
            
            result = await self._make_request("POST", "/qa/split_document", request_data)
            
            chunks = [
                DocumentChunk(
                    text=chunk["text"],
                    page=chunk["page"],
                    chunk_id=chunk["chunk_id"],
                    metadata=chunk.get("metadata", {})
                )
                for chunk in result["chunks"]
            ]
            
            logger.info(f"✅ 문서 분할 완료: {len(chunks)}개 청크 생성")
            return chunks
            
        except Exception as e:
            logger.error(f"❌ 문서 분할 실패: {e}")
            raise
    
    async def health_check(self) -> Dict[str, Any]:
        """VLLM 서버의 QA 생성 헬스 체크"""
        try:
            return await self._make_request("GET", "/qa/health")
        except Exception as e:
            logger.error(f"QA 생성 헬스 체크 실패: {e}")
            return {"status": "unhealthy", "error": str(e)}

# ============================================================================
# 통합 문서 처리 서비스
# ============================================================================

class IntegratedDocumentService:
    """통합 문서 처리 서비스 - 문서 처리부터 RAG 저장까지"""
    
    def __init__(self, 
                 vllm_base_url: str = "http://localhost:8000",
                 rag_service=None):
        self.vllm_base_url = vllm_base_url
        self.doc_processor = DocumentProcessorService(
            DocumentProcessorConfig(vllm_base_url=vllm_base_url)
        )
        self.rag_service = rag_service
    
    async def process_and_store_document(self, 
                                       file_path: str,
                                       source_name: str = None,
                                       max_qa_pairs: int = 100) -> Dict[str, Any]:
        """문서를 처리하고 RAG에 저장"""
        try:
            if not source_name:
                source_name = Path(file_path).stem
            
            logger.info(f"🔄 통합 문서 처리 시작: {file_path}")
            
            # 1. 문서 처리하여 QA 쌍 생성
            qa_response = await self.doc_processor.process_document_file(
                file_path, max_qa_pairs
            )
            
            # 2. RAG에 저장
            if self.rag_service:
                from .rag_service import QAChunk
                
                qa_chunks = [
                    QAChunk(
                        question=qa["question"],
                        answer=qa["answer"],
                        source=source_name,
                        page=0,  # 페이지 정보는 청크에서 가져올 수 있음
                        metadata={"chunk_id": qa.get("chunk_id", "")}
                    )
                    for qa in qa_response.qa_pairs
                ]
                
                store_result = await self.rag_service.store_qa_chunks(
                    qa_chunks, source_name
                )
                
                return {
                    "success": True,
                    "document_processed": True,
                    "qa_generated": qa_response.total_generated,
                    "rag_stored": store_result.get("success", False),
                    "source_name": source_name,
                    "qa_pairs": qa_response.qa_pairs[:5]  # 샘플만 반환
                }
            else:
                return {
                    "success": True,
                    "document_processed": True,
                    "qa_generated": qa_response.total_generated,
                    "rag_stored": False,
                    "source_name": source_name,
                    "qa_pairs": qa_response.qa_pairs[:5]  # 샘플만 반환
                }
                
        except Exception as e:
            logger.error(f"❌ 통합 문서 처리 실패: {e}")
            return {
                "success": False,
                "error": str(e),
                "document_processed": False,
                "qa_generated": 0,
                "rag_stored": False
            }

# ============================================================================
# 팩토리 함수
# ============================================================================

def create_document_processor_service(vllm_base_url: Optional[str] = None) -> DocumentProcessorService:
    """문서 처리 서비스 생성"""
    config = DocumentProcessorConfig()
    if vllm_base_url:
        config.vllm_base_url = vllm_base_url
    
    return DocumentProcessorService(config)

def create_integrated_document_service(vllm_base_url: Optional[str] = None, rag_service=None) -> IntegratedDocumentService:
    """통합 문서 처리 서비스 생성"""
    return IntegratedDocumentService(vllm_base_url, rag_service)

# ============================================================================
# 사용 예시
# ============================================================================

async def example_usage():
    """사용 예시"""
    async with create_document_processor_service() as doc_service:
        # 헬스 체크
        health = await doc_service.health_check()
        print(f"문서 처리 서비스 상태: {health}")
        
        # 샘플 청크로 QA 생성
        sample_chunks = [
            DocumentChunk(
                text="파이썬은 1991년 프로그래머인 귀도 반 로섬이 발표한 고급 프로그래밍 언어입니다.",
                page=1,
                chunk_id="chunk_1"
            ),
            DocumentChunk(
                text="파이썬의 특징은 간결하고 읽기 쉬운 문법, 풍부한 라이브러리, 크로스 플랫폼 지원 등이 있습니다.",
                page=1,
                chunk_id="chunk_2"
            )
        ]
        
        qa_response = await doc_service.generate_qa_from_chunks(sample_chunks, 3)
        print(f"QA 생성 결과: {qa_response}")

if __name__ == "__main__":
    asyncio.run(example_usage()) 
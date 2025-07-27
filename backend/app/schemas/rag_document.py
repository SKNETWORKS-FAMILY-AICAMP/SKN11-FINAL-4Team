"""
RAG 문서 관련 스키마
"""

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

# ============================================================================
# 기본 스키마
# ============================================================================

class RAGDocumentBase(BaseModel):
    """RAG 문서 기본 스키마"""
    group_id: int = Field(..., description="그룹 ID")
    original_filename: str = Field(..., description="원본 파일명")
    source_name: str = Field(..., description="소스 이름")
    file_size: Optional[int] = Field(None, description="파일 크기 (bytes)")
    total_chunks: int = Field(0, description="총 청크 수")
    qa_pairs_generated: int = Field(0, description="생성된 QA 쌍 수")
    status: str = Field("processing", description="처리 상태")
    error_message: Optional[str] = Field(None, description="오류 메시지")

# ============================================================================
# 생성 스키마
# ============================================================================

class RAGDocumentCreate(RAGDocumentBase):
    """RAG 문서 생성 스키마"""
    pass

# ============================================================================
# 업데이트 스키마
# ============================================================================

class RAGDocumentUpdate(BaseModel):
    """RAG 문서 업데이트 스키마"""
    source_name: Optional[str] = Field(None, description="소스 이름")
    total_chunks: Optional[int] = Field(None, description="총 청크 수")
    qa_pairs_generated: Optional[int] = Field(None, description="생성된 QA 쌍 수")
    status: Optional[str] = Field(None, description="처리 상태")
    error_message: Optional[str] = Field(None, description="오류 메시지")

# ============================================================================
# 응답 스키마
# ============================================================================

class RAGDocument(RAGDocumentBase):
    """RAG 문서 응답 스키마"""
    document_id: str = Field(..., description="문서 ID")
    created_at: datetime = Field(..., description="생성 시간")
    updated_at: Optional[datetime] = Field(None, description="수정 시간")

    class Config:
        from_attributes = True

class RAGDocumentList(BaseModel):
    """RAG 문서 목록 응답 스키마"""
    documents: List[RAGDocument] = Field(..., description="문서 목록")
    total_count: int = Field(..., description="총 문서 수")

# ============================================================================
# 요약 스키마
# ============================================================================

class RAGDocumentSummary(BaseModel):
    """RAG 문서 요약 스키마"""
    document_id: str = Field(..., description="문서 ID")
    original_filename: str = Field(..., description="원본 파일명")
    source_name: str = Field(..., description="소스 이름")
    file_size: Optional[int] = Field(None, description="파일 크기")
    total_chunks: int = Field(..., description="총 청크 수")
    qa_pairs_generated: int = Field(..., description="생성된 QA 쌍 수")
    status: str = Field(..., description="처리 상태")
    created_at: datetime = Field(..., description="생성 시간")

    class Config:
        from_attributes = True 
"""
RAG 스키마 (기존 auto_rag 통합)
RAG 시스템에서 사용하는 Pydantic 스키마들입니다.
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Union
from datetime import datetime
from enum import Enum


class ProcessingStatus(str, Enum):
    """문서 처리 상태"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ChunkType(str, Enum):
    """청크 타입"""
    TEXT = "text"
    QUESTION = "question"
    ANSWER = "answer"


class RAGDocumentBase(BaseModel):
    """RAG 문서 기본 스키마"""
    group_id: int = Field(..., description="그룹 ID")
    filename: str = Field(..., description="파일명")
    file_path: str = Field(..., description="파일 경로")
    file_size: int = Field(..., description="파일 크기 (bytes)")
    title: Optional[str] = Field(None, description="문서 제목")
    author: Optional[str] = Field(None, description="작성자")
    description: Optional[str] = Field(None, description="문서 설명")
    max_qa_pairs: int = Field(100, description="최대 QA 쌍 수")
    chunk_size: int = Field(1000, description="청크 크기")
    chunk_overlap: int = Field(200, description="청크 오버랩")


class RAGDocumentCreate(RAGDocumentBase):
    """RAG 문서 생성 스키마"""
    pass


class RAGDocumentUpdate(BaseModel):
    """RAG 문서 업데이트 스키마"""
    title: Optional[str] = None
    author: Optional[str] = None
    description: Optional[str] = None
    processed: Optional[bool] = None
    processing_status: Optional[ProcessingStatus] = None


class RAGDocumentResponse(RAGDocumentBase):
    """RAG 문서 응답 스키마"""
    id: int
    upload_date: datetime
    processed: bool
    qa_pairs_count: int
    processing_status: ProcessingStatus
    error_message: Optional[str] = None
    collection_name: Optional[str] = None
    vector_count: int
    processing_time: Optional[float] = None
    embedding_time: Optional[float] = None
    total_tokens: int
    
    class Config:
        from_attributes = True


class RAGChunkBase(BaseModel):
    """RAG 청크 기본 스키마"""
    document_id: int = Field(..., description="문서 ID")
    chunk_index: int = Field(..., description="청크 인덱스")
    content: str = Field(..., description="청크 내용")
    chunk_type: ChunkType = Field(ChunkType.TEXT, description="청크 타입")
    page_number: Optional[int] = Field(None, description="페이지 번호")


class RAGChunkCreate(RAGChunkBase):
    """RAG 청크 생성 스키마"""
    pass


class RAGChunkResponse(RAGChunkBase):
    """RAG 청크 응답 스키마"""
    id: int
    embedding_id: Optional[str] = None
    vector_dimension: Optional[int] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class RAGQAPairBase(BaseModel):
    """RAG QA 쌍 기본 스키마"""
    document_id: int = Field(..., description="문서 ID")
    question: str = Field(..., description="질문")
    answer: str = Field(..., description="답변")
    confidence_score: float = Field(0.0, ge=0.0, le=1.0, description="신뢰도 점수")
    page_number: Optional[int] = Field(None, description="페이지 번호")


class RAGQAPairCreate(RAGQAPairBase):
    """RAG QA 쌍 생성 스키마"""
    pass


class RAGQAPairResponse(RAGQAPairBase):
    """RAG QA 쌍 응답 스키마"""
    id: int
    question_embedding_id: Optional[str] = None
    answer_embedding_id: Optional[str] = None
    created_at: datetime
    
    class Config:
        from_attributes = True


class SearchRequest(BaseModel):
    """검색 요청 스키마"""
    query: str = Field(..., description="검색 질의")
    top_k: int = Field(3, ge=1, le=20, description="검색 결과 수")
    min_score: float = Field(0.7, ge=0.0, le=1.0, description="최소 유사도 점수")
    include_context: bool = Field(True, description="컨텍스트 포함 여부")
    
    @validator('query')
    def validate_query(cls, v):
        if not v or not v.strip():
            raise ValueError('검색 질의는 비어있을 수 없습니다.')
        if len(v.strip()) < 2:
            raise ValueError('검색 질의는 최소 2자 이상이어야 합니다.')
        return v.strip()


class SearchResult(BaseModel):
    """검색 결과 스키마"""
    content: str = Field(..., description="검색된 내용")
    score: float = Field(..., ge=0.0, le=1.0, description="유사도 점수")
    source: str = Field(..., description="출처 파일")
    page: Optional[int] = Field(None, description="페이지 번호")
    context: Optional[str] = Field(None, description="컨텍스트")


class SearchResponse(BaseModel):
    """검색 응답 스키마"""
    success: bool = Field(True, description="성공 여부")
    query: str = Field(..., description="검색 질의")
    results: List[SearchResult] = Field(..., description="검색 결과")
    total_results: int = Field(..., description="총 결과 수")
    search_time: Optional[float] = Field(None, description="검색 시간 (초)")


class ChatRequest(BaseModel):
    """채팅 요청 스키마"""
    query: str = Field(..., description="사용자 질문")
    group_id: int = Field(..., description="그룹 ID")
    include_sources: bool = Field(True, description="출처 정보 포함 여부")
    temperature: Optional[float] = Field(0.8, ge=0.1, le=2.0, description="생성 온도")
    max_tokens: Optional[int] = Field(512, ge=1, le=2048, description="최대 토큰 수")
    
    @validator('query')
    def validate_query(cls, v):
        if not v or not v.strip():
            raise ValueError('질문은 비어있을 수 없습니다.')
        if len(v.strip()) < 2:
            raise ValueError('질문은 최소 2자 이상이어야 합니다.')
        return v.strip()


class ChatResponse(BaseModel):
    """채팅 응답 스키마"""
    query: str = Field(..., description="사용자 질문")
    response: str = Field(..., description="AI 응답")
    timestamp: datetime = Field(..., description="응답 시간")
    sources: Optional[List[SearchResult]] = Field(None, description="참고 출처")
    context_preview: Optional[str] = Field(None, description="컨텍스트 미리보기")
    model_info: Optional[Dict[str, Any]] = Field(None, description="모델 정보")
    confidence_score: Optional[float] = Field(None, ge=0.0, le=1.0, description="신뢰도 점수")


class DocumentUploadRequest(BaseModel):
    """문서 업로드 요청 스키마"""
    group_id: int = Field(..., description="그룹 ID")
    filename: str = Field(..., description="파일명")
    file_size: int = Field(..., description="파일 크기")
    title: Optional[str] = Field(None, description="문서 제목")
    author: Optional[str] = Field(None, description="작성자")
    description: Optional[str] = Field(None, description="문서 설명")
    max_qa_pairs: int = Field(100, ge=1, le=1000, description="최대 QA 쌍 수")
    chunk_size: int = Field(1000, ge=100, le=5000, description="청크 크기")
    chunk_overlap: int = Field(200, ge=0, le=1000, description="청크 오버랩")
    
    @validator('filename')
    def validate_filename(cls, v):
        if not v or not v.strip():
            raise ValueError('파일명은 비어있을 수 없습니다.')
        if not v.lower().endswith('.pdf'):
            raise ValueError('PDF 파일만 업로드 가능합니다.')
        return v.strip()


class DocumentUploadResponse(BaseModel):
    """문서 업로드 응답 스키마"""
    success: bool = Field(True, description="성공 여부")
    message: str = Field(..., description="응답 메시지")
    document_id: int = Field(..., description="문서 ID")
    filename: str = Field(..., description="파일명")
    file_size: int = Field(..., description="파일 크기")
    qa_pairs_generated: int = Field(..., description="생성된 QA 쌍 수")
    processing_time: Optional[float] = Field(None, description="처리 시간 (초)")


class PipelineConfig(BaseModel):
    """파이프라인 설정 스키마"""
    group_id: int = Field(..., description="그룹 ID")
    pipeline_name: str = Field(..., description="파이프라인 이름")
    lora_adapter: Optional[str] = Field(None, description="LoRA 어댑터")
    system_message: Optional[str] = Field(None, description="시스템 메시지")
    influencer_name: str = Field("AI", description="AI 캐릭터 이름")
    temperature: float = Field(0.8, ge=0.1, le=2.0, description="생성 온도")
    max_tokens: int = Field(512, ge=1, le=2048, description="최대 토큰 수")
    search_top_k: int = Field(3, ge=1, le=20, description="검색 결과 수")
    search_threshold: float = Field(0.7, ge=0.0, le=1.0, description="검색 임계값")
    
    @validator('pipeline_name')
    def validate_pipeline_name(cls, v):
        if not v or not v.strip():
            raise ValueError('파이프라인 이름은 비어있을 수 없습니다.')
        if len(v.strip()) < 2:
            raise ValueError('파이프라인 이름은 최소 2자 이상이어야 합니다.')
        return v.strip()


class PipelineResponse(BaseModel):
    """파이프라인 응답 스키마"""
    id: int = Field(..., description="파이프라인 ID")
    group_id: int = Field(..., description="그룹 ID")
    pipeline_name: str = Field(..., description="파이프라인 이름")
    lora_adapter: Optional[str] = None
    system_message: Optional[str] = None
    influencer_name: str
    temperature: float
    max_tokens: int
    search_top_k: int
    search_threshold: float
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    documents_count: int = Field(0, description="연결된 문서 수")
    
    class Config:
        from_attributes = True


class HealthCheckResponse(BaseModel):
    """상태 확인 응답 스키마"""
    status: str = Field(..., description="상태")
    message: str = Field(..., description="메시지")
    services: Dict[str, str] = Field(..., description="서비스 상태")
    timestamp: datetime = Field(default_factory=datetime.now, description="확인 시간")


class ErrorResponse(BaseModel):
    """오류 응답 스키마"""
    success: bool = Field(False, description="성공 여부")
    error: str = Field(..., description="오류 코드")
    message: str = Field(..., description="오류 메시지")
    details: Optional[Dict[str, Any]] = Field(None, description="상세 정보")
    timestamp: datetime = Field(default_factory=datetime.now, description="오류 발생 시간")


class SuccessResponse(BaseModel):
    """성공 응답 스키마"""
    success: bool = Field(True, description="성공 여부")
    message: str = Field(..., description="응답 메시지")
    data: Optional[Dict[str, Any]] = Field(None, description="응답 데이터")
    timestamp: datetime = Field(default_factory=datetime.now, description="응답 시간")


# 웹소켓 메시지 스키마
class WebSocketMessage(BaseModel):
    """웹소켓 메시지 기본 스키마"""
    type: str = Field(..., description="메시지 타입")
    content: Optional[str] = Field(None, description="메시지 내용")
    timestamp: datetime = Field(default_factory=datetime.now, description="메시지 시간")


class WebSocketConnectionMessage(WebSocketMessage):
    """웹소켓 연결 메시지"""
    type: str = Field("connection", description="메시지 타입")
    message: str = Field(..., description="연결 메시지")
    group_id: int = Field(..., description="그룹 ID")


class WebSocketTokenMessage(WebSocketMessage):
    """웹소켓 토큰 메시지"""
    type: str = Field("token", description="메시지 타입")
    content: str = Field(..., description="토큰 내용")


class WebSocketSourcesMessage(WebSocketMessage):
    """웹소켓 출처 메시지"""
    type: str = Field("sources", description="메시지 타입")
    content: List[SearchResult] = Field(..., description="출처 목록")


class WebSocketCompleteMessage(WebSocketMessage):
    """웹소켓 완료 메시지"""
    type: str = Field("complete", description="메시지 타입")
    message: str = Field(..., description="완료 메시지")


class WebSocketErrorMessage(WebSocketMessage):
    """웹소켓 오류 메시지"""
    type: str = Field("error", description="메시지 타입")
    message: str = Field(..., description="오류 메시지")
    error_code: Optional[str] = Field(None, description="오류 코드")


class WebSocketWarningMessage(WebSocketMessage):
    """웹소켓 경고 메시지"""
    type: str = Field("warning", description="메시지 타입")
    message: str = Field(..., description="경고 메시지") 
"""
RAG (Retrieval-Augmented Generation) 관련 데이터베이스 모델
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, JSON
from sqlalchemy.sql import func
from app.models.base import Base


class RAGPipeline(Base):
    """RAG 파이프라인 모델"""

    __tablename__ = "rag_pipelines"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, nullable=False, index=True, comment="그룹 ID")
    pdf_path = Column(String(500), nullable=False, comment="PDF 파일 경로")
    pdf_name = Column(String(255), nullable=False, comment="PDF 파일명")
    qa_count = Column(Integer, default=0, comment="QA 쌍 개수")
    system_message = Column(Text, comment="시스템 메시지")
    influencer_name = Column(String(100), default="AI", comment="인플루언서 이름")
    status = Column(String(50), default="active", comment="파이프라인 상태")
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), comment="생성 시간"
    )
    updated_at = Column(
        DateTime(timezone=True), onupdate=func.now(), comment="수정 시간"
    )

    # 메타데이터
    metadata = Column(JSON, comment="추가 메타데이터")


class RAGDocument(Base):
    """RAG 문서 모델"""

    __tablename__ = "rag_documents"

    id = Column(Integer, primary_key=True, index=True)
    pipeline_id = Column(Integer, nullable=False, index=True, comment="파이프라인 ID")
    chunk_id = Column(String(100), nullable=False, comment="청크 ID")
    chunk_type = Column(
        String(50), nullable=False, comment="청크 타입 (question/answer)"
    )
    text = Column(Text, nullable=False, comment="텍스트 내용")
    embedding = Column(JSON, comment="임베딩 벡터")
    metadata = Column(JSON, comment="메타데이터")
    page = Column(Integer, default=1, comment="페이지 번호")
    score = Column(Float, default=0.0, comment="유사도 점수")
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), comment="생성 시간"
    )


class RAGChatHistory(Base):
    """RAG 채팅 기록 모델"""

    __tablename__ = "rag_chat_history"

    id = Column(Integer, primary_key=True, index=True)
    pipeline_id = Column(Integer, nullable=False, index=True, comment="파이프라인 ID")
    user_id = Column(Integer, nullable=False, index=True, comment="사용자 ID")
    query = Column(Text, nullable=False, comment="사용자 질문")
    response = Column(Text, nullable=False, comment="AI 응답")
    sources = Column(JSON, comment="출처 정보")
    context_preview = Column(Text, comment="컨텍스트 미리보기")
    model_info = Column(JSON, comment="모델 정보")
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), comment="생성 시간"
    )


class RAGConfig(Base):
    """RAG 설정 모델"""

    __tablename__ = "rag_configs"

    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, nullable=False, index=True, comment="그룹 ID")
    config_name = Column(String(100), nullable=False, comment="설정 이름")
    config_data = Column(JSON, nullable=False, comment="설정 데이터")
    is_active = Column(Boolean, default=True, comment="활성 여부")
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), comment="생성 시간"
    )
    updated_at = Column(
        DateTime(timezone=True), onupdate=func.now(), comment="수정 시간"
    )

    # 설정 타입별 기본값
    DEFAULT_CONFIG = {
        "min_paragraph_length": 30,
        "max_qa_pairs": 100,
        "chunk_size": 500,
        "chunk_overlap": 100,
        "search_top_k": 3,
        "score_threshold": 0.4,
        "max_context_length": 2000,
        "max_tokens": 512,
        "temperature": 0.8,
        "system_message": "당신은 제공된 참고 문서의 정확한 정보와 사실을 바탕으로 답변하는 AI 어시스턴트입니다.",
        "influencer_name": "AI",
    }

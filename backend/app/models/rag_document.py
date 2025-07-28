"""
RAG 문서 모델 (기존 auto_rag 통합)
RAG 시스템에서 사용하는 문서 관련 모델들입니다.
"""

from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, Float, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.models.base import Base


class RAGDocument(Base):
    """RAG 문서 모델"""
    __tablename__ = "rag_documents"
    
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, nullable=False, index=True)
    filename = Column(String(255), nullable=False)
    file_path = Column(String(500), nullable=False)
    file_size = Column(Integer, nullable=False)
    upload_date = Column(DateTime(timezone=True), server_default=func.now())
    processed = Column(Boolean, default=False)
    qa_pairs_count = Column(Integer, default=0)
    processing_status = Column(String(50), default="pending")  # pending, processing, completed, failed
    error_message = Column(Text, nullable=True)
    
    # 메타데이터
    title = Column(String(255), nullable=True)
    author = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    
    # 벡터 스토어 정보
    collection_name = Column(String(255), nullable=True)
    vector_count = Column(Integer, default=0)
    
    # 처리 설정
    max_qa_pairs = Column(Integer, default=100)
    chunk_size = Column(Integer, default=1000)
    chunk_overlap = Column(Integer, default=200)
    
    # 성능 메트릭
    processing_time = Column(Float, nullable=True)  # 초 단위
    embedding_time = Column(Float, nullable=True)  # 초 단위
    total_tokens = Column(Integer, default=0)
    
    def __repr__(self):
        return f"<RAGDocument(id={self.id}, filename='{self.filename}', group_id={self.group_id})>"


class RAGChunk(Base):
    """RAG 청크 모델 (문서의 작은 단위)"""
    __tablename__ = "rag_chunks"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("rag_documents.id"), nullable=False)
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    chunk_type = Column(String(50), default="text")  # text, question, answer
    page_number = Column(Integer, nullable=True)
    
    # 벡터 정보
    embedding_id = Column(String(255), nullable=True)  # 벡터 스토어의 ID
    vector_dimension = Column(Integer, nullable=True)
    
    # 메타데이터
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 관계
    document = relationship("RAGDocument", back_populates="chunks")
    
    def __repr__(self):
        return f"<RAGChunk(id={self.id}, document_id={self.document_id}, chunk_index={self.chunk_index})>"


class RAGQAPair(Base):
    """RAG QA 쌍 모델"""
    __tablename__ = "rag_qa_pairs"
    
    id = Column(Integer, primary_key=True, index=True)
    document_id = Column(Integer, ForeignKey("rag_documents.id"), nullable=False)
    question = Column(Text, nullable=False)
    answer = Column(Text, nullable=False)
    confidence_score = Column(Float, default=0.0)
    page_number = Column(Integer, nullable=True)
    
    # 벡터 정보
    question_embedding_id = Column(String(255), nullable=True)
    answer_embedding_id = Column(String(255), nullable=True)
    
    # 메타데이터
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # 관계
    document = relationship("RAGDocument", back_populates="qa_pairs")
    
    def __repr__(self):
        return f"<RAGQAPair(id={self.id}, document_id={self.document_id})>"


class RAGSearchLog(Base):
    """RAG 검색 로그 모델"""
    __tablename__ = "rag_search_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, nullable=False, index=True)
    query = Column(Text, nullable=False)
    search_results_count = Column(Integer, default=0)
    search_time = Column(Float, nullable=True)  # 초 단위
    search_score = Column(Float, nullable=True)  # 최고 점수
    
    # 사용자 정보
    user_id = Column(Integer, nullable=True)
    session_id = Column(String(255), nullable=True)
    
    # 메타데이터
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    def __repr__(self):
        return f"<RAGSearchLog(id={self.id}, group_id={self.group_id}, query='{self.query[:50]}...')>"


class RAGChatLog(Base):
    """RAG 채팅 로그 모델"""
    __tablename__ = "rag_chat_logs"
    
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, nullable=False, index=True)
    session_id = Column(String(255), nullable=False, index=True)
    
    # 메시지 정보
    user_message = Column(Text, nullable=False)
    ai_response = Column(Text, nullable=False)
    response_time = Column(Float, nullable=True)  # 초 단위
    
    # 컨텍스트 정보
    context_used = Column(Text, nullable=True)
    sources_count = Column(Integer, default=0)
    confidence_score = Column(Float, nullable=True)
    
    # 모델 정보
    model_name = Column(String(255), nullable=True)
    adapter_name = Column(String(255), nullable=True)
    temperature = Column(Float, nullable=True)
    max_tokens = Column(Integer, nullable=True)
    
    # 사용자 정보
    user_id = Column(Integer, nullable=True)
    
    # 메타데이터
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    def __repr__(self):
        return f"<RAGChatLog(id={self.id}, group_id={self.group_id}, session_id='{self.session_id}')>"


class RAGPipeline(Base):
    """RAG 파이프라인 모델"""
    __tablename__ = "rag_pipelines"
    
    id = Column(Integer, primary_key=True, index=True)
    group_id = Column(Integer, nullable=False, index=True)
    pipeline_name = Column(String(255), nullable=False)
    
    # 설정 정보
    lora_adapter = Column(String(255), nullable=True)
    system_message = Column(Text, nullable=True)
    influencer_name = Column(String(255), default="AI")
    temperature = Column(Float, default=0.8)
    max_tokens = Column(Integer, default=512)
    
    # 검색 설정
    search_top_k = Column(Integer, default=3)
    search_threshold = Column(Float, default=0.7)
    
    # 상태 정보
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    
    # 관계
    documents = relationship("RAGDocument", back_populates="pipeline")
    search_logs = relationship("RAGSearchLog", back_populates="pipeline")
    chat_logs = relationship("RAGChatLog", back_populates="pipeline")
    
    def __repr__(self):
        return f"<RAGPipeline(id={self.id}, group_id={self.group_id}, name='{self.pipeline_name}')>"


# 관계 설정
RAGDocument.chunks = relationship("RAGChunk", back_populates="document")
RAGDocument.qa_pairs = relationship("RAGQAPair", back_populates="document")
RAGDocument.pipeline = relationship("RAGPipeline", back_populates="documents")

RAGSearchLog.pipeline = relationship("RAGPipeline", back_populates="search_logs")
RAGChatLog.pipeline = relationship("RAGPipeline", back_populates="chat_logs") 
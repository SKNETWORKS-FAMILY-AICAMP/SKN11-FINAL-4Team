"""
RAG 문서 관리 서비스
"""

import logging
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc
import uuid

from app.models.user import RAGDocument
from app.schemas.rag_document import (
    RAGDocumentCreate,
    RAGDocumentUpdate,
    RAGDocumentList
)

logger = logging.getLogger(__name__)


class RAGDocumentService:
    """RAG 문서 관리 서비스"""
    
    def create_document(self, db: Session, document_data: RAGDocumentCreate) -> RAGDocument:
        """새 RAG 문서 생성"""
        try:
            document = RAGDocument(
                document_id=str(uuid.uuid4()),
                **document_data.dict()
            )
            
            db.add(document)
            db.commit()
            db.refresh(document)
            
            logger.info(f"RAG 문서 생성 완료: {document.document_id} ({document.original_filename})")
            return document
            
        except Exception as e:
            db.rollback()
            logger.error(f"RAG 문서 생성 실패: {e}")
            raise
    
    def get_documents_by_group(self, db: Session, group_id: int, skip: int = 0, limit: int = 100) -> RAGDocumentList:
        """그룹별 RAG 문서 목록 조회"""
        try:
            documents = db.query(RAGDocument).filter(
                RAGDocument.group_id == group_id
            ).order_by(desc(RAGDocument.created_at)).offset(skip).limit(limit).all()
            
            total_count = db.query(RAGDocument).filter(
                RAGDocument.group_id == group_id
            ).count()
            
            return RAGDocumentList(
                documents=documents,
                total_count=total_count
            )
            
        except Exception as e:
            logger.error(f"RAG 문서 목록 조회 실패: {e}")
            raise
    
    def get_document_by_id(self, db: Session, document_id: str) -> Optional[RAGDocument]:
        """문서 ID로 RAG 문서 조회"""
        try:
            return db.query(RAGDocument).filter(
                RAGDocument.document_id == document_id
            ).first()
            
        except Exception as e:
            logger.error(f"RAG 문서 조회 실패: {e}")
            raise
    
    def update_document(self, db: Session, document_id: str, update_data: RAGDocumentUpdate) -> Optional[RAGDocument]:
        """RAG 문서 업데이트"""
        try:
            document = self.get_document_by_id(db, document_id)
            if not document:
                return None
            
            # 업데이트할 필드들만 업데이트
            update_dict = update_data.dict(exclude_unset=True)
            for field, value in update_dict.items():
                setattr(document, field, value)
            
            db.commit()
            db.refresh(document)
            
            logger.info(f"RAG 문서 업데이트 완료: {document_id}")
            return document
            
        except Exception as e:
            db.rollback()
            logger.error(f"RAG 문서 업데이트 실패: {e}")
            raise
    
    def delete_document(self, db: Session, document_id: str) -> bool:
        """RAG 문서 삭제"""
        try:
            document = self.get_document_by_id(db, document_id)
            if not document:
                return False
            
            db.delete(document)
            db.commit()
            
            logger.info(f"RAG 문서 삭제 완료: {document_id}")
            return True
            
        except Exception as e:
            db.rollback()
            logger.error(f"RAG 문서 삭제 실패: {e}")
            raise
    
    def get_documents_summary(self, db: Session, group_id: int) -> Dict[str, Any]:
        """그룹별 문서 요약 정보 조회"""
        try:
            documents = db.query(RAGDocument).filter(
                RAGDocument.group_id == group_id
            ).all()
            
            total_documents = len(documents)
            total_chunks = sum(doc.total_chunks for doc in documents)
            total_qa_pairs = sum(doc.qa_pairs_generated for doc in documents)
            completed_documents = len([doc for doc in documents if doc.status == "completed"])
            
            return {
                "total_documents": total_documents,
                "total_chunks": total_chunks,
                "total_qa_pairs": total_qa_pairs,
                "completed_documents": completed_documents,
                "processing_documents": total_documents - completed_documents
            }
            
        except Exception as e:
            logger.error(f"문서 요약 정보 조회 실패: {e}")
            raise


def get_rag_document_service() -> RAGDocumentService:
    """RAG 문서 서비스 인스턴스 반환"""
    return RAGDocumentService() 
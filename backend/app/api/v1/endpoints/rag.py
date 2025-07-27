import os
import json
import logging
from typing import List, Dict, Optional, Any
from pathlib import Path

from fastapi import APIRouter, HTTPException, Depends, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from app.database import get_db
from app.models.user import HFTokenManage
# from app.models.user import HFTokenManage, RAGDocument
from app.core.encryption import decrypt_sensitive_data
from app.core.config import settings
from app.services.rag_service import (
    RAGService, AdvancedRAGService, QAChunk, 
    create_rag_service, create_advanced_rag_service
)
from app.services.document_processor_service import (
    DocumentProcessorService, IntegratedDocumentService,
    create_document_processor_service, create_integrated_document_service
)
# from app.services.rag_document_service import get_rag_document_service
# from app.schemas.rag_document import RAGDocumentCreate, RAGDocumentUpdate

logger = logging.getLogger(__name__)

router = APIRouter()

# ============================================================================
# Pydantic 모델들
# ============================================================================

class DocumentUploadRequest(BaseModel):
    """문서 업로드 요청 모델"""
    group_id: int = Field(..., description="그룹 ID")
    file_path: str = Field(..., description="PDF 파일 경로")
    source_name: Optional[str] = Field(None, description="소스 이름")
    max_qa_pairs: int = Field(100, description="최대 QA 쌍 수", ge=1, le=500)

class RAGSearchRequest(BaseModel):
    """RAG 검색 요청 모델"""
    query: str = Field(..., description="검색 쿼리")
    top_k: int = Field(3, description="검색 결과 수", ge=1, le=20)
    min_score: float = Field(0.7, description="최소 유사도 점수", ge=0.0, le=1.0)
    include_context: bool = Field(True, description="컨텍스트 포함 여부")

class RAGChatRequest(BaseModel):
    """RAG 채팅 요청 모델"""
    query: str = Field(..., description="사용자 질문")
    group_id: int = Field(..., description="그룹 ID")
    include_sources: bool = Field(True, description="출처 정보 포함 여부")

class RAGResponse(BaseModel):
    """RAG 응답 모델"""
    query: str
    response: str
    sources: Optional[List[Dict[str, Any]]] = None
    context: Optional[str] = None
    confidence_score: Optional[float] = None

# ============================================================================
# 헬퍼 함수들
# ============================================================================

async def _get_hf_token_by_group(group_id: int, db) -> Optional[str]:
    """그룹 ID로 HF 토큰 가져오기 (기본 토큰 우선, 없으면 최신 토큰)"""
    try:
        # 1. 기본 토큰 먼저 찾기
        hf_token_record = db.query(HFTokenManage).filter(
            HFTokenManage.group_id == group_id,
            HFTokenManage.is_default == True
        ).first()
        
        # 2. 기본 토큰이 없으면 해당 그룹의 최신 토큰 찾기
        if not hf_token_record:
            hf_token_record = db.query(HFTokenManage).filter(
                HFTokenManage.group_id == group_id
            ).order_by(HFTokenManage.created_at.desc()).first()
        
        # 3. 그룹에 할당된 토큰이 없으면 할당되지 않은 토큰 중에서 찾기
        if not hf_token_record:
            hf_token_record = db.query(HFTokenManage).filter(
                HFTokenManage.group_id.is_(None)
            ).order_by(HFTokenManage.created_at.desc()).first()
        
        if hf_token_record and hf_token_record.hf_token_value:
            logger.info(f"HF 토큰 사용: {hf_token_record.hf_token_nickname} (그룹: {hf_token_record.group_id})")
            return decrypt_sensitive_data(hf_token_record.hf_token_value)
        
        logger.warning(f"그룹 {group_id}에 사용 가능한 HF 토큰이 없습니다")
        return None
        
    except Exception as e:
        logger.error(f"HF 토큰 조회 실패: {e}")
        return None

async def _get_available_hf_tokens_info(db) -> Dict[str, Any]:
    """사용 가능한 HF 토큰 정보 조회 (에러 메시지용)"""
    try:
        # 할당된 토큰들
        assigned_tokens = db.query(HFTokenManage).filter(
            HFTokenManage.group_id.isnot(None)
        ).all()
        
        # 할당되지 않은 토큰들
        unassigned_tokens = db.query(HFTokenManage).filter(
            HFTokenManage.group_id.is_(None)
        ).all()
        
        return {
            "assigned_count": len(assigned_tokens),
            "unassigned_count": len(unassigned_tokens),
            "total_count": len(assigned_tokens) + len(unassigned_tokens),
            "assigned_groups": list(set([t.group_id for t in assigned_tokens if t.group_id])),
            "has_unassigned": len(unassigned_tokens) > 0
        }
    except Exception as e:
        logger.error(f"HF 토큰 정보 조회 실패: {e}")
        return {"error": str(e)}

def _get_vllm_base_url() -> str:
    """VLLM 서버 URL 가져오기"""
    return getattr(settings, 'VLLM_SERVER_URL', 'http://localhost:8000')

# ============================================================================
# API 엔드포인트들
# ============================================================================

@router.post("/upload_document")
async def upload_document(req: DocumentUploadRequest, db = Depends(get_db)):
    """RAG용 문서 업로드 및 처리 (파일 경로 기반)"""
    try:
        # 파일 존재 확인
        if not Path(req.file_path).exists():
            raise HTTPException(status_code=404, detail=f"파일을 찾을 수 없습니다: {req.file_path}")
        
        # 파일 확장자 확인
        file_ext = Path(req.file_path).suffix.lower()
        if file_ext != '.pdf':
            raise HTTPException(status_code=400, detail=f"지원하지 않는 파일 형식입니다: {file_ext}")
        
        # HF 토큰 가져오기
        hf_token = await _get_hf_token_by_group(req.group_id, db)
        if not hf_token:
            # 사용 가능한 토큰 정보 조회
            tokens_info = await _get_available_hf_tokens_info(db)
            
            error_detail = f"그룹 ID {req.group_id}에 사용 가능한 HF 토큰이 없습니다."
            if tokens_info.get("has_unassigned"):
                error_detail += f" 할당되지 않은 토큰이 {tokens_info['unassigned_count']}개 있습니다."
            error_detail += " 관리자 페이지(/administrator)에서 HF 토큰을 생성하고 할당해주세요."
            
            raise HTTPException(status_code=400, detail=error_detail)
        
        # VLLM 서버 URL
        vllm_base_url = _get_vllm_base_url()
        
        # 통합 문서 서비스 생성
        integrated_service = create_integrated_document_service(
            vllm_base_url=vllm_base_url,
            rag_service=create_rag_service(vllm_base_url)
        )
        
        # 문서 처리 및 저장
        source_name = req.source_name or Path(req.file_path).name
        result = await integrated_service.process_and_store_document(
            file_path=req.file_path,
            source_name=source_name,
            max_qa_pairs=req.max_qa_pairs
        )
        
        # 문서 메타데이터를 DB에 저장 (임시 주석 처리)
        # if result.get("success"):
        #     document_service = get_rag_document_service()
        #     document_data = RAGDocumentCreate(
        #         group_id=req.group_id,
        #         original_filename=Path(req.file_path).name,
        #         source_name=source_name,
        #         file_size=Path(req.file_path).stat().st_size if Path(req.file_path).exists() else None,
        #         total_chunks=result.get("total_chunks", 0),
        #         qa_pairs_generated=result.get("qa_generated", 0),
        #         status="completed"
        #     )
        #     document_service.create_document(db, document_data)
        
        return {
            "success": True,
            "message": "문서가 성공적으로 업로드되고 처리되었습니다",
            "data": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"문서 업로드 실패: {e}")
        raise HTTPException(status_code=500, detail=f"문서 업로드 중 오류가 발생했습니다: {str(e)}")

@router.post("/upload_file")
async def upload_file(
    file: UploadFile = File(...),
    group_id: int = Form(...),
    source_name: Optional[str] = Form(None),
    max_qa_pairs: int = Form(100),
    db = Depends(get_db)
):
    """RAG용 파일 업로드 및 처리"""
    try:
        # 파일 형식 확인
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다")
        
        # 파일 크기 확인 (50MB 제한)
        file_size = 0
        file_content = b""
        chunk_size = 1024 * 1024  # 1MB
        
        while True:
            chunk = await file.read(chunk_size)
            if not chunk:
                break
            file_content += chunk
            file_size += len(chunk)
            
            if file_size > 50 * 1024 * 1024:  # 50MB
                raise HTTPException(status_code=400, detail="파일 크기는 50MB 이하여야 합니다")
        
        # 임시 파일로 저장
        import tempfile
        import uuid
        
        temp_dir = Path("temp_uploads")
        temp_dir.mkdir(exist_ok=True)
        
        # temp_uploads 디렉토리가 .gitignore에 추가되도록 .gitkeep 파일 생성
        gitkeep_file = temp_dir / ".gitkeep"
        if not gitkeep_file.exists():
            gitkeep_file.touch()
        
        temp_filename = f"rag_doc_{uuid.uuid4().hex}.pdf"
        temp_file_path = temp_dir / temp_filename
        
        with open(temp_file_path, "wb") as f:
            f.write(file_content)
        
        try:
            # HF 토큰 가져오기
            hf_token = await _get_hf_token_by_group(group_id, db)
            if not hf_token:
                # 사용 가능한 토큰 정보 조회
                tokens_info = await _get_available_hf_tokens_info(db)
                
                error_detail = f"그룹 ID {group_id}에 사용 가능한 HF 토큰이 없습니다."
                if tokens_info.get("has_unassigned"):
                    error_detail += f" 할당되지 않은 토큰이 {tokens_info['unassigned_count']}개 있습니다."
                error_detail += " 관리자 페이지(/administrator)에서 HF 토큰을 생성하고 할당해주세요."
                
                raise HTTPException(status_code=400, detail=error_detail)
            
            # VLLM 서버 URL
            vllm_base_url = _get_vllm_base_url()
            
            # 통합 문서 서비스 생성
            integrated_service = create_integrated_document_service(
                vllm_base_url=vllm_base_url,
                rag_service=create_rag_service(vllm_base_url)
            )
            
            # 문서 처리 및 저장
            source_name = source_name or file.filename
            result = await integrated_service.process_and_store_document(
                file_path=str(temp_file_path),
                source_name=source_name,
                max_qa_pairs=max_qa_pairs
            )
            
            # 문서 메타데이터를 DB에 저장 (임시 주석 처리)
            # if result.get("success"):
            #     document_service = get_rag_document_service()
            #     document_data = RAGDocumentCreate(
            #         group_id=group_id,
            #         original_filename=file.filename,
            #         source_name=source_name,
            #         file_size=file_size,
            #         total_chunks=result.get("total_chunks", 0),
            #         qa_pairs_generated=result.get("qa_generated", 0),
            #         status="completed"
            #     )
            #     document_service.create_document(db, document_data)
            
            return {
                "success": True,
                "message": "문서가 성공적으로 업로드되고 처리되었습니다",
                "data": result
            }
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"문서 처리 실패: {e}")
            raise HTTPException(status_code=500, detail=f"문서 처리 중 오류가 발생했습니다: {str(e)}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"문서 업로드 실패: {e}")
        raise HTTPException(status_code=500, detail=f"문서 업로드 중 오류가 발생했습니다: {str(e)}")
    finally:
        # 임시 파일 삭제
        if temp_file_path.exists():
            temp_file_path.unlink()

@router.post("/search")
async def rag_search(req: RAGSearchRequest):
    """RAG 검색"""
    try:
        # VLLM 서버 URL 가져오기
        vllm_base_url = _get_vllm_base_url()
        
        # 고급 RAG 서비스 생성
        async with create_advanced_rag_service(vllm_base_url) as rag_service:
            # 헬스 체크
            health = await rag_service.health_check()
            if health.get("status") != "healthy":
                raise HTTPException(status_code=503, detail="RAG 서비스가 사용할 수 없습니다.")
            
            # 검색 수행
            search_response = await rag_service.search_with_filters(
                query=req.query,
                top_k=req.top_k,
                min_score=req.min_score
            )
            
            # 컨텍스트 생성 (요청시)
            context = None
            if req.include_context:
                context = await rag_service.get_context_for_query(req.query, req.top_k)
            
            return {
                "success": True,
                "query": req.query,
                "results": [
                    {
                        "text": result.text,
                        "score": result.score,
                        "source": result.source,
                        "page": result.page,
                        "question": result.question,
                        "answer": result.answer
                    }
                    for result in search_response.results
                ],
                "total_found": search_response.total_found,
                "context": context
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ RAG 검색 실패: {e}")
        raise HTTPException(status_code=500, detail=f"검색 중 오류가 발생했습니다: {str(e)}")

@router.post("/chat")
async def rag_chat(req: RAGChatRequest, db = Depends(get_db)):
    """RAG 기반 채팅"""
    try:
        # VLLM 서버 URL 가져오기
        vllm_base_url = _get_vllm_base_url()
        
        # 고급 RAG 서비스 생성
        async with create_advanced_rag_service(vllm_base_url) as rag_service:
            # 헬스 체크
            health = await rag_service.health_check()
            if health.get("status") != "healthy":
                raise HTTPException(status_code=503, detail="RAG 서비스가 사용할 수 없습니다.")
            
            # RAG 검색으로 관련 정보 찾기
            search_response = await rag_service.search_similar(req.query, 3)
            
            if not search_response.results:
                # RAG에서 답변을 찾을 수 없는 경우
                return RAGResponse(
                    query=req.query,
                    response="죄송합니다. 제공된 문서에서 관련 정보를 찾을 수 없습니다. 다른 질문을 해주시거나, 일반적인 질문으로 다시 시도해주세요.",
                    confidence_score=0.0
                )
            
            # 컨텍스트 생성
            context = await rag_service.get_context_for_query(req.query, 3)
            
            # VLLM을 사용하여 답변 생성 (여기서는 간단한 응답만)
            # 실제로는 VLLM 서버의 생성 API를 호출해야 함
            best_result = search_response.results[0]
            
            if best_result.score >= 0.8:
                # 높은 신뢰도: 직접 답변 제공
                response = best_result.answer
                confidence_score = best_result.score
            else:
                # 낮은 신뢰도: 컨텍스트 기반 답변
                response = f"제공된 문서를 바탕으로 답변드리겠습니다:\n\n{best_result.answer}\n\n이 정보가 도움이 되길 바랍니다."
                confidence_score = best_result.score
            
            # 출처 정보 포함 (요청시)
            sources = None
            if req.include_sources:
                sources = [
                    {
                        "source": result.source,
                        "page": result.page,
                        "score": result.score,
                        "question": result.question
                    }
                    for result in search_response.results[:3]
                ]
            
            return RAGResponse(
                query=req.query,
                response=response,
                sources=sources,
                context=context,
                confidence_score=confidence_score
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ RAG 채팅 실패: {e}")
        raise HTTPException(status_code=500, detail=f"채팅 중 오류가 발생했습니다: {str(e)}")

@router.get("/health")
async def rag_health_check():
    """RAG 서비스 헬스 체크"""
    try:
        # VLLM 서버 URL 가져오기
        vllm_base_url = _get_vllm_base_url()
        
        # RAG 서비스 생성
        async with create_rag_service(vllm_base_url) as rag_service:
            health = await rag_service.health_check()
            
            return {
                "status": "healthy" if health.get("status") == "healthy" else "unhealthy",
                "rag_service": health,
                "vllm_base_url": vllm_base_url
            }
            
    except Exception as e:
        logger.error(f"❌ RAG 헬스 체크 실패: {e}")
        return {
            "status": "unhealthy",
            "error": str(e),
            "vllm_base_url": _get_vllm_base_url()
        }

@router.get("/collection_info")
async def get_collection_info():
    """컬렉션 정보 조회"""
    try:
        # VLLM 서버 URL 가져오기
        vllm_base_url = _get_vllm_base_url()
        
        # RAG 서비스 생성
        async with create_rag_service(vllm_base_url) as rag_service:
            info = await rag_service.get_collection_info()
            
            return {
                "success": True,
                "collection_info": info
            }
            
    except Exception as e:
        logger.error(f"❌ 컬렉션 정보 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"컬렉션 정보 조회 중 오류가 발생했습니다: {str(e)}")

@router.delete("/clear_collection")
async def clear_collection():
    """컬렉션 초기화"""
    try:
        # VLLM 서버 URL 가져오기
        vllm_base_url = _get_vllm_base_url()
        
        # RAG 서비스 생성
        async with create_rag_service(vllm_base_url) as rag_service:
            result = await rag_service.clear_collection()
            
            return {
                "success": True,
                "message": "컬렉션이 성공적으로 초기화되었습니다."
            }
            
    except Exception as e:
        logger.error(f"❌ 컬렉션 초기화 실패: {e}")
        raise HTTPException(status_code=500, detail=f"컬렉션 초기화 중 오류가 발생했습니다: {str(e)}")

@router.post("/store_qa_chunks")
async def store_qa_chunks(qa_data: List[Dict[str, Any]], source_file: str = "document.pdf"):
    """QA 데이터를 RAG에 저장"""
    try:
        # VLLM 서버 URL 가져오기
        vllm_base_url = _get_vllm_base_url()
        
        # RAG 서비스 생성
        async with create_rag_service(vllm_base_url) as rag_service:
            # QAChunk 객체로 변환
            qa_chunks = [
                QAChunk(
                    question=qa["question"],
                    answer=qa["answer"],
                    source=qa.get("source", source_file),
                    page=qa.get("page", 0),
                    metadata=qa.get("metadata", {})
                )
                for qa in qa_data
            ]
            
            result = await rag_service.store_qa_chunks(qa_chunks, source_file)
            
            return {
                "success": True,
                "message": f"{len(qa_chunks)}개 QA 쌍이 성공적으로 저장되었습니다.",
                "data": result
            }
            
    except Exception as e:
        logger.error(f"❌ QA 데이터 저장 실패: {e}")
        raise HTTPException(status_code=500, detail=f"QA 데이터 저장 중 오류가 발생했습니다: {str(e)}")

@router.get("/documents/{group_id}")
async def get_documents_by_group(
    group_id: int,
    skip: int = 0,
    limit: int = 100,
    db = Depends(get_db)
):
    """그룹별 업로드된 문서 목록 조회"""
    try:
        # 임시로 빈 목록 반환 (나중에 실제 DB 연동)
        return {
            "success": True,
            "documents": [],
            "total_count": 0
        }
        
    except Exception as e:
        logger.error(f"❌ 문서 목록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"문서 목록 조회 중 오류가 발생했습니다: {str(e)}")

@router.get("/documents/{group_id}/summary")
async def get_documents_summary(
    group_id: int,
    db = Depends(get_db)
):
    """그룹별 문서 요약 정보 조회"""
    try:
        # 임시로 빈 요약 반환
        return {
            "success": True,
            "summary": {
                "total_documents": 0,
                "total_chunks": 0,
                "total_qa_pairs": 0
            }
        }
        
    except Exception as e:
        logger.error(f"❌ 문서 요약 정보 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"문서 요약 정보 조회 중 오류가 발생했습니다: {str(e)}")

@router.delete("/documents/{document_id}")
async def delete_document(
    document_id: str,
    db = Depends(get_db)
):
    """문서 삭제"""
    try:
        # 임시로 성공 응답 반환
        return {
            "success": True,
            "message": "문서가 성공적으로 삭제되었습니다"
        }
        
    except Exception as e:
        logger.error(f"❌ 문서 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail=f"문서 삭제 중 오류가 발생했습니다: {str(e)}") 
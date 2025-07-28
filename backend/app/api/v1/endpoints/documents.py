"""
DOCUMENTS 테이블 API 엔드포인트
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query, File, UploadFile, Form
from pydantic import BaseModel
from sqlalchemy.orm import Session
from sqlalchemy import select
import logging
import tempfile
import os
from datetime import datetime

from app.database import get_db
from app.models.rag import Documents
from app.services.rag_document_service import get_rag_document_service

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== Response Models ====================


class DocumentResponse(BaseModel):
    """문서 응답 모델"""
    
    documents_id: str
    documents_name: str
    file_size: Optional[int]
    s3_url: str
    is_vectorized: int
    created_at: Optional[str]


class DocumentListResponse(BaseModel):
    """문서 목록 응답 모델"""
    
    documents: List[DocumentResponse]
    total_count: int


class DocumentUploadResponse(BaseModel):
    """문서 업로드 응답 모델"""
    
    success: bool
    message: str
    documents_id: Optional[str] = None
    s3_url: Optional[str] = None
    file_size: Optional[int] = None


class VectorizationUpdateResponse(BaseModel):
    """벡터화 상태 업데이트 응답 모델"""
    
    success: bool
    message: str
    documents_id: str
    is_vectorized: int


class S3FileInfo(BaseModel):
    """S3 파일 정보 모델"""
    
    key: str
    filename: str
    size: int
    last_modified: str
    presigned_url: Optional[str] = None


class S3FileListResponse(BaseModel):
    """S3 파일 목록 응답 모델"""
    
    files: List[S3FileInfo]
    total_count: int


# ==================== Document Endpoints ====================


@router.post("/upload", response_model=DocumentUploadResponse)
async def upload_document(
    file: UploadFile = File(..., description="PDF 파일"),
    db: Session = Depends(get_db)
):
    """PDF 문서를 S3에 업로드하고 데이터베이스에 저장"""
    try:
        logger.info(f"📥 문서 업로드 시작: {file.filename}")

        # 파일 검증
        if not file.filename.lower().endswith(".pdf"):
            raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")

        if file.size > 10 * 1024 * 1024:  # 10MB 제한
            raise HTTPException(
                status_code=400, detail="파일 크기는 10MB를 초과할 수 없습니다."
            )

        logger.info(f"✅ 파일 검증 통과: {file.filename} ({file.size} bytes)")

        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
            logger.info(f"📁 임시 파일 저장: {temp_file_path}")

        try:
            # S3에 PDF 파일 업로드
            s3_url = None
            try:
                from app.services.s3_service import get_s3_service
                s3_service = get_s3_service()
                
                if s3_service.is_available():
                    # S3 키 생성 (documents/YYYY-MM-DD/HH-MM-SS_filename.pdf)
                    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                    s3_key = f"documents/{timestamp}/{file.filename}"
                    
                    # S3에 업로드
                    s3_url = s3_service.upload_file(
                        temp_file_path,
                        s3_key,
                        content_type="application/pdf"
                    )
                    
                    if s3_url:
                        logger.info(f"✅ S3 업로드 성공: {s3_url}")
                    else:
                        logger.warning("⚠️ S3 업로드 실패")
                        raise HTTPException(
                            status_code=500, detail="S3 업로드에 실패했습니다."
                        )
                else:
                    logger.warning("⚠️ S3 서비스를 사용할 수 없습니다")
                    raise HTTPException(
                        status_code=500, detail="S3 서비스를 사용할 수 없습니다."
                    )
            except Exception as s3_error:
                logger.error(f"❌ S3 업로드 중 오류: {s3_error}")
                raise HTTPException(
                    status_code=500, detail=f"S3 업로드 실패: {str(s3_error)}"
                )

            # 데이터베이스에 문서 정보 저장
            rag_document_service = get_rag_document_service()
            documents_id = rag_document_service.save_document_info(
                documents_name=file.filename,
                file_size=file.size,
                s3_url=s3_url,
                db=db
            )
            
            if documents_id:
                logger.info(f"✅ 문서 정보 저장 완료: {documents_id}")
                return DocumentUploadResponse(
                    success=True,
                    message="문서가 성공적으로 업로드되고 저장되었습니다.",
                    documents_id=documents_id,
                    s3_url=s3_url,
                    file_size=file.size
                )
            else:
                logger.error("❌ 문서 정보 저장 실패")
                raise HTTPException(
                    status_code=500, detail="데이터베이스 저장에 실패했습니다."
                )

        finally:
            # 임시 파일 정리
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                logger.info(f"🗑️ 임시 파일 삭제: {temp_file_path}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 문서 업로드 실패: {e}")
        raise HTTPException(status_code=500, detail=f"문서 업로드 실패: {str(e)}")


@router.put("/{documents_id}/vectorization", response_model=VectorizationUpdateResponse)
async def update_vectorization_status(
    documents_id: str,
    is_vectorized: int = Form(1, description="벡터화 상태 (1: 완료, 0: 미완료)"),
    db: Session = Depends(get_db)
):
    """문서의 벡터화 상태 업데이트"""
    try:
        rag_document_service = get_rag_document_service()
        
        success = rag_document_service.update_vectorization_status(
            documents_id=documents_id,
            db=db,
            is_vectorized=is_vectorized
        )
        
        if success:
            status_text = "완료" if is_vectorized == 1 else "미완료"
            return VectorizationUpdateResponse(
                success=True,
                message=f"벡터화 상태가 '{status_text}'로 업데이트되었습니다.",
                documents_id=documents_id,
                is_vectorized=is_vectorized
            )
        else:
            raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"벡터화 상태 업데이트 실패: {e}")
        raise HTTPException(status_code=500, detail=f"벡터화 상태 업데이트 실패: {str(e)}")


@router.get("/vectorized", response_model=DocumentListResponse)
async def get_vectorized_documents(
    limit: int = Query(50, description="조회 제한 수"),
    offset: int = Query(0, description="조회 시작 위치"),
    db: Session = Depends(get_db)
):
    """벡터화된 문서 목록 조회"""
    try:
        rag_document_service = get_rag_document_service()
        
        # 벡터화된 문서만 조회 (is_vectorized = 1)
        documents = rag_document_service.get_vectorized_documents(
            db=db,
            limit=limit,
            offset=offset
        )
        
        return DocumentListResponse(
            documents=documents,
            total_count=len(documents)
        )
        
    except Exception as e:
        logger.error(f"벡터화된 문서 목록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"벡터화된 문서 목록 조회 실패: {str(e)}")


@router.get("/{documents_id}/download")
async def download_document(
    documents_id: str,
    db: Session = Depends(get_db)
):
    """문서 다운로드 (Presigned URL 반환)"""
    try:
        rag_document_service = get_rag_document_service()
        document = await rag_document_service.get_document_by_id(
            documents_id=documents_id,
            db=db
        )
        
        if not document:
            raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
        
        # S3에서 presigned URL 생성
        try:
            from app.services.s3_service import get_s3_service
            s3_service = get_s3_service()
            
            if s3_service.is_available():
                # S3 키 추출 (URL에서 키 부분만)
                s3_url = document['s3_url']
                s3_key = s3_url.split('.com/')[-1] if '.com/' in s3_url else s3_url
                
                # Presigned URL 생성 (24시간 유효)
                presigned_url = s3_service.generate_presigned_url(s3_key, expiration=86400)
                
                if presigned_url:
                    return {
                        "success": True,
                        "download_url": presigned_url,
                        "filename": document['documents_name'],
                        "expires_in": 86400
                    }
                else:
                    raise HTTPException(status_code=500, detail="다운로드 URL 생성에 실패했습니다.")
            else:
                raise HTTPException(status_code=500, detail="S3 서비스를 사용할 수 없습니다.")
                
        except Exception as s3_error:
            logger.error(f"S3 다운로드 URL 생성 실패: {s3_error}")
            raise HTTPException(status_code=500, detail=f"다운로드 URL 생성 실패: {str(s3_error)}")
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"문서 다운로드 실패: {e}")
        raise HTTPException(status_code=500, detail=f"문서 다운로드 실패: {str(e)}")


@router.get("/s3", response_model=S3FileListResponse)
async def list_s3_documents(
    prefix: str = Query("documents/", description="S3 파일 경로 접두사"),
    include_presigned: bool = Query(True, description="Presigned URL 포함 여부"),
    db: Session = Depends(get_db)
):
    """S3에서 문서 파일 목록 조회"""
    try:
        from app.services.s3_service import get_s3_service
        s3_service = get_s3_service()
        
        if not s3_service.is_available():
            raise HTTPException(status_code=500, detail="S3 서비스를 사용할 수 없습니다.")
        
        # S3에서 파일 목록 조회
        if include_presigned:
            s3_files = s3_service.list_files_with_presigned_urls(prefix=prefix)
        else:
            s3_keys = s3_service.list_files(prefix=prefix)
            s3_files = []
            for key in s3_keys:
                # 파일명 추출
                filename = key.split('/')[-1]
                # 기본 정보만 포함
                s3_files.append({
                    'key': key,
                    'filename': filename,
                    'size': 0,  # 크기 정보는 별도 조회 필요
                    'last_modified': '',
                    'presigned_url': None
                })
        
        # PDF 파일만 필터링
        pdf_files = [
            file for file in s3_files 
            if file['filename'].lower().endswith('.pdf')
        ]
        
        return S3FileListResponse(
            files=pdf_files,
            total_count=len(pdf_files)
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"S3 문서 목록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"S3 문서 목록 조회 실패: {str(e)}")


@router.get("", response_model=DocumentListResponse)
async def get_documents(
    limit: int = Query(50, description="조회 제한 수"),
    offset: int = Query(0, description="조회 시작 위치"),
    db: Session = Depends(get_db)
):
    """문서 목록 조회"""
    try:
        rag_document_service = get_rag_document_service()
        
        # All documents lookup
        documents = await rag_document_service.get_all_documents(
            db=db,
            limit=limit,
            offset=offset
        )
        
        return DocumentListResponse(
            documents=documents,
            total_count=len(documents)
        )
        
    except Exception as e:
        logger.error(f"문서 목록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"문서 목록 조회 실패: {str(e)}")


@router.get("/{documents_id}", response_model=DocumentResponse)
async def get_document(
    documents_id: str,
    db: Session = Depends(get_db)
):
    """특정 문서 조회"""
    try:
        rag_document_service = get_rag_document_service()
        document = await rag_document_service.get_document_by_id(
            documents_id=documents_id,
            db=db
        )
        
        if not document:
            raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
        
        return DocumentResponse(**document)
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"문서 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"문서 조회 실패: {str(e)}")


@router.delete("/{documents_id}")
async def delete_document(
    documents_id: str,
    delete_from_s3: bool = Query(False, description="S3에서도 삭제할지 여부"),
    db: Session = Depends(get_db)
):
    """문서 삭제"""
    try:
        rag_document_service = get_rag_document_service()
        success = await rag_document_service.delete_document(
            documents_id=documents_id,
            db=db,
            delete_from_s3=delete_from_s3
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="문서를 찾을 수 없습니다.")
        
        return {"message": "문서가 성공적으로 삭제되었습니다."}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"문서 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail=f"문서 삭제 실패: {str(e)}")


@router.get("/stats")
async def get_document_stats(
    db: Session = Depends(get_db)
):
    """문서 통계 조회"""
    try:
        rag_document_service = get_rag_document_service()
        stats = await rag_document_service.get_all_document_stats(db=db)
        return stats
        
    except Exception as e:
        logger.error(f"문서 통계 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"문서 통계 조회 실패: {str(e)}") 
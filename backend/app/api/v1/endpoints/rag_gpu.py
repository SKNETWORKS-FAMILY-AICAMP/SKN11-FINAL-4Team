"""
VLLM GPU 벡터 검색 기반 RAG API
CUDA 기반 고성능 벡터 검색 기능 제공
"""

import logging
import tempfile
import os
from typing import List, Dict, Optional
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session

from app.database import get_db
from app.services.rag_service import RAGService, RAGConfig
from app.services.vllm_vector_client import (
    store_qa_chunks_to_vllm, 
    search_similar_from_vllm,
    get_vllm_vector_stats,
    clear_vllm_vector_store,
    check_vllm_vector_health
)

logger = logging.getLogger(__name__)
router = APIRouter()


class DocumentUploadResponse(BaseModel):
    """문서 업로드 응답"""
    success: bool
    message: str
    qa_pairs_count: int
    source_file: str


class ChatResponse(BaseModel):
    """채팅 응답"""
    response: str
    sources: List[Dict]
    query: str
    search_results: List[Dict]


class VectorStatsResponse(BaseModel):
    """벡터 통계 응답"""
    stats: Dict
    health: Dict


@router.post("/upload_document_gpu", response_model=DocumentUploadResponse)
async def upload_document_gpu(
    file: UploadFile = File(..., description="PDF 파일"),
    group_id: int = Form(..., description="그룹 ID"),
    system_message: Optional[str] = Form(
        "당신은 제공된 참고 문서의 정확한 정보와 사실을 바탕으로 답변하는 AI 어시스턴트입니다.",
        description="시스템 메시지"
    ),
    influencer_name: Optional[str] = Form("AI", description="AI 캐릭터 이름"),
    db: Session = Depends(get_db)
):
    """PDF 문서를 VLLM GPU 벡터 스토어에 업로드"""
    try:
        # 파일 검증
        if not file.filename.lower().endswith('.pdf'):
            raise HTTPException(status_code=400, detail="PDF 파일만 업로드 가능합니다.")
        
        if file.size > 10 * 1024 * 1024:  # 10MB 제한
            raise HTTPException(status_code=400, detail="파일 크기는 10MB를 초과할 수 없습니다.")
        
        # 임시 파일로 저장
        with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        
        try:
            # RAG 서비스로 문서 처리
            rag_service = RAGService()
            qa_pairs = await rag_service.document_processor.process_pdf(temp_file_path)
            
            if not qa_pairs:
                raise HTTPException(status_code=500, detail="QA 쌍 생성에 실패했습니다.")
            
            # VLLM GPU 벡터 스토어에 저장
            source_file = file.filename
            success = await store_qa_chunks_to_vllm(qa_pairs, source_file)
            
            if not success:
                raise HTTPException(status_code=500, detail="VLLM GPU 벡터 스토어 저장에 실패했습니다.")
            
            # 파이프라인 정보 저장 (선택사항)
            # await rag_service.create_pipeline(group_id, temp_file_path, system_message, influencer_name)
            
            return DocumentUploadResponse(
                success=True,
                message=f"문서가 VLLM GPU 벡터 스토어에 성공적으로 업로드되었습니다.",
                qa_pairs_count=len(qa_pairs),
                source_file=source_file
            )
            
        finally:
            # 임시 파일 정리
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ GPU 문서 업로드 실패: {e}")
        raise HTTPException(status_code=500, detail=f"문서 업로드 실패: {str(e)}")


@router.post("/chat_gpu", response_model=ChatResponse)
async def chat_gpu(
    query: str,
    top_k: int = 5,
    similarity_threshold: float = 0.5,
    include_sources: bool = True
):
    """VLLM GPU 벡터 검색을 사용한 채팅"""
    try:
        logger.info(f"🔍 GPU 벡터 검색 시작: '{query}'")
        
        # VLLM GPU 벡터 검색
        search_results = await search_similar_from_vllm(
            query=query,
            top_k=top_k,
            similarity_threshold=similarity_threshold
        )
        
        if not search_results:
            return ChatResponse(
                response="죄송합니다. 관련된 정보를 찾을 수 없습니다.",
                sources=[],
                query=query,
                search_results=[]
            )
        
        # 컨텍스트 구성
        context_parts = []
        sources = []
        
        for result in search_results:
            context_parts.append(result.text)
            if include_sources:
                sources.append({
                    "text": result.text,
                    "score": result.similarity,
                    "type": result.metadata.get("type", "unknown"),
                    "chunk_id": result.chunk_id,
                    "metadata": result.metadata
                })
        
        context = "\n\n".join(context_parts)
        
        # VLLM 서버에서 응답 생성
        from app.services.vllm_client import get_vllm_client
        
        vllm_client = await get_vllm_client()
        system_message = (
            "당신은 제공된 참고 문서의 정확한 정보와 사실을 바탕으로 답변하는 AI 어시스턴트입니다. "
            "**중요**: 문서에 포함된 모든 내용은 절대 요약하거나 생략하지 말고, 원문 그대로 완전히 포함해야 합니다. "
            "참고 문서:\n" + context
        )
        
        response = await vllm_client.generate_response(
            user_message=query,
            system_message=system_message,
            influencer_name="AI",
            max_new_tokens=512,
            temperature=0.8
        )
        
        response_text = response.get("response", "죄송합니다. 응답을 생성할 수 없습니다.")
        
        return ChatResponse(
            response=response_text,
            sources=sources,
            query=query,
            search_results=search_results
        )
        
    except Exception as e:
        logger.error(f"❌ GPU 채팅 실패: {e}")
        raise HTTPException(status_code=500, detail=f"채팅 실패: {str(e)}")


@router.get("/vector_stats", response_model=VectorStatsResponse)
async def get_vector_stats():
    """VLLM 벡터 스토어 통계 및 상태 확인"""
    try:
        # 벡터 스토어 통계
        stats = await get_vllm_vector_stats()
        
        # 벡터 서비스 상태
        health = await check_vllm_vector_health()
        
        return VectorStatsResponse(
            stats=stats,
            health=health
        )
        
    except Exception as e:
        logger.error(f"❌ 벡터 통계 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"통계 조회 실패: {str(e)}")


@router.delete("/clear_vector_store")
async def clear_vector_store():
    """VLLM 벡터 스토어 정리"""
    try:
        success = await clear_vllm_vector_store()
        
        if success:
            return {"success": True, "message": "VLLM 벡터 스토어가 정리되었습니다."}
        else:
            raise HTTPException(status_code=500, detail="벡터 스토어 정리 실패")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 벡터 스토어 정리 실패: {e}")
        raise HTTPException(status_code=500, detail=f"벡터 스토어 정리 실패: {str(e)}")


@router.get("/health_gpu")
async def health_check_gpu():
    """VLLM GPU 벡터 검색 서비스 상태 확인"""
    try:
        health = await check_vllm_vector_health()
        return health
        
    except Exception as e:
        logger.error(f"❌ GPU 벡터 서비스 상태 확인 실패: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        } 
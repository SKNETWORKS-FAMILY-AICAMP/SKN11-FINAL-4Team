"""
RAG (Retrieval-Augmented Generation) API 엔드포인트
VLLM GPU 메모리 기반 통합 RAG API
"""

from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
import tempfile
import os
import logging
from datetime import datetime

from app.core.config import settings
from app.database import get_db
from app.services.rag_service import get_rag_service
from app.services.rag_processor import process_with_rag

logger = logging.getLogger(__name__)

router = APIRouter()


# ==================== Response Models ====================


class DocumentUploadResponse(BaseModel):
    """문서 업로드 응답 모델"""

    status: str
    message: str
    pipeline_info: Optional[Dict] = None


class ChatRequest(BaseModel):
    """채팅 요청 스키마"""

    message: str = Field(..., description="사용자 메시지")
    similarity_threshold: float = Field(0.7, description="유사도 임계값")  # 0.5에서 0.7로 높임
    max_tokens: int = Field(1024, description="최대 토큰 수")
    include_sources: Optional[bool] = Field(True, description="소스 포함 여부")


class ChatResponse(BaseModel):
    """OpenAI 기반 채팅 응답"""

    response: str
    sources: List[Dict]
    query: str
    search_results: List[Dict]


class SearchResult(BaseModel):
    """검색 결과 모델"""

    id: str
    text: str
    score: float
    metadata: Dict


class VectorStatsResponse(BaseModel):
    """벡터 통계 응답"""

    stats: Dict
    health: Dict


# ==================== Utility Functions ====================


async def _check_vllm_server_with_retry(max_retries: int = 3) -> bool:
    """VLLM 서버 상태 확인 (재시도 포함)"""
    import httpx

    vllm_url = settings.VLLM_BASE_URL or "http://localhost:8001"

    for attempt in range(max_retries):
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{vllm_url}/health")
                if response.status_code == 200:
                    logger.info("✅ VLLM 서버 연결 확인됨")
                    return True

        except Exception as e:
            logger.warning(
                f"VLLM 서버 확인 실패 (시도 {attempt + 1}/{max_retries}): {e}"
            )

        if attempt < max_retries - 1:
            import asyncio

            await asyncio.sleep(1)  # 1초 대기

    return False


# ==================== Document Upload Endpoints ====================


@router.post("/upload_document_gpu", response_model=DocumentUploadResponse)
async def upload_document_gpu(
    file: UploadFile = File(..., description="PDF 파일"),
    system_message: Optional[str] = Form(
        "당신은 제공된 참고 문서의 정확한 정보와 사실을 바탕으로 답변하는 AI 어시스턴트입니다.",
        description="시스템 메시지",
    ),
    influencer_name: Optional[str] = Form("AI", description="AI 캐릭터 이름"),
    db: Session = Depends(get_db),
):
    """PDF 문서를 VLLM GPU 벡터 스토어에 업로드 (자동 벡터DB 초기화 포함)"""
    try:
        logger.info(
            f"📥 GPU 문서 업로드 시작 (벡터DB 자동 초기화 포함): {file.filename}"
        )

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
            # RAG 서비스로 문서 처리
            logger.info("🔄 RAG 서비스 문서 처리 시작")
            rag_service = get_rag_service()
            qa_pairs = await rag_service.document_processor.process_pdf(temp_file_path)

            logger.info(f"📄 QA 쌍 생성 완료: {len(qa_pairs)}개")

            if not qa_pairs:
                raise HTTPException(
                    status_code=500, detail="QA 쌍 생성에 실패했습니다."
                )

            # vLLM 서버의 Milvus 벡터DB에 저장
            source_file = file.filename
            logger.info("💾 vLLM 서버 벡터DB 저장 시작")

            import httpx

            # QA 쌍을 DocumentChunk 형식으로 변환
            documents = []
            for i, qa in enumerate(qa_pairs):
                documents.append(
                    {
                        "id": f"chunk_{i}",
                        "text": qa["answer"],  # 답변을 텍스트로 사용
                        "metadata": {
                            "question": qa["question"],
                            "chunk_id": qa["chunk_id"],
                            "source": source_file,
                            "page": qa.get("page", 1),
                        },
                    }
                )

            # vLLM 서버의 벡터DB API 호출
            vllm_url = settings.VLLM_BASE_URL or "http://localhost:8001"
            logger.info(f"🔗 vLLM 서버 URL: {vllm_url}")

            async with httpx.AsyncClient(timeout=60.0) as client:
                # 1. 벡터DB 초기화
                logger.info("🗑️ 벡터DB 초기화 시작")
                clear_response = await client.delete(f"{vllm_url}/vector-db/clear")

                if clear_response.status_code == 200:
                    logger.info("✅ 벡터DB 초기화 완료")
                else:
                    logger.warning(
                        f"⚠️ 벡터DB 초기화 실패: {clear_response.status_code}"
                    )
                    # 초기화 실패해도 계속 진행

                # 2. 문서 저장
                logger.info(f"📊 저장할 문서 수: {len(documents)}개")
                logger.info(
                    f"📤 vLLM 서버로 요청 전송: {vllm_url}/vector-db/embed-and-store"
                )
                response = await client.post(
                    f"{vllm_url}/vector-db/embed-and-store",
                    json={"documents": documents},
                )

                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"✅ vLLM 서버 벡터DB 저장 완료: {result}")
                else:
                    logger.error(
                        f"❌ vLLM 서버 벡터DB 저장 실패: {response.status_code}"
                    )
                    logger.error(f"❌ 응답 내용: {response.text}")
                    raise HTTPException(
                        status_code=500, detail="vLLM 서버 벡터DB 저장에 실패했습니다."
                    )

            return DocumentUploadResponse(
                status="success",
                message=f"벡터DB가 초기화되고 문서가 vLLM 서버의 Milvus 벡터DB에 성공적으로 업로드되었습니다.",
                pipeline_info={"qa_count": len(qa_pairs), "source_file": source_file},
            )

        finally:
            # 임시 파일 정리
            if os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
                logger.info(f"🗑️ 임시 파일 삭제: {temp_file_path}")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ GPU 문서 업로드 실패: {e}")
        import traceback

        logger.error(f"❌ 상세 오류: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"문서 업로드 실패: {str(e)}")


# ==================== Chat Endpoints ====================


@router.post("/chat_gpu", response_model=ChatResponse)
async def chat_gpu(chat_request: ChatRequest):
    """VLLM GPU 벡터 검색을 사용한 채팅 (단순화된 RAG 프로세서 기반)"""
    try:
        query = chat_request.message
        top_k = 5  # Default value from ChatRequest
        similarity_threshold = chat_request.similarity_threshold
        include_sources = True  # Default value from ChatRequest
        max_tokens = chat_request.max_tokens
        model = "gpt-4"  # Default value from ChatRequest

        logger.info(
            f"🔍 단순화된 RAG 프로세서 시작: query='{query}', top_k={top_k}, similarity_threshold={similarity_threshold}"
        )

        # 단순화된 RAG 프로세서 사용
        response, sources, should_fallback_to_mcp = await process_with_rag(
            message=query,
            influencer_name="AI 어시스턴트",
            system_message="당신은 제공된 참고 문서의 정확한 정보와 사실을 바탕으로 답변하는 AI 어시스턴트입니다.",
        )

        if should_fallback_to_mcp:
            logger.info("🔄 RAG 처리 실패 또는 문서 없음, MCP로 전환 필요")
            return ChatResponse(
                response="",  # 빈 응답으로 MCP 분기처리 유도
                sources=[],
                query=query,
                search_results=[],
            )

        if not response:
            logger.info("❌ RAG에서 응답 생성 실패, MCP로 전환")
            return ChatResponse(
                response="",  # 빈 응답으로 MCP 분기처리 유도
                sources=[],
                query=query,
                search_results=[],
            )

        # 검색 결과를 딕셔너리로 변환
        search_results_dict = []
        for source in sources:
            search_results_dict.append(
                {
                    "text": source.get("text", ""),
                    "score": source.get("score", 0),
                    "metadata": source.get("metadata", {}),
                }
            )

        logger.info(f"✅ RAG 응답 생성 완료: {len(sources)}개 문서 참조")
        return ChatResponse(
            response=response,
            sources=sources,
            query=query,
            search_results=search_results_dict,
        )

    except Exception as e:
        logger.error(f"❌ RAG 프로세서 처리 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== Vector Search Endpoints ====================


@router.post("/embed_and_search", response_model=List[SearchResult])
async def embed_and_search(
    query: str = Form(..., description="검색 쿼리"),
    top_k: int = Form(5, description="검색할 상위 k개"),
    score_threshold: float = Form(0.7, description="유사도 임계값"),  # 0.5에서 0.7로 높임
):
    """임베딩 생성 및 벡터 검색"""
    try:
        logger.info(
            f"🔍 임베딩 검색 시작: query='{query}', top_k={top_k}, score_threshold={score_threshold}"
        )

        # RAG 서비스 가져오기
        rag_service = get_rag_service()

        # VLLM GPU 메모리에서 검색
        search_results = await rag_service.vector_store.search_similar(query, top_k)

        if not search_results:
            return []

        # 결과를 SearchResult 형태로 변환
        results = []
        for result in search_results:
            if result["score"] >= score_threshold:
                results.append(
                    {
                        "id": result["metadata"].get("chunk_id", "unknown"),
                        "text": result["text"],
                        "score": result["score"],
                        "metadata": result["metadata"],
                    }
                )

        logger.info(f"✅ 검색 완료: {len(results)}개 결과")
        return results

    except Exception as e:
        logger.error(f"❌ 임베딩 검색 실패: {e}")
        raise HTTPException(status_code=500, detail=f"검색 실패: {str(e)}")


# ==================== Vector Store Management ====================


@router.get("/vector_stats", response_model=VectorStatsResponse)
async def get_vector_stats():
    """vLLM 서버의 Milvus 벡터DB 통계 및 상태 확인"""
    try:
        import httpx

        # vLLM 서버의 벡터DB 통계 API 호출
        vllm_url = settings.VLLM_BASE_URL or "http://localhost:8001"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{vllm_url}/vector-db/stats")

            if response.status_code == 200:
                vllm_stats = response.json()

                # vLLM 서버 통계 정보
                stats = {
                    "total_chunks": vllm_stats.get("num_entities", 0),
                    "embedding_dimension": 1024,  # BGE-M3 기본 차원
                    "device": "vllm_milvus",
                    "collection_name": vllm_stats.get(
                        "collection_name", "rag_documents"
                    ),
                }

                health = {
                    "status": (
                        "healthy" if vllm_stats.get("num_entities", 0) > 0 else "empty"
                    ),
                    "device": "vllm_milvus",
                    "total_chunks": vllm_stats.get("num_entities", 0),
                    "embedding_model_loaded": True,
                }

                return VectorStatsResponse(stats=stats, health=health)
            else:
                logger.error(f"❌ vLLM 벡터DB 통계 조회 실패: {response.status_code}")
                raise HTTPException(
                    status_code=500, detail="vLLM 벡터DB 통계 조회 실패"
                )

    except Exception as e:
        logger.error(f"❌ vLLM 벡터DB 통계 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"통계 조회 실패: {str(e)}")


@router.delete("/clear_vector_store")
async def clear_vector_store():
    """vLLM 서버의 Milvus 벡터DB 초기화"""
    try:
        import httpx

        # vLLM 서버의 벡터DB 초기화 API 호출
        vllm_url = settings.VLLM_BASE_URL or "http://localhost:8001"

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.delete(f"{vllm_url}/vector-db/clear")

            if response.status_code == 200:
                result = response.json()
                return {
                    "success": result.get("success", True),
                    "message": result.get("message", "vLLM 벡터DB가 초기화되었습니다."),
                }
            else:
                logger.error(f"❌ vLLM 벡터DB 초기화 실패: {response.status_code}")
                raise HTTPException(status_code=500, detail="vLLM 벡터DB 초기화 실패")

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ vLLM 벡터DB 초기화 실패: {e}")
        raise HTTPException(status_code=500, detail=f"벡터DB 초기화 실패: {str(e)}")

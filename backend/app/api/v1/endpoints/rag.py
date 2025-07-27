"""
RAG (Retrieval-Augmented Generation) API 엔드포인트
프로젝트 구조에 맞게 재구성된 RAG API
"""

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Optional, Dict, List
import json
import logging
import base64
from datetime import datetime

# Backend imports
from app.database import get_db
from app.models.user import HFTokenManage
from app.core.encryption import decrypt_sensitive_data
from app.core.config import settings
from app.services.rag_service import get_rag_service, RAGConfig
from app.services.vllm_client import vllm_health_check

logger = logging.getLogger(__name__)

router = APIRouter()


class DocumentUploadRequest(BaseModel):
    """문서 업로드 요청 모델"""
    group_id: int = Field(..., description="그룹 ID")
    pdf_path: str = Field(..., description="PDF 파일 경로")
    system_message: Optional[str] = Field(
        "당신은 제공된 참고 문서의 정확한 정보와 사실을 바탕으로 답변하는 AI 어시스턴트입니다.",
        description="시스템 메시지"
    )
    influencer_name: Optional[str] = Field("AI", description="AI 캐릭터 이름")


class RAGChatRequest(BaseModel):
    """RAG 채팅 요청 모델"""
    query: str = Field(..., description="사용자 질문")
    group_id: int = Field(..., description="그룹 ID")
    include_sources: Optional[bool] = Field(True, description="출처 정보 포함 여부")


class RAGChatResponse(BaseModel):
    """RAG 채팅 응답 모델"""
    query: str
    response: str
    timestamp: str
    sources: Optional[List[Dict]] = None
    context_preview: Optional[str] = None
    model_info: Optional[Dict] = None
    error: Optional[str] = None


class RAGPipelineInfo(BaseModel):
    """RAG 파이프라인 정보 모델"""
    group_id: int
    pdf_path: str
    qa_count: int
    system_message: str
    influencer_name: str
    created_at: str


class RAGHealthResponse(BaseModel):
    """RAG 상태 응답 모델"""
    status: str
    vllm_server: str
    active_pipelines: int
    pipeline_groups: List[int]
    timestamp: str


async def _get_hf_token_by_group(group_id: int, db: Session) -> Optional[str]:
    """그룹별 HF 토큰 가져오기"""
    try:
        # 그룹에 해당하는 HF 토큰 조회
        hf_token_record = db.query(HFTokenManage).filter(
            HFTokenManage.group_id == group_id,
            HFTokenManage.is_active == True
        ).first()
        
        if hf_token_record and hf_token_record.hf_token:
            # 암호화된 토큰 복호화
            return decrypt_sensitive_data(hf_token_record.hf_token)
        
        return None
        
    except Exception as e:
        logger.error(f"HF 토큰 조회 실패: {e}")
        return None


async def _check_vllm_server_with_retry(max_retries: int = 3) -> bool:
    """VLLM 서버 상태 확인 (재시도 포함)"""
    for attempt in range(max_retries):
        try:
            if await vllm_health_check():
                return True
        except Exception as e:
            logger.warning(f"VLLM 서버 확인 실패 (시도 {attempt + 1}/{max_retries}): {e}")
        
        if attempt < max_retries - 1:
            import asyncio
            await asyncio.sleep(1)  # 1초 대기
    
    return False


@router.post("/upload_document", response_model=Dict)
async def upload_document(req: DocumentUploadRequest, db: Session = Depends(get_db)):
    """문서 업로드 및 RAG 파이프라인 생성"""
    try:
        # VLLM 서버 상태 확인
        if not await _check_vllm_server_with_retry():
            raise HTTPException(
                status_code=503,
                detail="VLLM 서버에 연결할 수 없습니다. 서버 상태를 확인해주세요."
            )
        
        # HF 토큰 가져오기
        hf_token = await _get_hf_token_by_group(req.group_id, db)
        if not hf_token:
            logger.warning(f"그룹 {req.group_id}에 대한 HF 토큰이 없습니다.")
        
        # RAG 서비스 가져오기
        rag_service = get_rag_service()
        
        # 파이프라인 생성
        success = await rag_service.create_pipeline(
            group_id=req.group_id,
            pdf_path=req.pdf_path,
            system_message=req.system_message,
            influencer_name=req.influencer_name
        )
        
        if success:
            pipeline_info = rag_service.get_pipeline_info(req.group_id)
            return {
                "status": "success",
                "message": f"문서 업로드 완료: {pipeline_info['qa_count']}개 QA 쌍 생성",
                "pipeline_info": pipeline_info
            }
        else:
            raise HTTPException(
                status_code=500,
                detail="문서 업로드에 실패했습니다."
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[RAG UPLOAD] 문서 업로드 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/chat", response_model=RAGChatResponse)
async def rag_chat(req: RAGChatRequest, db: Session = Depends(get_db)):
    """RAG 기반 채팅 (비스트리밍)"""
    try:
        # RAG 서비스 가져오기
        rag_service = get_rag_service()
        
        # 채팅 실행
        result = await rag_service.chat(
            group_id=req.group_id,
            query=req.query,
            include_sources=req.include_sources
        )
        
        return RAGChatResponse(**result)
        
    except Exception as e:
        logger.error(f"[RAG CHAT] 채팅 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.websocket("/chat/{group_id}")
async def rag_chat_websocket(
    websocket: WebSocket, 
    group_id: int, 
    lora_repo: str = Query(...), 
    influencer_id: str = Query(None), 
    db: Session = Depends(get_db)
):
    """RAG 기반 웹소켓 채팅"""
    # lora_repo 디코딩
    try:
        lora_repo_decoded = base64.b64decode(lora_repo).decode()
    except Exception as e:
        await websocket.accept()
        await websocket.send_text(json.dumps({
            "error_code": "LORA_REPO_DECODE_ERROR", 
            "message": f"lora_repo 디코딩 실패: {e}"
        }))
        await websocket.close()
        return
    
    await websocket.accept()
    
    try:
        # VLLM 서버 상태 확인
        if not await _check_vllm_server_with_retry():
            logger.warning(f"[RAG WS] VLLM 서버 연결 불안정하지만 계속 진행")
            await websocket.send_text(json.dumps({
                "type": "warning",
                "message": "VLLM 서버 연결이 불안정합니다. 응답이 지연될 수 있습니다."
            }))
        
        # RAG 서비스 가져오기
        rag_service = get_rag_service()
        
        # 파이프라인 확인
        pipeline_info = rag_service.get_pipeline_info(group_id)
        if not pipeline_info:
            await websocket.send_text(json.dumps({
                "error_code": "RAG_PIPELINE_NOT_FOUND",
                "message": f"그룹 {group_id}에 대한 RAG 파이프라인이 없습니다. 먼저 문서를 업로드해주세요."
            }))
            await websocket.close()
            return
        
        # 인플루언서 정보 가져오기 (필요시)
        system_prompt = pipeline_info.get("system_message", "당신은 도움이 되는 AI 어시스턴트입니다.")
        influencer_name = pipeline_info.get("influencer_name", "AI")
        
        # WebSocket 프록시 모드
        while True:
            try:
                data = await websocket.receive_text()
                logger.info(f"[RAG WS] 메시지 수신: {data[:100]}...")
                
                # RAG 채팅 실행
                result = await rag_service.chat(
                    group_id=group_id,
                    query=data,
                    include_sources=True
                )
                
                if "error" in result:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": result["error"]
                    }))
                    continue
                
                # 응답 전송
                await websocket.send_text(json.dumps({
                    "type": "response",
                    "content": result["response"],
                    "sources": result.get("sources", []),
                    "context_preview": result.get("context_preview", "")
                }))
                
            except WebSocketDisconnect:
                logger.info(f"[RAG WS] WebSocket 연결 종료: group_id={group_id}")
                break
            except Exception as e:
                logger.error(f"[RAG WS] 오류 발생: {e}")
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"채팅 중 오류가 발생했습니다: {str(e)}"
                }))
                break
                
    except Exception as e:
        logger.error(f"[RAG WS] 초기화 실패: {e}")
        await websocket.send_text(json.dumps({
            "error_code": "INITIALIZATION_ERROR",
            "message": f"초기화 중 오류가 발생했습니다: {str(e)}"
        }))
        await websocket.close()


@router.get("/status/{group_id}", response_model=Optional[RAGPipelineInfo])
async def get_rag_status(group_id: int):
    """RAG 파이프라인 상태 조회"""
    try:
        rag_service = get_rag_service()
        pipeline_info = rag_service.get_pipeline_info(group_id)
        
        if pipeline_info:
            return RAGPipelineInfo(group_id=group_id, **pipeline_info)
        else:
            return None
            
    except Exception as e:
        logger.error(f"[RAG STATUS] 상태 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/cleanup/{group_id}")
async def cleanup_rag_pipeline(group_id: int):
    """RAG 파이프라인 정리"""
    try:
        rag_service = get_rag_service()
        success = await rag_service.cleanup_pipeline(group_id)
        
        if success:
            return {"status": "success", "message": f"파이프라인 정리 완료: group_id={group_id}"}
        else:
            raise HTTPException(
                status_code=404,
                detail=f"그룹 {group_id}에 대한 파이프라인을 찾을 수 없습니다."
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[RAG CLEANUP] 파이프라인 정리 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health", response_model=RAGHealthResponse)
async def check_rag_health():
    """RAG 서비스 전체 상태 확인"""
    try:
        # VLLM 서버 상태 확인
        vllm_status = await _check_vllm_server_with_retry(max_retries=1)
        
        # RAG 서비스 가져오기
        rag_service = get_rag_service()
        pipelines = rag_service.list_pipelines()
        
        return RAGHealthResponse(
            status="healthy",
            vllm_server="connected" if vllm_status else "disconnected",
            active_pipelines=len(pipelines),
            pipeline_groups=[p["group_id"] for p in pipelines],
            timestamp=datetime.now().isoformat()
        )
        
    except Exception as e:
        logger.error(f"[RAG HEALTH] 상태 확인 실패: {e}")
        return RAGHealthResponse(
            status="unhealthy",
            vllm_server="unknown",
            active_pipelines=0,
            pipeline_groups=[],
            timestamp=datetime.now().isoformat()
        )


@router.get("/pipelines", response_model=List[RAGPipelineInfo])
async def list_rag_pipelines():
    """모든 RAG 파이프라인 목록 조회"""
    try:
        rag_service = get_rag_service()
        pipelines = rag_service.list_pipelines()
        
        return [
            RAGPipelineInfo(**pipeline)
            for pipeline in pipelines
        ]
        
    except Exception as e:
        logger.error(f"[RAG PIPELINES] 파이프라인 목록 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 
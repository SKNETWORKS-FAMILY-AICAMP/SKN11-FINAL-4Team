from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect,
    Query,
    Depends,
    HTTPException,
)
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import HFTokenManage
from app.services.vllm_client import (
    VLLMWebSocketClient,
    VLLMClient,
    get_vllm_client,
    vllm_health_check,
)
from app.core.encryption import decrypt_sensitive_data
from app.services.hf_token_resolver import get_token_by_group
from app.services.chat_message_service import ChatMessageService
import json
import logging
import base64
import asyncio
from datetime import datetime
from typing import List, Dict, Optional
from app.core.config import settings
import os
import httpx

router = APIRouter()
logger = logging.getLogger(__name__)


# 메모리 히스토리 클래스 제거 - 데이터베이스만 사용


class ModelLoadRequest(BaseModel):
    lora_repo: str
    group_id: int


# 전역 히스토리 저장소 제거 - 데이터베이스만 사용


@router.websocket("/chatbot/{lora_repo}")
async def chatbot(
    websocket: WebSocket,
    lora_repo: str,
    group_id: int = Query(...),
    influencer_id: str = Query(None),
    db: Session = Depends(get_db),
):
    # lora_repo는 base64로 인코딩되어 있으므로 디코딩
    try:
        lora_repo_decoded = base64.b64decode(lora_repo).decode()
    except Exception as e:
        await websocket.accept()
        await websocket.send_text(
            json.dumps(
                {
                    "error_code": "LORA_REPO_DECODE_ERROR",
                    "message": f"lora_repo 디코딩 실패: {e}",
                }
            )
        )
        await websocket.close()
        return

    await websocket.accept()

    # 데이터베이스 히스토리 서비스 초기화
    chat_message_service = ChatMessageService(db)
    
    # 세션 관리 변수
    current_session_id: Optional[str] = None

    try:
        # VLLM 서버 상태 확인
        if not await vllm_health_check():
            logger.error(f"[WS] VLLM 서버 연결 실패 (URL: {settings.VLLM_BASE_URL})")
            await websocket.send_text(
                json.dumps(
                    {
                        "error_code": "VLLM_SERVER_UNAVAILABLE",
                        "message": "VLLM 서버에 연결할 수 없습니다. 서버 상태를 확인해주세요.",
                    }
                )
            )
            await websocket.close()
            return

        logger.info(
            f"[WS] VLLM WebSocket 연결 시작: lora_repo={lora_repo_decoded}, group_id={group_id}"
        )

        # HF 토큰 가져오기
        hf_token = await _get_hf_token_by_group(group_id, db)

        if influencer_id:
            from app.models.influencer import AIInfluencer

            influencer = (
                db.query(AIInfluencer)
                .filter(AIInfluencer.influencer_id == influencer_id)
                .first()
            )
            if influencer and influencer.system_prompt is not None:
                system_prompt = str(influencer.system_prompt)
                logger.info(
                    f"[WS] ✅ 저장된 시스템 프롬프트 사용: {influencer.influencer_name}"
                )
            else:
                logger.info(
                    f"[WS] ⚠️ 저장된 시스템 프롬프트가 없어 기본 시스템 프롬프트 사용"
                )

        # VLLM 서버에 어댑터 로드
        vllm_client = await get_vllm_client()
        try:
            await vllm_client.load_adapter(
                lora_repo_decoded, lora_repo_decoded, hf_token
            )
            logger.info(f"[WS] VLLM 어댑터 로드 완료: {lora_repo_decoded}")
        except Exception as e:
            logger.error(f"[WS] VLLM 어댑터 로드 실패: {e}")
            await websocket.send_text(
                json.dumps(
                    {
                        "error_code": "VLLM_ADAPTER_LOAD_FAILED",
                        "message": f"VLLM 어댑터 로드에 실패했습니다: {str(e)}",
                    }
                )
            )
            await websocket.close()
            return

        # WebSocket 프록시 모드
        while True:
            try:
                data = await websocket.receive_text()
                logger.info(f"[WS] 메시지 수신: {data[:100]}...")

                # 메시지 파싱 (JSON 또는 일반 텍스트)
                try:
                    message_data = json.loads(data)
                    message_type = message_data.get("type", "chat")
                    user_message = message_data.get("message", data)
                    
                    # 히스토리 관련 명령 처리
                    if message_type == "get_history":
                        # 현재 세션의 히스토리 조회
                        if current_session_id:
                            session_messages = chat_message_service.get_session_messages(current_session_id)
                            
                            # 세션 메시지를 히스토리 형식으로 변환
                            history_data = []
                            for msg in session_messages:
                                if msg.message_content:  # 빈 메시지 제외
                                    history_data.append({
                                        "query": "이전 대화",
                                        "response": msg.message_content,
                                        "timestamp": msg.created_at.isoformat() if msg.created_at else None,
                                        "source": "session",
                                        "session_id": msg.session_id
                                    })
                            
                            await websocket.send_text(
                                json.dumps({
                                    "type": "history",
                                    "data": history_data
                                })
                            )
                        else:
                            await websocket.send_text(
                                json.dumps({
                                    "type": "history",
                                    "data": []
                                })
                            )
                        continue
                    elif message_type == "clear_history":
                        # 현재 세션 종료 (새 세션 시작)
                        if current_session_id:
                            chat_message_service.end_session(current_session_id)
                            logger.info(f"[WS] 세션 종료 (히스토리 초기화): session_id={current_session_id}")
                        
                        # 새 세션 생성
                        current_session_id = chat_message_service.create_session(influencer_id or "default")
                        logger.info(f"[WS] 새 세션 생성 (히스토리 초기화): session_id={current_session_id}")
                        
                        await websocket.send_text(
                            json.dumps({
                                "type": "history_cleared",
                                "message": "채팅 히스토리가 초기화되었습니다."
                            })
                        )
                        continue
                    
                except json.JSONDecodeError:
                    # 일반 텍스트 메시지로 처리
                    message_type = "chat"
                    user_message = data

                # 세션 관리
                if current_session_id is None:
                    # 새 세션 생성
                    current_session_id = chat_message_service.create_session(influencer_id or "default")
                    logger.info(f"[WS] 새 세션 생성: session_id={current_session_id}")
                
                # 히스토리 컨텍스트 추가 (현재 세션 기반)
                history_summary = ""  # 변수 초기화
                
                # 현재 세션의 이전 메시지들 조회
                session_messages = chat_message_service.get_session_messages(current_session_id)
                
                if session_messages and len(session_messages) > 1:  # 첫 번째 메시지(빈 세션) 제외
                    # OpenAI로 히스토리 요약
                    try:
                        # 세션 메시지를 히스토리 형식으로 변환
                        all_history = []
                        for msg in session_messages[1:]:  # 첫 번째 빈 메시지 제외
                            all_history.append({
                                "query": msg.message_content[:100] + "...",  # 간단한 요약
                                "response": msg.message_content
                            })
                        
                        if all_history:
                            history_summary = await summarize_chat_history(all_history, max_tokens=100)
                            if history_summary and len(history_summary) > 10:
                                enhanced_message = f"이전 대화 요약: {history_summary}\n\n현재 질문: {user_message}"
                                logger.info(f"[WS] OpenAI 히스토리 요약 사용 (세션: {current_session_id}, 메시지: {len(all_history)}개, 요약: {len(history_summary)}자)")
                            else:
                                # 요약 실패 시 간단한 대체 방법 사용
                                recent_chat = all_history[-1]
                                simple_summary = f"마지막 질문: {recent_chat['query'][:50]}..."
                                enhanced_message = f"이전: {simple_summary}\n\n현재 질문: {user_message}"
                                logger.info(f"[WS] 간단한 히스토리 사용 (세션: {current_session_id}, 메시지: {len(all_history)}개)")
                        else:
                            enhanced_message = user_message
                    except Exception as e:
                        logger.warning(f"[WS] 히스토리 요약 실패, 요약 없이 진행: {e}")
                        enhanced_message = user_message
                else:
                    enhanced_message = user_message

                # VLLM 서버에서 스트리밍 응답 생성
                try:
                    vllm_client = await get_vllm_client()
                    system_prompt = (
                        str(influencer.system_prompt)
                        if influencer and influencer.system_prompt
                        else "당신은 도움이 되는 AI 어시스턴트입니다."
                    )

                    # 스트리밍 응답 생성
                    token_count = 0
                    full_response = ""
                    
                    async for token in vllm_client.generate_response_stream(
                        user_message=enhanced_message,
                        system_message=system_prompt,
                        influencer_name=(
                            str(influencer.influencer_name) if influencer else "한세나"
                        ),
                        model_id=lora_repo_decoded,
                        max_new_tokens=512,
                        temperature=0.7,
                    ):
                        # 각 토큰을 실시간으로 클라이언트에 전송
                        await websocket.send_text(
                            json.dumps({"type": "token", "content": token})
                        )
                        full_response += token
                        token_count += 1

                        # 너무 많은 토큰이 오면 중단 (무한 루프 방지)
                        if token_count > 1000:
                            logger.warning(
                                f"[WS] 토큰 수가 너무 많아 중단: {token_count}"
                            )
                            break

                    # 스트리밍 완료 신호
                    await websocket.send_text(
                        json.dumps({"type": "complete", "content": ""})
                    )

                    # 세션에 대화 저장 (완료 후에만)
                    if full_response.strip():
                        try:
                            # 전체 대화 내용을 하나의 메시지로 저장
                            full_conversation = f"사용자: {user_message}\n\nAI: {full_response}"
                            chat_message_service.add_message_to_session(
                                session_id=current_session_id,
                                influencer_id=influencer_id or "default",
                                message_content=full_conversation
                            )
                            logger.info(f"[WS] 세션에 대화 저장 완료: session_id={current_session_id}")
                        except Exception as e:
                            logger.error(f"[WS] 세션 저장 실패: {e}")
                    
                    logger.info(
                        f"[WS] VLLM 스트리밍 응답 전송 완료 (토큰 수: {token_count})"
                    )

                except Exception as e:
                    logger.error(f"[WS] VLLM 스트리밍 추론 중 오류: {e}")
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "error",
                                "error_code": "VLLM_INFERENCE_ERROR",
                                "message": str(e),
                            }
                        )
                    )

            except WebSocketDisconnect:
                # 세션 종료
                if current_session_id:
                    chat_message_service.end_session(current_session_id)
                    logger.info(f"[WS] 세션 종료: session_id={current_session_id}")
                
                logger.info(f"[WS] WebSocket 연결 종료: lora_repo={lora_repo_decoded}")
                break
            except Exception as e:
                logger.error(f"[WS] WebSocket 처리 중 오류: {e}")
                await websocket.send_text(
                    json.dumps({"error_code": "WEBSOCKET_ERROR", "message": str(e)})
                )
                break

    except Exception as e:
        logger.error(f"[WS] WebSocket 연결 처리 중 오류: {e}")
        try:
            await websocket.send_text(
                json.dumps({"error_code": "CONNECTION_ERROR", "message": str(e)})
            )
        except:
            pass


async def _get_hf_token_by_group(group_id: int, db: Session) -> str | None:
    """그룹 ID로 HF 토큰 가져오기"""
    try:
        hf_token_manage = (
            db.query(HFTokenManage)
            .filter(HFTokenManage.group_id == group_id)
            .order_by(HFTokenManage.created_at.desc())
            .first()
        )

        if hf_token_manage:
            return decrypt_sensitive_data(str(hf_token_manage.hf_token_value))
        else:
            logger.warning(f"그룹 {group_id}에 등록된 HF 토큰이 없습니다.")
            return None

    except Exception as e:
        logger.error(f"HF 토큰 조회 실패: {e}")
        return None


# OpenAI API 클라이언트 추가
async def get_openai_client():
    """OpenAI API 클라이언트 생성"""
    return httpx.AsyncClient(
        base_url="https://api.openai.com/v1",
        headers={
            "Authorization": f"Bearer {os.getenv('OPENAI_API_KEY')}",
            "Content-Type": "application/json"
        },
        timeout=30.0
    )

async def summarize_chat_history(history: List[Dict], max_tokens: int = 80) -> str:
    """OpenAI를 사용해서 채팅 히스토리를 요약 (완전한 요약 보장)"""
    if not history:
        return ""
    
    try:
        # 히스토리를 텍스트로 변환
        history_text = ""
        for i, chat in enumerate(history[-5:], 1):  # 최근 5개 대화만
            history_text += f"Q{i}: {chat['query']}\nA{i}: {chat['response']}\n\n"
        
        # OpenAI API 호출 (개선된 시스템 프롬프트)
        openai_client = await get_openai_client()
        response = await openai_client.post(
            "/chat/completions",
            json={
                "model": "gpt-3.5-turbo",
                "messages": [
                    {
                        "role": "system",
                        "content": "다음 대화를 80토큰 이하로 완전히 요약하세요. 핵심 정보만 포함하고, 문장을 중간에 끊지 마세요. 반드시 완전한 문장으로 마무리하세요."
                    },
                    {
                        "role": "user",
                        "content": f"다음 대화를 요약해주세요:\n\n{history_text}"
                    }
                ],
                "max_tokens": max_tokens,
                "temperature": 0.1,  # 더 일관된 요약을 위해 낮춤
                "stop": None  # 중간에 끊기지 않도록 stop 토큰 제거
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            summary = result["choices"][0]["message"]["content"].strip()
            logger.info(f"[WS] 히스토리 요약 완료: {len(summary)}자")
            return summary
        else:
            logger.warning(f"[WS] OpenAI 요약 실패: {response.status_code}")
            return ""
            
    except Exception as e:
        logger.error(f"[WS] 히스토리 요약 중 오류: {e}")
        return ""


@router.post("/load_model")
async def model_load(req: ModelLoadRequest, db: Session = Depends(get_db)):
    """모델 로드 (VLLM 서버만 사용)"""
    try:
        # HF 토큰 가져오기
        hf_token = await _get_hf_token_by_group(req.group_id, db)
        if not hf_token:
            raise HTTPException(status_code=400, detail="HF 토큰이 없습니다.")

        # VLLM 서버 상태 확인
        if not await vllm_health_check():
            raise HTTPException(
                status_code=503, detail="VLLM 서버에 연결할 수 없습니다."
            )

        # VLLM 서버에 어댑터 로드
        try:
            vllm_client = await get_vllm_client()
            await vllm_client.load_adapter(req.lora_repo, req.lora_repo, hf_token)
            logger.info(f"[MODEL LOAD API] VLLM 어댑터 로드 성공: {req.lora_repo}")
            return {
                "success": True,
                "message": "VLLM 서버에서 모델이 성공적으로 로드되었습니다.",
                "server_type": "vllm",
            }
        except Exception as e:
            logger.error(f"[MODEL LOAD API] VLLM 어댑터 로드 실패: {e}")
            raise HTTPException(
                status_code=500, detail=f"VLLM 어댑터 로드 실패: {str(e)}"
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MODEL LOAD API] 모델 로드 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

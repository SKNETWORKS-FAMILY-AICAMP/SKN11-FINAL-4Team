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
from app.services.runpod_client import (
    get_runpod_client,
    runpod_health_check,
    runpod_generate_text_stream,
    runpod_generate_text,
)
from app.core.encryption import decrypt_sensitive_data
from app.services.hf_token_resolver import get_token_by_group
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


class ChatHistory:
    """채팅 히스토리 관리 클래스"""
    
    def __init__(self, max_chars: int = 1000):
        self.history: List[Dict] = []
        self.max_chars = max_chars
    
    def add_message(self, query: str, response: str, context: str = "", sources: List[Dict] = None, model_info: Dict = None):
        """메시지 추가"""
        message = {
            "query": query,
            "response": response,
            "context": context,
            "sources": sources or [],
            "model_info": model_info or {},
            "timestamp": datetime.now().isoformat()
        }
        
        self.history.append(message)
        self._truncate_history()
    
    def get_history_context(self, max_messages: int = 1) -> str:
        """히스토리 컨텍스트 생성 (OpenAI 요약 사용으로 대체됨)"""
        # OpenAI 요약을 사용하므로 이 메서드는 더 이상 사용하지 않음
        return ""
    
    def _truncate_history(self):
        """히스토리 자르기 (문자 수 기준)"""
        if len(self.history) <= 1:
            return
        
        # 최신 메시지부터 역순으로 계산
        total_chars = 0
        keep_messages = []
        
        for message in reversed(self.history):
            query_length = len(message.get("query", ""))
            response_length = len(message.get("response", ""))
            total_message_length = query_length + response_length
            
            if total_chars + total_message_length > self.max_chars:
                break
            
            total_chars += total_message_length
            keep_messages.append(message)
        
        # 순서 복원
        self.history = list(reversed(keep_messages))
    
    def get_history(self) -> List[Dict]:
        """전체 히스토리 반환"""
        return self.history.copy()
    
    def clear_history(self):
        """히스토리 초기화"""
        self.history.clear()


class ModelLoadRequest(BaseModel):
    lora_repo: str
    group_id: int


# 전역 히스토리 저장소 (세션별)
chat_histories: Dict[str, ChatHistory] = {}


@router.websocket("/chatbot/{lora_repo}")
async def chatbot(
    websocket: WebSocket,
    lora_repo: str,
):
    # 매우 상세한 연결 정보 로그
    client_host = websocket.client.host if websocket.client else "unknown"
    client_port = websocket.client.port if websocket.client else "unknown"
    
    logger.info(f"🔗 [WS] WebSocket 연결 요청 시작")
    logger.info(f"🔗 [WS] Client: {client_host}:{client_port}")
    logger.info(f"🔗 [WS] Path: {websocket.scope.get('path', 'unknown')}")
    logger.info(f"🔗 [WS] Method: {websocket.scope.get('method', 'unknown')}")
    logger.info(f"🔗 [WS] Scheme: {websocket.scope.get('scheme', 'unknown')}")
    logger.info(f"🔗 [WS] Full URL: {websocket.url}")
    logger.info(f"🔗 [WS] Scope keys: {list(websocket.scope.keys())}")
    
    # Headers 로깅 (보안상 민감한 정보 제외)
    headers = dict(websocket.scope.get("headers", []))
    safe_headers = {}
    for header_name, header_value in headers.items():
        header_name_str = header_name.decode() if isinstance(header_name, bytes) else str(header_name)
        header_value_str = header_value.decode() if isinstance(header_value, bytes) else str(header_value)
        
        # 민감한 헤더는 마스킹
        if header_name_str.lower() in ['authorization', 'cookie', 'token']:
            safe_headers[header_name_str] = f"{header_value_str[:10]}..." if len(header_value_str) > 10 else "***"
        else:
            safe_headers[header_name_str] = header_value_str
    
    logger.info(f"🔗 [WS] Headers: {safe_headers}")
    
    # WebSocket query 파라미터 수동 파싱
    try:
        from urllib.parse import parse_qs, urlparse
        query_string = str(websocket.scope.get("query_string", b""), "utf-8")
        query_params = parse_qs(query_string)
        
        logger.info(f"[WS] Raw query string: {query_string}")
        logger.info(f"[WS] Parsed query params: {query_params}")
        
        # 필수 파라미터 추출
        group_id = query_params.get("group_id", [None])[0]
        influencer_id = query_params.get("influencer_id", [None])[0]
        token = query_params.get("token", [None])[0]
        
        logger.info(f"[WS] 요청 파라미터: lora_repo={lora_repo}, group_id={group_id}, influencer_id={influencer_id}")
        
        if not group_id:
            logger.error(f"[WS] group_id 파라미터가 없음")
            await websocket.close(code=1003, reason="Missing group_id parameter")
            return
            
        if not token:
            logger.error(f"[WS] token 파라미터가 없음")
            await websocket.close(code=1003, reason="Missing token parameter")
            return
        
        try:
            group_id = int(group_id)
        except (ValueError, TypeError):
            logger.error(f"[WS] group_id가 유효한 정수가 아님: {group_id}")
            await websocket.close(code=1003, reason="Invalid group_id parameter")
            return
        
        logger.info(f"[WS] 토큰 길이: {len(token)}자")
        logger.info(f"[WS] 토큰 앞 50자: {token[:50]}..." if len(token) > 50 else f"[WS] 토큰 전체: {token}")
        
    except Exception as e:
        logger.error(f"[WS] Query 파라미터 파싱 실패: {e}")
        logger.error(f"[WS] Exception type: {type(e).__name__}")
        logger.error(f"[WS] Full scope: {websocket.scope}")
        import traceback
        logger.error(f"[WS] Traceback: {traceback.format_exc()}")
        await websocket.close(code=1003, reason="Parameter parsing failed")
        return
    
    # WebSocket 연결을 먼저 수락
    try:
        await websocket.accept()
        logger.info(f"[WS] WebSocket 연결 수락 완료")
        logger.info(f"[WS] Connection state: {websocket.client_state}")
        logger.info(f"[WS] Application state: {websocket.application_state}")
    except Exception as e:
        logger.error(f"[WS] WebSocket 연결 수락 실패: {e}")
        logger.error(f"[WS] Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"[WS] Traceback: {traceback.format_exc()}")
        return
    
    # JWT 토큰 검증 (연결 후)
    try:
        from app.core.security import verify_token
        
        logger.info(f"[WS] JWT 토큰 검증 시작...")
        payload = verify_token(token)
        
        if not payload:
            logger.error(f"[WS] JWT 토큰 검증 실패: payload가 None")
            await websocket.send_text(
                json.dumps({
                    "error_code": "INVALID_TOKEN",
                    "message": "유효하지 않은 토큰입니다."
                })
            )
            await websocket.close()
            return
        
        user_id = payload.get("sub")
        user_email = payload.get("email")
        user_name = payload.get("name")
        groups = payload.get("groups", [])
        permissions = payload.get("permissions", [])
        
        logger.info(f"[WS] ✅ 토큰 검증 성공!")
        logger.info(f"[WS] 사용자 정보: user_id={user_id}, email={user_email}, name={user_name}")
        logger.info(f"[WS] 권한 정보: groups={groups}, permissions={permissions}")
        
    except Exception as e:
        logger.error(f"[WS] ❌ 토큰 검증 중 예외 발생: {type(e).__name__}: {str(e)}")
        logger.error(f"[WS] 토큰 디버그 정보:")
        logger.error(f"[WS] - 토큰 타입: {type(token)}")
        logger.error(f"[WS] - 토큰 길이: {len(token) if token else 'None'}")
        logger.error(f"[WS] - 첫 10자: {token[:10] if token else 'None'}")
        
        import traceback
        logger.error(f"[WS] 상세 스택 트레이스: {traceback.format_exc()}")
        
        await websocket.send_text(
            json.dumps({
                "error_code": "TOKEN_VERIFICATION_FAILED",
                "message": f"토큰 검증에 실패했습니다: {str(e)}"
            })
        )
        await websocket.close()
        return

    # 데이터베이스 연결 수동 생성
    try:
        from app.database import SessionLocal
        db = SessionLocal()
        logger.info(f"[WS] 데이터베이스 연결 생성 완료")
    except Exception as e:
        logger.error(f"[WS] 데이터베이스 연결 실패: {e}")
        await websocket.send_text(
            json.dumps({
                "error_code": "DATABASE_CONNECTION_FAILED",
                "message": "데이터베이스 연결에 실패했습니다."
            })
        )
        await websocket.close()
        return

    # lora_repo는 base64로 인코딩되어 있으므로 디코딩
    try:
        lora_repo_decoded = base64.b64decode(lora_repo).decode()
    except Exception as e:
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

    # 세션별 히스토리 초기화
    session_id = f"{lora_repo_decoded}_{group_id}_{influencer_id or 'default'}"
    if session_id not in chat_histories:
        chat_histories[session_id] = ChatHistory()
    
    chat_history = chat_histories[session_id]

    try:
        # RunPod 서버 상태 확인 (상세 로그 포함)
        logger.info(f"[WS] ========== RunPod 서버 상태 확인 시작 ==========")
        logger.info(f"[WS] Session ID: {session_id}")
        logger.info(f"[WS] Model/LoRA repo: {lora_repo_decoded}")
        logger.info(f"[WS] Group ID: {group_id}")
        logger.info(f"[WS] Influencer ID: {influencer_id}")
        
        # 환경변수 확인 (settings 사용)
        from app.core.config import settings
        runpod_api_key = settings.RUNPOD_API_KEY
        logger.info(f"[WS] RUNPOD_API_KEY 설정됨: {'Yes' if runpod_api_key else 'No'}")
        if runpod_api_key:
            logger.info(f"[WS] RUNPOD_API_KEY 길이: {len(runpod_api_key)}자")
            logger.info(f"[WS] RUNPOD_API_KEY 앞 10자: {runpod_api_key[:10]}...")
        
        # RunPod 클라이언트 정보 확인
        from app.services.runpod_client import get_runpod_client
        runpod_client = get_runpod_client()
        logger.info(f"[WS] RunPod 클라이언트 생성됨: {type(runpod_client)}")
        logger.info(f"[WS] RunPod 클라이언트 base_url: {getattr(runpod_client, 'base_url', 'Unknown')}")
        
        health_status = await runpod_health_check()
        logger.info(f"[WS] RunPod health check 결과: {health_status}")
        
        if not health_status:
            logger.error(f"[WS] ❌ RunPod 서버 연결 실패")
            await websocket.send_text(
                json.dumps(
                    {
                        "error_code": "RUNPOD_SERVER_UNAVAILABLE", 
                        "message": "RunPod 서버에 연결할 수 없습니다. API 키를 확인해주세요.",
                    }
                )
            )
            await websocket.close()
            return
        
        logger.info(f"[WS] ✅ RunPod 서버 상태 확인 완료")
        
        # RunPod vLLM endpoint 상태 추가 확인
        try:
            from app.services.runpod_manager import get_vllm_manager
            vllm_manager = get_vllm_manager()
            # endpoint_id는 RunPod Serverless에서는 필요하지 않음
            logger.info(f"[WS] ✅ vLLM Manager 준비됨 (RunPod Serverless)")
                
        except Exception as endpoint_error:
            logger.error(f"[WS] ❌ vLLM Manager 확인 중 오류: {endpoint_error}")

        logger.info(
            f"[WS] RunPod WebSocket 연결 시작: lora_repo={lora_repo_decoded}, group_id={group_id}, session_id={session_id}"
        )

        # HF 토큰 가져오기 (필요시)
        hf_token = await _get_hf_token_by_group(group_id, db)

        # 인플루언서 정보 가져오기
        influencer = None
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

        # RunPod는 어댑터 사전 로드가 필요하지 않음 (요청 시 지정)
        logger.info(f"[WS] RunPod LoRA 어댑터 준비: {lora_repo_decoded}")

        # WebSocket 프록시 모드
        while True:
            try:
                data = await websocket.receive_text()
                logger.info(f"[WS] 메시지 수신: {data[:100]}...")

                # 메시지 파싱 (JSON 또는 일반 텍스트)
                logger.info(f"[WS] 메시지 타입 분석 시작")
                try:
                    message_data = json.loads(data)
                    message_type = message_data.get("type", "chat")
                    user_message = message_data.get("message", data)
                    logger.info(f"[WS] JSON 메시지 파싱 성공: type={message_type}")
                    
                    # 히스토리 관련 명령 처리
                    if message_type == "get_history":
                        history = chat_history.get_history()
                        await websocket.send_text(
                            json.dumps({
                                "type": "history",
                                "data": history
                            })
                        )
                        continue
                    elif message_type == "clear_history":
                        chat_history.clear_history()
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
                    logger.info(f"[WS] 일반 텍스트 메시지로 처리")

                # 히스토리 컨텍스트 추가 (OpenAI 요약 사용)
                history_summary = ""  # 변수 초기화
                if chat_history.history:
                    # OpenAI로 히스토리 요약
                    try:
                        history_summary = await summarize_chat_history(chat_history.history, max_tokens=100)  # 80에서 100으로 증가
                        if history_summary and len(history_summary) > 10:  # 의미있는 요약인지 확인
                            enhanced_message = f"이전 대화 요약: {history_summary}\n\n현재 질문: {user_message}"
                            logger.info(f"[WS] OpenAI 히스토리 요약 사용 ({len(chat_history.history)}개 대화, {len(history_summary)}자)")
                        else:
                            # 요약 실패 시 간단한 대체 방법 사용
                            recent_chat = chat_history.history[-1]
                            simple_summary = f"마지막 질문: {recent_chat['query'][:50]}..."
                            enhanced_message = f"이전: {simple_summary}\n\n현재 질문: {user_message}"
                            logger.info(f"[WS] 간단한 히스토리 사용 ({len(chat_history.history)}개 대화)")
                    except Exception as e:
                        logger.warning(f"[WS] 히스토리 요약 실패, 요약 없이 진행: {e}")
                        logger.warning(f"[WS] Summary error type: {type(e).__name__}")
                        enhanced_message = user_message
                else:
                    enhanced_message = user_message

                # RunPod 서버에서 스트리밍 응답 생성
                try:
                    system_prompt = (
                        str(influencer.system_prompt)
                        if influencer and influencer.system_prompt
                        else "당신은 도움이 되는 AI 어시스턴트입니다."
                    )

                    # 스트리밍 응답 생성 (RunPod 사용)
                    token_count = 0
                    full_response = ""
                    
                    async for token in runpod_generate_text_stream(
                        prompt=enhanced_message,
                        lora_adapter=lora_repo_decoded,  # LoRA 어댑터 지정
                        system_message=system_prompt,
                        temperature=0.7,
                        max_tokens=512
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

                    # 히스토리에 대화 추가 (완료 후에만)
                    if full_response.strip():
                        model_info = {
                            "mode": "runpod",  # vllm → runpod 변경
                            "adapter": lora_repo_decoded,
                            "temperature": 0.7,
                            "influencer_name": str(influencer.influencer_name) if influencer else "한세나"
                        }
                        
                        chat_history.add_message(
                            query=user_message,
                            response=full_response,
                            context=history_summary if history_summary else "",  # 안전한 사용
                            model_info=model_info
                        )
                    
                    logger.info(
                        f"[WS] RunPod 스트리밍 응답 전송 완료 (토큰 수: {token_count}, 히스토리: {len(chat_history.history)}개)"
                    )

                except Exception as e:
                    logger.error(f"[WS] RunPod 스트리밍 추론 중 오류: {e}")
                    logger.error(f"[WS] Inference error type: {type(e).__name__}")
                    logger.error(f"[WS] LoRA adapter: {lora_repo_decoded}")
                    logger.error(f"[WS] User message: {user_message[:100]}..." if len(user_message) > 100 else f"[WS] User message: {user_message}")
                    import traceback
                    logger.error(f"[WS] Inference traceback:\n{traceback.format_exc()}")
                    await websocket.send_text(
                        json.dumps(
                            {
                                "type": "error",
                                "error_code": "RUNPOD_INFERENCE_ERROR",
                                "message": str(e),
                            }
                        )
                    )

            except WebSocketDisconnect:
                logger.info(f"[WS] WebSocket 연결 종료: lora_repo={lora_repo_decoded}, session_id={session_id}")
                logger.info(f"[WS] 총 처리된 메시지 수: {len(chat_history.history)}")
                break
            except Exception as e:
                logger.error(f"[WS] WebSocket 처리 중 오류: {e}")
                logger.error(f"[WS] Exception type: {type(e).__name__}")
                import traceback
                logger.error(f"[WS] Full traceback: {traceback.format_exc()}")
                logger.error(f"[WS] Current message: {data[:200]}..." if len(data) > 200 else f"[WS] Current message: {data}")
                await websocket.send_text(
                    json.dumps({"error_code": "WEBSOCKET_ERROR", "message": str(e)})
                )
                break

    except Exception as e:
        logger.error(f"[WS] ========== WebSocket 연결 처리 중 심각한 오류 ==========")
        logger.error(f"[WS] Error: {e}")
        logger.error(f"[WS] Exception type: {type(e).__name__}")
        import traceback
        logger.error(f"[WS] Full traceback:\n{traceback.format_exc()}")
        logger.error(f"[WS] Session ID: {session_id if 'session_id' in locals() else 'Not created'}")
        logger.error(f"[WS] ====================================================")
        try:
            await websocket.send_text(
                json.dumps({"error_code": "CONNECTION_ERROR", "message": str(e)})
            )
        except:
            logger.error(f"[WS] Failed to send error message to client")
    finally:
        # 데이터베이스 연결 정리
        try:
            if 'db' in locals():
                db.close()
                logger.info(f"[WS] 데이터베이스 연결 정리 완료")
        except Exception as e:
            logger.error(f"[WS] 데이터베이스 연결 정리 실패: {e}")


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
    """모델 로드 (RunPod 서버리스 사용)"""
    try:
        # HF 토큰 가져오기
        hf_token = await _get_hf_token_by_group(req.group_id, db)
        if not hf_token:
            raise HTTPException(status_code=400, detail="HF 토큰이 없습니다.")

        # RunPod 서버 상태 확인
        if not await runpod_health_check():
            raise HTTPException(
                status_code=503, detail="RunPod 서버에 연결할 수 없습니다."
            )

        # RunPod 서버리스는 어댑터 사전 로드가 필요하지 않음
        # 요청 시 동적으로 로드되므로 성공으로 반환
        logger.info(f"[MODEL LOAD API] RunPod 어댑터 준비 완료: {req.lora_repo}")
        return {
            "success": True,
            "message": "RunPod 서버에서 모델이 준비되었습니다. 요청 시 동적으로 로드됩니다.",
            "server_type": "runpod",
            "adapter_repo": req.lora_repo
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MODEL LOAD API] 모델 로드 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import HFTokenManage
from app.services.vllm_client import VLLMWebSocketClient, VLLMClient, get_vllm_client, vllm_health_check
from app.core.encryption import decrypt_sensitive_data
# MCP 클라이언트 추가
from app.services.mcp_client import mcp_client_service
import json
import logging
import base64
import asyncio
from app.core.config import settings

router = APIRouter()
logger = logging.getLogger(__name__)

class ModelLoadRequest(BaseModel):
    lora_repo: str
    group_id: int

@router.websocket("/chatbot/{lora_repo}")
async def chatbot(websocket: WebSocket, lora_repo: str, group_id: int = Query(...), influencer_id: str = Query(None), db: Session = Depends(get_db)):
    # lora_repo는 base64로 인코딩되어 있으므로 디코딩
    try:
        lora_repo_decoded = base64.b64decode(lora_repo).decode()
    except Exception as e:
        await websocket.accept()
        await websocket.send_text(json.dumps({"error_code": "LORA_REPO_DECODE_ERROR", "message": f"lora_repo 디코딩 실패: {e}"}))
        await websocket.close()
        return
    
    await websocket.accept()
    
    try:
        # VLLM 서버 상태 확인
        if not await vllm_health_check():
            logger.error(f"[WS] VLLM 서버 연결 실패 (URL: {settings.VLLM_BASE_URL})")
            await websocket.send_text(json.dumps({
                "error_code": "VLLM_SERVER_UNAVAILABLE", 
                "message": "VLLM 서버에 연결할 수 없습니다. 서버 상태를 확인해주세요."
            }))
            await websocket.close()
            return
        
        logger.info(f"[WS] VLLM WebSocket 연결 시작: lora_repo={lora_repo_decoded}, group_id={group_id}")
        
        # HF 토큰 가져오기
        hf_token = await _get_hf_token_by_group(group_id, db)

        if influencer_id:
            from app.models.influencer import AIInfluencer
            influencer = db.query(AIInfluencer).filter(AIInfluencer.influencer_id == influencer_id).first()
            if influencer and influencer.system_prompt is not None:
                system_prompt = str(influencer.system_prompt)
                logger.info(f"[WS] ✅ 저장된 시스템 프롬프트 사용: {influencer.influencer_name}")
            else:
                logger.info(f"[WS] ⚠️ 저장된 시스템 프롬프트가 없어 기본 시스템 프롬프트 사용")
        
        # VLLM 서버에 어댑터 로드
        vllm_client = await get_vllm_client()
        try:
            await vllm_client.load_adapter(lora_repo_decoded, lora_repo_decoded, hf_token)
            logger.info(f"[WS] VLLM 어댑터 로드 완료: {lora_repo_decoded}")
        except Exception as e:
            logger.error(f"[WS] VLLM 어댑터 로드 실패: {e}")
            await websocket.send_text(json.dumps({
                "error_code": "VLLM_ADAPTER_LOAD_FAILED", 
                "message": f"VLLM 어댑터 로드에 실패했습니다: {str(e)}"
            }))
            await websocket.close()
            return
        
        # MCP 도구들 초기화 (선택적)
        mcp_tools_available = False
        try:
            # MCP 서버 상태 확인
            math_tools = await mcp_client_service.list_available_tools("math")
            weather_tools = await mcp_client_service.list_available_tools("weather")
            mcp_tools_available = len(math_tools) > 0 or len(weather_tools) > 0
            if mcp_tools_available:
                logger.info(f"[WS] ✅ MCP 도구들 사용 가능: 수학({len(math_tools)}개), 날씨({len(weather_tools)}개)")
        except Exception as e:
            logger.warning(f"[WS] ⚠️ MCP 도구 초기화 실패: {e}")
        
        # WebSocket 프록시 모드
        while True:
            try:
                data = await websocket.receive_text()
                logger.info(f"[WS] 메시지 수신: {data[:100]}...")
                
                # JSON 메시지 파싱 시도
                try:
                    message_data = json.loads(data)
                    user_message = message_data.get("message", data)
                    use_mcp_tools = message_data.get("use_mcp_tools", True)
                except json.JSONDecodeError:
                    # 일반 텍스트 메시지로 처리 (하위 호환성)
                    user_message = data
                    use_mcp_tools = True
                
                # MCP 도구 사용 가능 여부 확인 및 처리
                if mcp_tools_available and use_mcp_tools and _should_use_mcp_tools(user_message):
                    try:
                        # MCP 도구를 사용한 응답 생성
                        mcp_response = await _process_with_mcp_tools(user_message)
                        await websocket.send_text(json.dumps({
                            "type": "mcp_response",
                            "content": mcp_response,
                            "tools_used": ["math", "weather"]
                        }))
                        logger.info(f"[WS] MCP 도구 응답 전송 완료")
                        continue
                    except Exception as e:
                        logger.warning(f"[WS] MCP 도구 처리 실패, VLLM으로 폴백: {e}")
                
                # VLLM 서버에서 스트리밍 응답 생성
                try:
                    vllm_client = await get_vllm_client()
                    system_prompt = str(influencer.system_prompt) if influencer and influencer.system_prompt else "당신은 도움이 되는 AI 어시스턴트입니다."
                    
                    # 스트리밍 응답 생성
                    token_count = 0
                    async for token in vllm_client.generate_response_stream(
                        user_message=user_message,
                        system_message=system_prompt,
                        influencer_name=str(influencer.influencer_name) if influencer else "한세나",
                        model_id=lora_repo_decoded,
                        max_new_tokens=512,
                        temperature=0.7
                    ):
                        # 각 토큰을 실시간으로 클라이언트에 전송
                        logger.debug(f"[WS] 토큰 전송: {repr(token)}")
                        await websocket.send_text(json.dumps({
                            "type": "token",
                            "content": token
                        }))
                        token_count += 1
                        
                        # 너무 많은 토큰이 오면 중단 (무한 루프 방지)
                        if token_count > 1000:
                            logger.warning(f"[WS] 토큰 수가 너무 많아 중단: {token_count}")
                            break
                    
                    # 스트리밍 완료 신호
                    await websocket.send_text(json.dumps({
                        "type": "complete",
                        "content": ""
                    }))
                    
                    logger.info(f"[WS] VLLM 스트리밍 응답 전송 완료 (토큰 수: {token_count})")
                    
                except Exception as e:
                    logger.error(f"[WS] VLLM 스트리밍 추론 중 오류: {e}")
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "error_code": "VLLM_INFERENCE_ERROR", 
                        "message": str(e)
                    }))
                    
            except WebSocketDisconnect:
                logger.info(f"[WS] WebSocket 연결 종료: lora_repo={lora_repo_decoded}")
                break
            except Exception as e:
                logger.error(f"[WS] WebSocket 처리 중 오류: {e}")
                await websocket.send_text(json.dumps({"error_code": "WEBSOCKET_ERROR", "message": str(e)}))
                break
                
    except Exception as e:
        logger.error(f"[WS] WebSocket 연결 처리 중 오류: {e}")
        try:
            await websocket.send_text(json.dumps({"error_code": "CONNECTION_ERROR", "message": str(e)}))
        except:
            pass

def _should_use_mcp_tools(message: str) -> bool:
    """메시지가 MCP 도구 사용이 필요한지 확인"""
    mcp_keywords = [
        "계산", "더하기", "빼기", "곱하기", "나누기", "제곱", "제곱근", "팩토리얼",
        "날씨", "기온", "습도", "강수", "바람", "자외선", "대기질", "일출", "일몰"
    ]
    message_lower = message.lower()
    return any(keyword in message_lower for keyword in mcp_keywords)

async def _process_with_mcp_tools(message: str) -> str:
    """MCP 도구를 사용하여 메시지 처리"""
    try:
        # LangChain React Agent를 사용하여 MCP 도구 실행
        from langchain_openai import ChatOpenAI
        from langchain.agents import AgentExecutor, create_react_agent
        from langchain.prompts import PromptTemplate
        
        # MCP 도구들 가져오기
        math_tools = await mcp_client_service.get_tools("math")
        weather_tools = await mcp_client_service.get_tools("weather")
        all_tools = math_tools + weather_tools
        
        if not all_tools:
            raise Exception("사용 가능한 MCP 도구가 없습니다.")
        
        # React 에이전트 생성
        llm = ChatOpenAI(model="gpt-4", temperature=0)
        agent = create_react_agent(
            llm,
            all_tools,
            prompt=PromptTemplate.from_template("당신은 도움이 되는 AI 어시스턴트입니다. 사용자의 질문에 적절한 도구를 사용하여 답변해주세요."),
        )
        agent_executor = AgentExecutor.from_agent_and_tools(
            agent=agent, tools=all_tools, verbose=True
        )
        
        # 에이전트 실행
        response = await agent_executor.ainvoke({"input": message})
        return response.get("output", str(response))
        
    except Exception as e:
        logger.error(f"MCP 도구 처리 중 오류: {e}")
        return f"MCP 도구 처리 중 오류가 발생했습니다: {str(e)}"

async def _get_hf_token_by_group(group_id: int, db: Session) -> str:
    """그룹 ID로 HF 토큰을 가져옵니다."""
    try:
        hf_token_manage = db.query(HFTokenManage).filter(
            HFTokenManage.group_id == group_id
        ).order_by(HFTokenManage.created_at.desc()).first()
        
        if hf_token_manage:
            return decrypt_sensitive_data(str(hf_token_manage.hf_token_value))
        else:
            logger.warning(f"그룹 {group_id}에 대한 HF 토큰을 찾을 수 없습니다.")
            return ""
    except Exception as e:
        logger.error(f"HF 토큰 가져오기 실패: {e}")
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
            raise HTTPException(status_code=503, detail="VLLM 서버에 연결할 수 없습니다.")
        
        # VLLM 서버에 어댑터 로드
        try:
            vllm_client = await get_vllm_client()
            await vllm_client.load_adapter(req.lora_repo, req.lora_repo, hf_token)
            logger.info(f"[MODEL LOAD API] VLLM 어댑터 로드 성공: {req.lora_repo}")
            return {
                "success": True, 
                "message": "VLLM 서버에서 모델이 성공적으로 로드되었습니다.",
                "server_type": "vllm"
            }
        except Exception as e:
            logger.error(f"[MODEL LOAD API] VLLM 어댑터 로드 실패: {e}")
            raise HTTPException(status_code=500, detail=f"VLLM 어댑터 로드 실패: {str(e)}")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"[MODEL LOAD API] 모델 로드 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))
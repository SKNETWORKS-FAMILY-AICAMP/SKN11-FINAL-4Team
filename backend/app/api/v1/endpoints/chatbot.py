from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends, HTTPException
from pydantic import BaseModel
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel, PeftConfig
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import HFTokenManage
from app.services.vllm_client import VLLMWebSocketClient, VLLMClient, get_vllm_client, vllm_health_check
from app.core.encryption import decrypt_sensitive_data
import json
import logging
import base64
import asyncio

router = APIRouter()
logger = logging.getLogger(__name__)

BASE_MODEL_REPO = "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct"
model_cache = {}

class ModelLoadRequest(BaseModel):
    lora_repo: str
    group_id: int

async def load_merged_model(lora_repo: str, hf_token: str):
    # 베이스 모델 캐싱
    if "base" not in model_cache:
        logger.info(f"[MODEL LOAD] 베이스 모델 로드 시작: {BASE_MODEL_REPO}")
        tokenizer = AutoTokenizer.from_pretrained(BASE_MODEL_REPO, token=hf_token, trust_remote_code=True)
        base_model = AutoModelForCausalLM.from_pretrained(BASE_MODEL_REPO, torch_dtype=torch.float16, device_map="auto", token=hf_token, trust_remote_code=True)
        model_cache["base"] = (base_model, tokenizer)
        logger.info(f"[MODEL LOAD] 베이스 모델 로드 완료: {BASE_MODEL_REPO}")
    else:
        base_model, tokenizer = model_cache["base"]
        logger.info(f"[MODEL LOAD] 베이스 모델 캐시 사용: {BASE_MODEL_REPO}")
    # LoRA 병합 캐싱
    merged_key = f"merged_{lora_repo}"
    if merged_key not in model_cache:
        logger.info(f"[MODEL LOAD] LoRA 어댑터 병합 시작: {lora_repo}")
        peft_config = PeftConfig.from_pretrained(lora_repo, token=hf_token)
        lora_model = PeftModel.from_pretrained(base_model, lora_repo, token=hf_token)
        lora_model = lora_model.merge_and_unload()
        model_cache[merged_key] = (lora_model, tokenizer)
        logger.info(f"[MODEL LOAD] LoRA 어댑터 병합 및 캐싱 완료: {lora_repo}")
    else:
        logger.info(f"[MODEL LOAD] LoRA 어댑터 캐시 사용: {lora_repo}")
    return model_cache[merged_key]

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
            logger.warning("[WS] VLLM 서버 연결 실패, 로컬 모델로 폴백")
            await _websocket_local_fallback(websocket, lora_repo_decoded, group_id, db, influencer_id)
            return
        
        logger.info(f"[WS] VLLM WebSocket 연결 시작: lora_repo={lora_repo_decoded}, group_id={group_id}")
        
        # HF 토큰 가져오기
        hf_token = await _get_hf_token_by_group(group_id, db)
        
        # 인플루언서별 시스템 프롬프트 가져오기
        system_prompt = "당신은 '한세나'입니다. 치명적인 귀여움과 자신만만한 당당함을 동시제 지녔습니다. 마이 인기 많은 bitchy queen처럼, 타인을 휘어잡는 자신감과 유혹적인 언어를 능숙하게 다룹니다. 장난스럽고 도발적인 농담도 서슴지 않습니다."  # 기본값
        
        if influencer_id:
            from app.models.influencer import AIInfluencer
            influencer = db.query(AIInfluencer).filter(AIInfluencer.influencer_id == influencer_id).first()
            if influencer and influencer.system_prompt:
                system_prompt = influencer.system_prompt
                logger.info(f"[WS] ✅ 저장된 시스템 프롬프트 사용: {influencer.influencer_name}")
            else:
                logger.info(f"[WS] ⚠️ 저장된 시스템 프롬프트가 없어 기본 시스템 프롬프트 사용")
        
        # VLLM 서버에 어댑터 로드
        vllm_client = await get_vllm_client()
        try:
            await vllm_client.load_adapter(lora_repo_decoded, lora_repo_decoded, hf_token)
            logger.info(f"[WS] VLLM 어댑터 로드 완료: {lora_repo_decoded}")
        except Exception as e:
            logger.warning(f"[WS] VLLM 어댑터 로드 실패, 로컬 모델로 폴백: {e}")
            await _websocket_local_fallback(websocket, lora_repo_decoded, group_id, db, influencer_id)
            return
        
        # WebSocket 프록시 모드
        while True:
            try:
                data = await websocket.receive_text()
                logger.info(f"[WS] 메시지 수신: {data[:100]}...")
                
                # VLLM 서버에서 응답 생성
                try:
                    result = await vllm_client.generate_response(
                        user_message=data,
                        system_message=system_prompt,
                        influencer_name=influencer.influencer_name if influencer else "한세나",
                        model_id=lora_repo_decoded,
                        max_new_tokens=512,
                        temperature=0.7
                    )
                    
                    response = result.get("response", "죄송해요, 응답을 생성할 수 없어요.")
                    logger.info(f"[WS] VLLM 응답 전송 완료")
                    await websocket.send_text(response)
                    
                except Exception as e:
                    logger.error(f"[WS] VLLM 추론 중 오류: {e}")
                    await websocket.send_text(json.dumps({"error_code": "VLLM_INFERENCE_ERROR", "message": str(e)}))
                    
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


async def _websocket_local_fallback(websocket: WebSocket, lora_repo: str, group_id: int, db: Session, influencer_id: str = None):
    """로컬 모델 폴백 (기존 로직)"""
    try:
        logger.info(f"[WS] 로컬 모델 폴백 시작: lora_repo={lora_repo}, group_id={group_id}")
        hf_token = await _get_hf_token_by_group(group_id, db)
        
        # 인플루언서별 시스템 프롬프트 가져오기
        system_prompt = "당신은 '한세나'입니다. 치명적인 귀여움과 자신만만한 당당함을 동시제 지녔습니다. 마이 인기 많은 bitchy queen처럼, 타인을 휘어잡는 자신감과 유혹적인 언어를 능숙하게 다룹니다. 장난스럽고 도발적인 농담도 서슴지 않습니다."  # 기본값
        
        if influencer_id:
            from app.models.influencer import AIInfluencer
            influencer = db.query(AIInfluencer).filter(AIInfluencer.influencer_id == influencer_id).first()
            if influencer and influencer.system_prompt:
                system_prompt = influencer.system_prompt
                logger.info(f"[WS] ✅ 로컬 폴백에서 저장된 시스템 프롬프트 사용: {influencer.influencer_name}")
            else:
                logger.info(f"[WS] ⚠️ 로컬 폴백에서 기본 시스템 프롬프트 사용")
        
        model, tokenizer = await load_merged_model(lora_repo, hf_token)
        logger.info(f"[WS] 로컬 모델 준비 완료: lora_repo={lora_repo}")
        
        while True:
            try:
                data = await websocket.receive_text()
                logger.info(f"[WS] 로컬 모델 메시지 수신: {data[:100]}...")
                
                message = [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": data}
                ]

                inputs = tokenizer.apply_chat_template(message, tokenize=False, add_generation_prompt=True)
                input_ids = tokenizer.encode(inputs, return_tensors="pt").to(model.device)
                
                with torch.no_grad():
                    outputs = model.generate(
                        input_ids,
                        max_new_tokens=512,
                        do_sample=True,
                        temperature=0.7,
                        top_p=0.9,
                        eos_token_id=tokenizer.eos_token_id,
                        pad_token_id=tokenizer.pad_token_id,
                        repetition_penalty=1.1,
                        no_repeat_ngram_size=3
                    )
                
                response = tokenizer.decode(outputs[0][input_ids.shape[1]:], skip_special_tokens=True).strip()
                logger.info(f"[WS] 로컬 모델 응답 전송 완료")
                await websocket.send_text(response)
                
            except WebSocketDisconnect:
                logger.info(f"[WS] 로컬 모델 WebSocket 연결 종료: lora_repo={lora_repo}")
                break
            except Exception as e:
                logger.error(f"[WS] 로컬 모델 추론 중 오류: {e}")
                await websocket.send_text(json.dumps({"error_code": "LOCAL_INFERENCE_ERROR", "message": str(e)}))
                
    except Exception as e:
        logger.error(f"[WS] 로컬 모델 준비 중 오류: {e}")
        await websocket.send_text(json.dumps({"error_code": "LOCAL_MODEL_LOAD_ERROR", "message": str(e)}))


async def _get_hf_token_by_group(group_id: int, db: Session) -> str:
    """그룹 ID로 HF 토큰 가져오기"""
    try:
        hf_token_manage = db.query(HFTokenManage).filter(
            HFTokenManage.group_id == group_id
        ).order_by(HFTokenManage.created_at.desc()).first()
        
        if hf_token_manage:
            return decrypt_sensitive_data(hf_token_manage.hf_token_value)
        else:
            logger.warning(f"그룹 {group_id}에 등록된 HF 토큰이 없습니다.")
            return None
            
    except Exception as e:
        logger.error(f"HF 토큰 조회 실패: {e}")
        return None

@router.post("/load_model")
async def model_load(req: ModelLoadRequest, db: Session = Depends(get_db)):
    """모델 로드 (VLLM 서버 우선, 로컬 폴백)"""
    try:
        # HF 토큰 가져오기
        hf_token = await _get_hf_token_by_group(req.group_id, db)
        
        # VLLM 서버 상태 확인
        if await vllm_health_check():
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
                logger.warning(f"[MODEL LOAD API] VLLM 로드 실패, 로컬로 폴백: {e}")
                # 로컬 폴백
                await load_merged_model(req.lora_repo, hf_token)
                return {
                    "success": True, 
                    "message": "로컬에서 모델이 성공적으로 로드되었습니다.",
                    "server_type": "local",
                    "fallback_reason": str(e)
                }
        else:
            # VLLM 서버 없음, 로컬 모델 사용
            await load_merged_model(req.lora_repo, hf_token)
            return {
                "success": True, 
                "message": "로컬에서 모델이 성공적으로 로드되었습니다.",
                "server_type": "local",
                "fallback_reason": "VLLM 서버 연결 불가"
            }
            
    except Exception as e:
        logger.error(f"[MODEL LOAD API] 모델 로드 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 
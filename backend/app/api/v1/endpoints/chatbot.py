from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query, Depends, HTTPException
from pydantic import BaseModel
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel, PeftConfig
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import HFTokenManage
import json
import logging
import base64

router = APIRouter()
logger = logging.getLogger(__name__)

BASE_MODEL_REPO = "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct"
model_cache = {}
# HARDCODED HUGGINGFACE TOKEN (임시)
# HARDCODED_HF_TOKEN = "token입력"

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
async def chatbot(websocket: WebSocket, lora_repo: str, group_id: int = Query(...), db: Session = Depends(get_db)):
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
        try:
            logger.info(f"[WS] WebSocket 연결 시작: lora_repo={lora_repo_decoded}, group_id={group_id}")
            hf_token = HARDCODED_HF_TOKEN
            model, tokenizer = await load_merged_model(lora_repo_decoded, hf_token)
            logger.info(f"[WS] WebSocket 연결 및 모델 준비 완료: lora_repo={lora_repo_decoded}, group_id={group_id}")
        except Exception as e:
            logger.error(f"[WS] 모델 준비 중 오류: {e}")
            await websocket.send_text(json.dumps({"error_code": "MODEL_LOAD_ERROR", "message": str(e)}))
            await websocket.close()
            return
        while True:
            try:
                data = await websocket.receive_text()
                logger.info(f"[WS] 메시지 수신: {data}")
                message = [
                    {"role": "system", "content": "당신은 '한세나'입니다. 치명적인 귀여움과 자신만만한 당당함을 동시제 지녔습니다. 마이 인기 많은 bitchy queen처럼, 타인을 휘어잡는 자신감과 유혹적인 언어를 능숙하게 다룹니다. 장난스럽고 도발적인 농담도 서슴지 않습니다."},
                    {"role": "user", "content": data}]

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
                logger.info(f"[WS] 모델 응답 전송 완료.")
                await websocket.send_text(response)
            except Exception as e:
                logger.error(f"[WS] 추론 중 오류: {e}")
                await websocket.send_text(json.dumps({"error_code": "INFERENCE_ERROR", "message": str(e)}))
    except WebSocketDisconnect:
        logger.info(f"[WS] WebSocket 연결 종료: lora_repo={lora_repo_decoded}, group_id={group_id}")
        pass

@router.post("/load_model")
async def model_load(req: ModelLoadRequest, db: Session = Depends(get_db)):
    try:
        hf_token = HARDCODED_HF_TOKEN
        await load_merged_model(req.lora_repo, hf_token)
        return {"success": True, "message": "모델이 성공적으로 로드되었습니다."}
    except Exception as e:
        logger.error(f"[MODEL LOAD API] 모델 로드 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e)) 
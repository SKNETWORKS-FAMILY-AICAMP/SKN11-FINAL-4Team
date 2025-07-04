from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List
from transformers import AutoModelForCausalLM, AutoTokenizer
from peft import PeftModel
import os
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.influencer import AIInfluencer
from app.models.user import HFTokenManage
from app.core.encryption import decrypt_sensitive_data
import re

router = APIRouter()

# 모델 id와 HuggingFace 모델 경로 매핑 예시
MODEL_MAP = {}

SYSTEM_PROMPT = ""


class InfluencerInfo(BaseModel):
    influencer_id: str
    influencer_model_repo: str


class MultiChatRequest(BaseModel):
    influencers: List[InfluencerInfo]
    message: str


class InfluencerResponse(BaseModel):
    influencer_id: str
    response: str


class MultiChatResponse(BaseModel):
    results: List[InfluencerResponse]


def normalize_text(text):
    return re.sub(r"\s+", " ", text).strip()


@router.post("/multi-chat", response_model=MultiChatResponse)
async def multi_chat(request: MultiChatRequest, db: Session = Depends(get_db)):
    results = []

    for influencer_info in request.influencers:
        try:
            # 데이터베이스에서 AI 인플루언서 정보 조회
            ai_influencer = (
                db.query(AIInfluencer)
                .filter(AIInfluencer.influencer_id == influencer_info.influencer_id)
                .first()
            )

            if not ai_influencer:
                results.append(
                    {
                        "influencer_id": influencer_info.influencer_id,
                        "response": "AI 인플루언서를 찾을 수 없습니다.",
                    }
                )
                continue

            # hf_manage_id가 없으면 오류
            if ai_influencer.hf_manage_id is None:
                results.append(
                    {
                        "influencer_id": influencer_info.influencer_id,
                        "response": "허깅페이스 토큰이 설정되지 않았습니다.",
                    }
                )
                continue

            # 허깅페이스 토큰 조회
            hf_token = (
                db.query(HFTokenManage)
                .filter(HFTokenManage.hf_manage_id == ai_influencer.hf_manage_id)
                .first()
            )

            if not hf_token:
                results.append(
                    {
                        "influencer_id": influencer_info.influencer_id,
                        "response": "허깅페이스 토큰을 찾을 수 없습니다.",
                    }
                )
                continue

            # 허깅페이스 토큰 복호화
            encrypted_token_value = getattr(hf_token, "hf_token_value", None)
            if not encrypted_token_value:
                results.append(
                    {
                        "influencer_id": influencer_info.influencer_id,
                        "response": "토큰 값이 없습니다.",
                    }
                )
                continue
            decrypted_token = decrypt_sensitive_data(encrypted_token_value)

            # 1. 인플루언서별 시스템 프롬프트 생성
            system_prompt = f"""
너는 {ai_influencer.influencer_name}라는 AI 인플루언서야.\n"""
            desc = getattr(ai_influencer, "influencer_description", None)
            if desc is not None and str(desc).strip() != "":
                system_prompt += f"설명: {desc}\n"
            personality = getattr(ai_influencer, "influencer_personality", None)
            if personality is not None and str(personality).strip() != "":
                system_prompt += f"성격: {personality}\n"
            system_prompt += "한국어로만 대답해.\n"

            # 2. 입력 메시지와 결합
            full_input = system_prompt + request.message

            # 1. 베이스 모델 로드 (공통 토큰 사용)
            base_model_name = "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct"
            base_model = AutoModelForCausalLM.from_pretrained(
                base_model_name, trust_remote_code=True, token=decrypted_token
            )
            tokenizer = AutoTokenizer.from_pretrained(
                base_model_name, trust_remote_code=True, token=decrypted_token
            )

            # 2. 어댑터(LoRA 등)만 로드해서 결합 (각 인플루언서별 어댑터 레포지토리에 접근 가능한 토큰 사용)
            adapter_repo = (
                influencer_info.influencer_model_repo
            )  # 어댑터 레포지토리 URL
            # adapter_access_token은 반드시 해당 어댑터 레포지토리에 접근 가능한 허깅페이스 토큰이어야 함
            adapter_access_token = (
                decrypted_token  # 실제로는 인플루언서별로 다를 수 있음
            )
            model = PeftModel.from_pretrained(
                base_model, adapter_repo, token=adapter_access_token
            )

            # 3. 텍스트 생성
            inputs = tokenizer(full_input, return_tensors="pt")
            outputs = model.generate(**inputs, max_new_tokens=50)
            answer = tokenizer.decode(outputs[0], skip_special_tokens=True)

            # 시스템 프롬프트+질문 부분 제거 (정규화 후 비교)
            norm_full_input = normalize_text(full_input)
            norm_answer = normalize_text(answer)

            if norm_answer.startswith(norm_full_input):
                # 원본 answer에서 정규화된 길이만큼 자르기 (정확한 위치 찾기)
                raw_idx = answer.find(full_input)
                if raw_idx != -1:
                    answer = answer[raw_idx + len(full_input) :].lstrip()
                else:
                    # fallback: 정규화된 길이 기준으로 자르기
                    answer = answer[len(full_input) :].lstrip()
            else:
                idx = norm_answer.find(norm_full_input)
                if idx != -1:
                    # 원본 answer에서 해당 위치를 찾아서 자름
                    raw_idx = answer.find(full_input)
                    if raw_idx != -1:
                        answer = answer[raw_idx + len(full_input) :].lstrip()
                    else:
                        answer = answer[idx + len(norm_full_input) :].lstrip()

            if not answer.strip():
                answer = tokenizer.decode(outputs[0], skip_special_tokens=True)

            results.append(
                {"influencer_id": influencer_info.influencer_id, "response": answer}
            )

        except Exception as e:
            results.append(
                {
                    "influencer_id": influencer_info.influencer_id,
                    "response": f"모델 오류: {str(e)}",
                }
            )

    return {"results": results}


# 해당 형식으로 POST 요청 보내야함
# {
#   "influencers": [
#     {
#       "influencer_id": "string",
#       "influencer_model_repo": "string"
#     },
#     {
#       "influencer_id": "string",
#       "influencer_model_repo": "string"
#     }
#   ],
#   "message": "string"
# }

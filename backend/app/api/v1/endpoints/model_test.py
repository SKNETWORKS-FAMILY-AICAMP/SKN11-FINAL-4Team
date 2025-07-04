from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List
from transformers.pipelines import pipeline
import os
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.influencer import AIInfluencer
from app.models.user import HFTokenManage

router = APIRouter()

# 모델 id와 HuggingFace 모델 경로 매핑 예시
MODEL_MAP = {}

SYSTEM_PROMPT = (
    "너는 친절하고 공손한 AI야. 항상 예의 바르게 대답해. 한국어로만 대답해\n"
)


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

            # 해당 인플루언서의 토큰으로 모델 로드 (환경변수 대신 직접 토큰 전달)
            nlp = pipeline(
                "text-generation",
                model=influencer_info.influencer_model_repo,
                token=str(hf_token.hf_token_value),  # 직접 토큰 전달
            )

            full_input = SYSTEM_PROMPT + request.message
            output = nlp(full_input, max_length=50)
            answer = output[0]["generated_text"]

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

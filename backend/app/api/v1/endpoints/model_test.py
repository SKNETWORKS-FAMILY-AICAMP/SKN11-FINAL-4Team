from fastapi import APIRouter
from pydantic import BaseModel
from typing import List
from transformers.pipelines import pipeline
import os

router = APIRouter()

# 모델 id와 HuggingFace 모델 경로 매핑 예시
MODEL_MAP = {
}

SYSTEM_PROMPT = "너는 친절하고 공손한 AI야. 항상 예의 바르게 대답해. 한국어로만 대답해\n"

class InfluencerInfo(BaseModel):
    influencer_id: str
    influencer_model_repo: str

class MultiChatRequest(BaseModel):
    influencers: List[InfluencerInfo]
    message: str
    hf_token: str  # 토큰 받을시

class InfluencerResponse(BaseModel):
    influencer_id: str
    response: str

class MultiChatResponse(BaseModel):
    results: List[InfluencerResponse]

@router.post("/multi-chat", response_model=MultiChatResponse)
async def multi_chat(request: MultiChatRequest):
    os.environ["HUGGINGFACE_HUB_TOKEN"] = request.hf_token  # 토큰 넣어줘야함
    results = []
    for influencer in request.influencers:
        try:
            nlp = pipeline("text-generation", model=influencer.influencer_model_repo)
            # 공통 시스템 프롬프트 적용
            full_input = SYSTEM_PROMPT + request.message
            output = nlp(full_input, max_length=50)
            answer = output[0]["generated_text"]
            results.append({"influencer_id": influencer.influencer_id, "response": answer})
        except Exception as e:
            results.append({"influencer_id": influencer.influencer_id, "response": f"모델 오류: {str(e)}"})
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
#   "message": "string",
#   "hf_token": "hf_xxxxxxxxxxxxxxxxxxxxx"  # 토큰 받을시
# }
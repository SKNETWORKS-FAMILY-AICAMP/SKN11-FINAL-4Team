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
from app.core.security import get_current_user
import re
from fastapi import HTTPException

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
async def multi_chat(request: MultiChatRequest, db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)):
    # 디버깅을 위한 로그 추가
    import logging
    logger = logging.getLogger(__name__)
    logger.info(f"Multi-chat request received: {request}")
    
    # 현재 사용자 정보
    user_id = current_user.get("sub")
    logger.info(f"Current user ID: {user_id}")
    
    # 사용자가 속한 그룹 ID 목록 조회
    from app.models.user import User
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    user_group_ids = [team.group_id for team in user.teams]
    logger.info(f"User belongs to groups: {user_group_ids}")
    
    results = []

    for influencer_info in request.influencers:
        logger.info(f"Processing influencer: {influencer_info.influencer_id}, repo: {influencer_info.influencer_model_repo}")
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

            # 그룹 권한 확인 - 사용자가 속한 그룹의 모델만 접근 가능
            if ai_influencer.group_id not in user_group_ids and ai_influencer.user_id != user_id:
                logger.warning(f"User {user_id} does not have access to influencer {influencer_info.influencer_id} in group {ai_influencer.group_id}")
                results.append(
                    {
                        "influencer_id": influencer_info.influencer_id,
                        "response": "해당 모델에 대한 접근 권한이 없습니다.",
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

            # 2. 채팅 템플릿 형식으로 메시지 구성
            messages = [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": request.message}
            ]
            
            # 채팅 템플릿 적용
            try:
                full_input = tokenizer.apply_chat_template(
                    messages, 
                    tokenize=False, 
                    add_generation_prompt=True
                )
            except Exception as template_error:
                logger.warning(f"Chat template failed, using simple concatenation: {template_error}")
                full_input = system_prompt + "\n\n사용자: " + request.message + "\n\n어시스턴트: "

            # 1. 베이스 모델 로드 (공통 토큰 사용)
            base_model_name = "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct"
            logger.info(f"Loading base model: {base_model_name}")
            
            try:
                base_model = AutoModelForCausalLM.from_pretrained(
                    base_model_name, trust_remote_code=True, token=decrypted_token
                )
                tokenizer = AutoTokenizer.from_pretrained(
                    base_model_name, trust_remote_code=True, token=decrypted_token
                )
                logger.info(f"Successfully loaded base model and tokenizer")
            except Exception as base_model_error:
                logger.error(f"Failed to load base model: {base_model_error}")
                results.append(
                    {
                        "influencer_id": influencer_info.influencer_id,
                        "response": f"베이스 모델 로딩 실패: {str(base_model_error)}",
                    }
                )
                continue

            # 2. 어댑터(LoRA 등)만 로드해서 결합 (각 인플루언서별 어댑터 레포지토리에 접근 가능한 토큰 사용)
            adapter_repo = (
                influencer_info.influencer_model_repo
            )  # 어댑터 레포지토리 URL
            
            # 어댑터 레포지토리가 비어있거나 유효하지 않은 경우 오류
            if not adapter_repo or adapter_repo.strip() == "":
                logger.error(f"Empty adapter repo for influencer {influencer_info.influencer_id}")
                results.append(
                    {
                        "influencer_id": influencer_info.influencer_id,
                        "response": "어댑터 레포지토리가 설정되지 않았습니다.",
                    }
                )
                continue
            
            # URL 형태의 레포지토리를 Hugging Face 레포지토리 형식으로 변환
            if adapter_repo.startswith("https://huggingface.co/models/"):
                adapter_repo = adapter_repo.replace("https://huggingface.co/models/", "")
            elif adapter_repo.startswith("https://huggingface.co/"):
                adapter_repo = adapter_repo.replace("https://huggingface.co/", "")
            
            # 임시로 테스트용 레포지토리 사용 (실제 레포지토리가 없을 경우)
            if adapter_repo in ["sample1", "sample2", "sample3"] or "sample" in adapter_repo:
                logger.warning(f"Using test repository for {influencer_info.influencer_id}")
                # 실제 유효한 Hugging Face 레포지토리로 대체 (테스트용)
                adapter_repo = "microsoft/DialoGPT-medium"  # 임시 테스트용
            
            logger.info(f"Processed adapter repo: {adapter_repo}")
            
            # 어댑터 로딩 시도
            try:
                logger.info(f"Loading adapter from: {adapter_repo}")
                # adapter_access_token은 반드시 해당 어댑터 레포지토리에 접근 가능한 허깅페이스 토큰이어야 함
                adapter_access_token = decrypted_token
                
                # PeftConfig를 먼저 로드하여 어댑터 설정 확인
                from peft import PeftConfig
                try:
                    peft_config = PeftConfig.from_pretrained(adapter_repo, token=adapter_access_token)
                    logger.info(f"Successfully loaded PeftConfig from {adapter_repo}")
                    logger.info(f"Adapter config: {peft_config}")
                    
                    # 어댑터 설정 유효성 검사
                    if not hasattr(peft_config, 'base_model_name_or_path'):
                        logger.warning(f"PeftConfig missing base_model_name_or_path")
                    
                except Exception as config_error:
                    logger.error(f"Failed to load PeftConfig from {adapter_repo}: {config_error}")
                    results.append(
                        {
                            "influencer_id": influencer_info.influencer_id,
                            "response": f"어댑터 설정 로딩 실패: {str(config_error)}",
                        }
                    )
                    continue
                
                # 어댑터 모델 로딩
                logger.info(f"Loading PeftModel from {adapter_repo}")
                model = PeftModel.from_pretrained(
                    base_model, adapter_repo, token=adapter_access_token
                )
                logger.info(f"Successfully loaded adapter from {adapter_repo}")
                
                # 모델이 제대로 로드되었는지 확인
                if model is None:
                    raise Exception("PeftModel loading returned None")
                
                logger.info(f"Adapter model loaded successfully for {influencer_info.influencer_id}")
                
            except Exception as adapter_error:
                logger.error(f"Failed to load adapter from {adapter_repo}: {adapter_error}")
                results.append(
                    {
                        "influencer_id": influencer_info.influencer_id,
                        "response": f"어댑터 로딩 실패: {str(adapter_error)}",
                    }
                )
                continue

            # 3. 텍스트 생성
            logger.info(f"Generating text for influencer {influencer_info.influencer_id}")
            try:
                inputs = tokenizer(full_input, return_tensors="pt")
                outputs = model.generate(**inputs, max_new_tokens=100)
                full_response = tokenizer.decode(outputs[0], skip_special_tokens=True)
                logger.info(f"Successfully generated text for influencer {influencer_info.influencer_id}")
                
                # 시스템 프롬프트와 사용자 메시지 제거하여 순수 응답만 추출
                logger.info(f"Full response: {full_response}")
                logger.info(f"Full input: {full_input}")
                
                # 개선된 응답 추출 로직
                answer = full_response
                
                # 1. 어시스턴트 응답 마커로 정확한 응답 부분 추출
                assistant_markers = [
                    "어시스턴트:", "Assistant:", "assistant:", 
                    "AI:", "ai:", "답변:", "응답:"
                ]
                
                found_assistant_response = False
                for marker in assistant_markers:
                    if marker in answer:
                        parts = answer.split(marker)
                        if len(parts) > 1:
                            answer = parts[-1].strip()
                            found_assistant_response = True
                            logger.info(f"Found assistant response with marker '{marker}': {answer}")
                            break
                
                # 2. 어시스턴트 마커가 없는 경우, 입력 프롬프트 제거
                if not found_assistant_response:
                    # 입력 프롬프트에서 시스템 프롬프트 부분만 정확히 제거
                    system_prompt_clean = system_prompt.strip()
                    if system_prompt_clean in answer:
                        # 시스템 프롬프트 이후 부분만 추출
                        system_start = answer.find(system_prompt_clean)
                        if system_start != -1:
                            after_system = answer[system_start + len(system_prompt_clean):].strip()
                            # 사용자 메시지도 제거
                            user_message_clean = request.message.strip()
                            if user_message_clean in after_system:
                                user_start = after_system.find(user_message_clean)
                                if user_start != -1:
                                    answer = after_system[user_start + len(user_message_clean):].strip()
                                else:
                                    answer = after_system
                            else:
                                answer = after_system
                    
                    # 입력 프롬프트 전체가 포함된 경우 제거
                    if full_input in answer:
                        answer = answer.replace(full_input, "").strip()
                
                # 3. 정확한 시스템 프롬프트 패턴만 제거 (실제 답변 보존)
                import re
                
                # 정확한 시스템 프롬프트 패턴만 제거
                exact_system_patterns = [
                    r"^너는.*?AI 인플루언서야\.\s*",  # 시작 부분의 시스템 프롬프트
                    r"설명:.*?\n",  # 설명 라인
                    r"성격:.*?\n",  # 성격 라인
                    r"한국어로만 대답해\.\s*",  # 언어 지시
                ]
                
                for pattern in exact_system_patterns:
                    answer = re.sub(pattern, "", answer, flags=re.DOTALL)
                
                # 4. 연속된 공백과 불필요한 문장 부호 정리
                answer = re.sub(r'\s+', ' ', answer)
                answer = answer.strip('.,!? \n')
                
                # 5. 빈 응답인 경우 전체 응답 사용
                if not answer.strip():
                    answer = full_response
                    logger.warning(f"Empty answer after cleaning, using full response")
                
                # 6. 최종 정리
                answer = answer.strip()
                
                # 7. 응답이 너무 짧은 경우 처리 (실제 답변이 아닌 경우만)
                if len(answer) < 5:
                    # 전체 응답에서 마지막 부분만 사용
                    lines = full_response.split('\n')
                    for line in reversed(lines):
                        line = line.strip()
                        if line and len(line) > 5 and not any(marker in line for marker in assistant_markers):
                            answer = line
                            break
                
                logger.info(f"Final extracted answer: {answer}")
                
            except Exception as generation_error:
                logger.error(f"Text generation failed for influencer {influencer_info.influencer_id}: {generation_error}")
                results.append(
                    {
                        "influencer_id": influencer_info.influencer_id,
                        "response": f"텍스트 생성 실패: {str(generation_error)}",
                    }
                )
                continue

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

    response = {"results": results}
    logger.info(f"Multi-chat response: {response}")
    return response


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

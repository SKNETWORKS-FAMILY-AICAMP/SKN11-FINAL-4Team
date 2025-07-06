from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from enum import Enum
from pipeline.speech_generator import Gender # Gender Enum은 speech_generator에서 가져옴

# 파인튜닝 상태 Enum
class FineTuningStatus(Enum):
    PENDING = "pending"
    PREPARING_DATA = "preparing_data"
    TRAINING = "training"
    UPLOADING = "uploading"
    COMPLETED = "completed"
    FAILED = "failed"

# 요청 모델 정의
class LoRALoadRequest(BaseModel):
    model_id: str  # 어댑터를 식별할 ID
    hf_repo_name: str  # 허깅페이스 레포 이름
    hf_token: Optional[str] = None  # 허깅페이스 액세스 토큰
    base_model_override: Optional[str] = None  # 베이스 모델 오버라이드

class GenerateRequest(BaseModel):
    user_message: str
    system_message: str = "당신은 도움이 되는 AI 어시스턴트입니다."
    influencer_name: str = "어시스턴트"
    model_id: Optional[str] = None  # 사용할 LoRA 어댑터 ID
    max_new_tokens: int = 150
    temperature: float = 0.7
    do_sample: bool = True
    use_chat_template: bool = True

class GenerateResponse(BaseModel):
    response: str
    model_id: Optional[str]
    used_adapter: bool
    formatted_prompt: str
    raw_response: str

class FineTuningRequest(BaseModel):
    influencer_id: str
    influencer_name: str
    personality: str
    qa_data: List[Dict[str, Any]]
    hf_repo_id: str
    hf_token: str
    training_epochs: int = 5
    style_info: Optional[str] = ""

class FineTuningResponse(BaseModel):
    task_id: str
    status: str
    message: str
    hf_repo_id: Optional[str] = None

class FineTuningStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    hf_model_url: Optional[str] = None

# Speech Generator 관련 모델
class VLLMCharacterProfile(BaseModel):
    name: str
    description: str
    age_range: Optional[str] = None
    gender: Gender
    personality: str
    mbti: Optional[str] = None

    class Config:
        use_enum_values = True

class VLLMQAGenerationResponse(BaseModel):
    question: str
    responses: Dict[str, List[Dict[str, Any]]]

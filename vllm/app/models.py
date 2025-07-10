from pydantic import BaseModel, Field, validator
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
    is_converted: Optional[bool] = False
    batch_id: Optional[str] = None

class FineTuningResponse(BaseModel):
    task_id: str
    status: str
    message: str
    hf_repo_id: Optional[str] = None
    batch_id: Optional[str] = None

class FineTuningStatusResponse(BaseModel):
    task_id: str
    status: str
    progress: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    hf_model_url: Optional[str] = None
    batch_id: Optional[str] = None

# Speech Generator 관련 모델
class VLLMCharacterProfile(BaseModel):
    name: str
    description: str
    age_range: Optional[str] = None
    gender: Gender
    personality: str
    mbti: Optional[str] = None

    @validator('gender', pre=True)
    def convert_gender_to_korean_enum(cls, v):
        if isinstance(v, str):
            v_lower = v.lower()
            if v_lower == 'male':
                return Gender.MALE
            elif v_lower == 'female':
                return Gender.FEMALE
            elif v_lower in ['non_binary', 'none']:
                return Gender.NON_BINARY
        return v

    class Config:
        use_enum_values = True

class VLLMQAGenerationResponse(BaseModel):
    question: str
    responses: Dict[str, List[Dict[str, Any]]]

# 배치 처리 관련 모델
class VLLMBatchQARequest(BaseModel):
    characters: List[VLLMCharacterProfile]
    num_qa_per_character: int = 1

class VLLMBatchQAResponse(BaseModel):
    results: List[VLLMQAGenerationResponse]
    total_processed: int
    success_count: int
    error_count: int
    errors: List[str] = []

# 질문 생성 전용 모델
class VLLMQuestionRequest(BaseModel):
    character: VLLMCharacterProfile
    num_questions: int = 1

class VLLMQuestionResponse(BaseModel):
    questions: List[str]
    character_name: str

class VLLMBatchQuestionRequest(BaseModel):
    characters: List[VLLMCharacterProfile]
    num_questions_per_character: int = 1

class VLLMBatchQuestionResponse(BaseModel):
    results: List[VLLMQuestionResponse]
    total_processed: int
    success_count: int
    error_count: int
    errors: List[str] = []

# 말투 생성 전용 모델
class VLLMToneRequest(BaseModel):
    character: VLLMCharacterProfile
    questions: List[str]
    num_tone_variations: int = 3

class VLLMToneResponse(BaseModel):
    responses: Dict[str, Dict[str, List[Dict[str, Any]]]]  # {question: {tone_name: [responses]}}
    character_name: str

class VLLMBatchToneRequest(BaseModel):
    requests: List[VLLMToneRequest]

class VLLMBatchToneResponse(BaseModel):
    results: List[VLLMToneResponse]
    total_processed: int
    success_count: int
    error_count: int
    errors: List[str] = []

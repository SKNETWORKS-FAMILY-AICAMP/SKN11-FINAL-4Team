from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime
from app.schemas.base import BaseSchema, TimestampSchema


# ModelMBTI 스키마
class ModelMBTIBase(BaseModel):
    mbti_name: str
    mbti_traits: str
    mbti_speech: str


class ModelMBTICreate(ModelMBTIBase):
    pass


class ModelMBTIUpdate(BaseModel):
    mbti_name: Optional[str] = None
    mbti_traits: Optional[str] = None
    mbti_speech: Optional[str] = None


class ModelMBTI(ModelMBTIBase):
    mbti_id: int


# StylePreset 스키마
class StylePresetBase(BaseModel):
    style_preset_name: str
    influencer_type: int
    influencer_gender: int
    influencer_age_group: int
    influencer_hairstyle: str
    influencer_style: str
    influencer_personality: str
    influencer_speech: str


class StylePresetCreate(StylePresetBase):
    pass


class StylePresetUpdate(BaseModel):
    style_preset_name: Optional[str] = None
    influencer_type: Optional[int] = None
    influencer_gender: Optional[int] = None
    influencer_age_group: Optional[int] = None
    influencer_hairstyle: Optional[str] = None
    influencer_style: Optional[str] = None
    influencer_personality: Optional[str] = None
    influencer_speech: Optional[str] = None


class StylePreset(StylePresetBase, TimestampSchema):
    style_preset_id: str


# AIInfluencer 스키마
class AIInfluencerBase(BaseModel):
    user_id: str
    group_id: int
    style_preset_id: str
    mbti_id: Optional[int] = None
    influencer_name: str
    influencer_description: Optional[str] = None
    image_url: Optional[str] = None
    influencer_data_url: Optional[str] = None
    learning_status: int
    influencer_model_repo: str
    chatbot_option: bool


class AIInfluencerCreate(BaseSchema):
    user_id: str
    group_id: int
    style_preset_id: Optional[str] = None  # 프리셋이 없으면 자동 생성
    mbti_id: Optional[int] = None
    hf_manage_id: Optional[str] = None  # 허깅페이스 토큰 관리 ID
    influencer_name: str
    influencer_description: Optional[str] = None
    image_url: Optional[str] = None
    influencer_data_url: Optional[str] = None
    learning_status: int = 0
    influencer_model_repo: str = ""
    chatbot_option: bool = True
    
    # 프리셋 자동 생성을 위한 추가 필드들
    personality: Optional[str] = None  # 성격
    tone: Optional[str] = None         # 말투
    model_type: Optional[str] = None   # 모델 타입
    mbti: Optional[str] = None         # MBTI
    gender: Optional[str] = None       # 성별
    age: Optional[str] = None          # 나이
    hair_style: Optional[str] = None   # 헤어스타일
    mood: Optional[str] = None         # 분위기/스타일


class AIInfluencerUpdate(BaseModel):
    style_preset_id: Optional[str] = None
    mbti_id: Optional[int] = None
    hf_manage_id: Optional[str] = None
    influencer_name: Optional[str] = None
    influencer_description: Optional[str] = None
    image_url: Optional[str] = None
    influencer_data_url: Optional[str] = None
    learning_status: Optional[int] = None
    influencer_model_repo: Optional[str] = None
    chatbot_option: Optional[bool] = None


class AIInfluencer(AIInfluencerBase, TimestampSchema):
    influencer_id: str
    style_preset: Optional[StylePreset] = None
    mbti: Optional[ModelMBTI] = None


class AIInfluencerWithDetails(AIInfluencer):
    style_preset: Optional[StylePreset] = None
    mbti: Optional[ModelMBTI] = None


# BatchKey 스키마
class BatchKeyBase(BaseModel):
    influencer_id: str
    batch_key: str


class BatchKeyCreate(BatchKeyBase):
    pass


class BatchKey(BatchKeyBase):
    batch_key_id: str


# ChatMessage 스키마
class ChatMessageBase(BaseModel):
    influencer_id: str
    message_content: str
    end_at: datetime


class ChatMessageCreate(ChatMessageBase):
    pass


class ChatMessage(ChatMessageBase):
    session_id: int
    created_at: datetime


# InfluencerAPI 스키마
class InfluencerAPIBase(BaseModel):
    influencer_id: str
    api_value: str


class InfluencerAPICreate(InfluencerAPIBase):
    pass


class InfluencerAPIUpdate(BaseModel):
    api_value: Optional[str] = None


class InfluencerAPI(InfluencerAPIBase, TimestampSchema):
    api_id: str


# APICallAggregation 스키마
class APICallAggregationBase(BaseModel):
    api_id: str
    influencer_id: str
    daily_call_count: int


class APICallAggregationCreate(APICallAggregationBase):
    pass


class APICallAggregationUpdate(BaseModel):
    daily_call_count: Optional[int] = None


class APICallAggregation(APICallAggregationBase, TimestampSchema):
    api_call_id: str

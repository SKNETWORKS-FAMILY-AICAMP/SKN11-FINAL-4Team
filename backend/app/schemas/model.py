from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ModelBase(BaseModel):
    group_uuid: str
    mbti_id: int
    model_name: str
    model_description: Optional[str] = None
    model_personality: str
    model_speaks: str
    model_repo: str
    image_url: Optional[str] = None
    model_status: int = 0
    model_data_url: Optional[str] = None


class ModelCreate(BaseModel):
    group_uuid: str = Field(..., description="그룹 UUID")
    mbti_id: int = Field(..., description="MBTI ID")
    model_name: str = Field(..., min_length=1, max_length=100, description="모델 이름")
    model_description: Optional[str] = Field(None, description="모델 설명")
    model_personality: str = Field(
        ..., min_length=1, max_length=50, description="모델 성격"
    )
    model_speaks: str = Field(..., min_length=1, max_length=50, description="모델 말투")
    model_repo: str = Field(
        ..., min_length=1, max_length=255, description="모델 저장소"
    )
    image_url: Optional[str] = Field(None, max_length=255, description="이미지 URL")
    model_status: int = Field(
        0, ge=0, le=1, description="모델 상태 (0: 학습 중, 1: 사용가능)"
    )
    model_data_url: Optional[str] = Field(
        None, max_length=255, description="모델 데이터 URL"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "group_uuid": "550e8400-e29b-41d4-a716-446655440000",
                "mbti_id": 1,
                "model_name": "친근한 AI 어시스턴트",
                "model_description": "사용자와 친근하게 대화하는 AI 모델",
                "model_personality": "친근하고 도움이 되는",
                "model_speaks": "정중한 존댓말",
                "model_repo": "huggingface/friendly-ai-assistant",
                "model_status": 1,
            }
        }


class ModelUpdate(BaseModel):
    model_name: Optional[str] = Field(
        None, min_length=1, max_length=100, description="모델 이름"
    )
    model_description: Optional[str] = Field(None, description="모델 설명")
    model_personality: Optional[str] = Field(
        None, min_length=1, max_length=50, description="모델 성격"
    )
    model_speaks: Optional[str] = Field(
        None, min_length=1, max_length=50, description="모델 말투"
    )
    model_repo: Optional[str] = Field(
        None, min_length=1, max_length=255, description="모델 저장소"
    )
    image_url: Optional[str] = Field(None, max_length=255, description="이미지 URL")
    model_status: Optional[int] = Field(None, ge=0, le=1, description="모델 상태")
    model_data_url: Optional[str] = Field(
        None, max_length=255, description="모델 데이터 URL"
    )

    class Config:
        json_schema_extra = {
            "example": {"model_description": "업데이트된 모델 설명", "model_status": 1}
        }


class ModelResponse(BaseModel):
    model_uuid: str
    group_uuid: str
    mbti_id: int
    model_name: str
    model_description: Optional[str]
    model_personality: str
    model_speaks: str
    model_repo: str
    image_url: Optional[str]
    model_status: int
    model_data_url: Optional[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ModelDeleteRequest(BaseModel):
    force_delete: bool = Field(False, description="관련 데이터와 함께 강제 삭제")
    reason: Optional[str] = Field(None, max_length=500, description="삭제 사유")

    class Config:
        json_schema_extra = {
            "example": {"force_delete": False, "reason": "테스트 모델이므로 삭제"}
        }


class ModelDeleteResponse(BaseModel):
    message: str
    model_uuid: str
    model_name: str
    force_delete: bool
    deleted_at: datetime

    class Config:
        json_schema_extra = {
            "example": {
                "message": "Model deleted successfully",
                "model_uuid": "550e8400-e29b-41d4-a716-446655440000",
                "model_name": "테스트 모델",
                "force_delete": False,
                "deleted_at": "2024-01-01T12:00:00",
            }
        }


class ModelSecurityAudit(BaseModel):
    model_uuid: str
    model_name: str
    related_boards: int
    related_apis: int
    can_delete: bool
    requires_force_delete: bool
    security_warnings: List[str] = []

    class Config:
        json_schema_extra = {
            "example": {
                "model_uuid": "550e8400-e29b-41d4-a716-446655440000",
                "model_name": "테스트 모델",
                "related_boards": 5,
                "related_apis": 2,
                "can_delete": False,
                "requires_force_delete": True,
                "security_warnings": ["Model has active boards", "Model has API calls"],
            }
        }

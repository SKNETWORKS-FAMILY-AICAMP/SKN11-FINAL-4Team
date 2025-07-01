from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.database import get_db
from app.models.influencer import AIInfluencer, StylePreset, ModelMBTI
from app.models.user import User
from app.schemas.influencer import (
    AIInfluencerCreate,
    AIInfluencerUpdate,
    AIInfluencer as AIInfluencerSchema,
    AIInfluencerWithDetails,
    StylePresetCreate,
    StylePreset as StylePresetSchema,
    ModelMBTI as ModelMBTISchema,
)
from app.core.security import get_current_user

router = APIRouter()


@router.get("/", response_model=List[AIInfluencerSchema])
async def get_influencers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """사용자별 AI 인플루언서 목록 조회"""
    user_id = current_user.get("sub")
    
    # 사용자 정보 가져오기
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    
    # 사용자의 팀에 속한 모델들 조회
    user_group_ids = [group.group_id for group in user.groups]
    
    print(user_group_ids)
    query = db.query(AIInfluencer)
    if user_group_ids:
        # 팀이 있는 경우: 팀에 속한 모델들 + 본인이 생성한 모델들
        query = query.filter(
            (AIInfluencer.group_id.in_(user_group_ids)) |
            (AIInfluencer.user_id == user_id)
        )
    else:
        # 팀이 없는 경우: 본인이 생성한 모델들만
        query = query.filter(AIInfluencer.user_id == user_id)
    
    influencers = query.offset(skip).limit(limit).all()
    return influencers


@router.get("/{influencer_id}", response_model=AIInfluencerWithDetails)
async def get_influencer(
    influencer_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """특정 AI 인플루언서 조회"""
    user_id = current_user.get("sub")
    
    # 사용자 정보 가져오기
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    print(user)
    # 사용자의 팀에 속한 모델들 조회
    user_group_ids = [group.group_id for group in user.groups]
    
    query = db.query(AIInfluencer).filter(AIInfluencer.influencer_id == influencer_id)
    if user_group_ids:
        # 팀이 있는 경우: 팀에 속한 모델들 + 본인이 생성한 모델들
        query = query.filter(
            (AIInfluencer.group_id.in_(user_group_ids)) |
            (AIInfluencer.user_id == user_id)
        )
    else:
        # 팀이 없는 경우: 본인이 생성한 모델들만
        query = query.filter(AIInfluencer.user_id == user_id)
    
    influencer = query.first()

    if influencer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Influencer not found"
        )
    return influencer


@router.post("/", response_model=AIInfluencerSchema)
async def create_influencer(
    influencer_data: AIInfluencerCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """새 AI 인플루언서 생성"""
    user_id = current_user.get("sub")
    
    # 스타일 프리셋 존재 확인
    style_preset = (
        db.query(StylePreset)
        .filter(StylePreset.style_preset_id == influencer_data.style_preset_id)
        .first()
    )
    if style_preset is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Style preset not found"
        )

    # MBTI 존재 확인 (선택사항)
    if influencer_data.mbti_id:
        mbti = (
            db.query(ModelMBTI)
            .filter(ModelMBTI.mbti_id == influencer_data.mbti_id)
            .first()
        )
        if mbti is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="MBTI not found"
            )

    influencer = AIInfluencer(
        influencer_id=str(uuid.uuid4()),
        user_id=user_id,
        **influencer_data.dict()
    )

    db.add(influencer)
    db.commit()
    db.refresh(influencer)

    return influencer


@router.put("/{influencer_id}", response_model=AIInfluencerSchema)
async def update_influencer(
    influencer_id: str,
    influencer_update: AIInfluencerUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI 인플루언서 정보 수정"""
    influencer = (
        db.query(AIInfluencer)
        .filter(
            AIInfluencer.influencer_id == influencer_id,
            AIInfluencer.user_id == current_user.user_id,
        )
        .first()
    )

    if influencer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Influencer not found"
        )

    # 업데이트할 필드들
    update_data = influencer_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(influencer, field, value)

    db.commit()
    db.refresh(influencer)
    return influencer


@router.delete("/{influencer_id}")
async def delete_influencer(
    influencer_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """AI 인플루언서 삭제"""
    influencer = (
        db.query(AIInfluencer)
        .filter(
            AIInfluencer.influencer_id == influencer_id,
            AIInfluencer.user_id == current_user.user_id,
        )
        .first()
    )

    if influencer is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Influencer not found"
        )

    db.delete(influencer)
    db.commit()

    return {"message": "Influencer deleted successfully"}


# 스타일 프리셋 관련 API
@router.get("/style-presets/", response_model=List[StylePresetSchema])
async def get_style_presets(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """스타일 프리셋 목록 조회"""
    presets = db.query(StylePreset).offset(skip).limit(limit).all()
    return presets


@router.post("/style-presets/", response_model=StylePresetSchema)
async def create_style_preset(
    preset_data: StylePresetCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """새 스타일 프리셋 생성"""
    preset = StylePreset(style_preset_id=str(uuid.uuid4()), **preset_data.dict())

    db.add(preset)
    db.commit()
    db.refresh(preset)

    return preset


# MBTI 관련 API
@router.get("/mbti/", response_model=List[ModelMBTISchema])
async def get_mbti_list(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """MBTI 목록 조회"""
    mbti_list = db.query(ModelMBTI).all()
    return mbti_list

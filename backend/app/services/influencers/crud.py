from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from typing import List
import uuid

from app.models.influencer import AIInfluencer, StylePreset, ModelMBTI
from app.models.user import User
from app.schemas.influencer import AIInfluencerCreate, AIInfluencerUpdate


def get_user_group_ids(db: Session, user_id: str) -> List[str]:
    """사용자의 그룹 ID 목록을 반환"""
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    return [group.group_id for group in user.groups]


def build_influencer_query(db: Session, user_id: str, influencer_id: str = None):
    """사용자 권한에 따른 인플루언서 쿼리 생성"""
    user_group_ids = get_user_group_ids(db, user_id)
    
    query = db.query(AIInfluencer)
    if influencer_id:
        query = query.filter(AIInfluencer.influencer_id == influencer_id)
    
    if user_group_ids:
        query = query.filter(
            (AIInfluencer.group_id.in_(user_group_ids)) |
            (AIInfluencer.user_id == user_id)
        )
    else:
        query = query.filter(AIInfluencer.user_id == user_id)
    
    return query


def get_influencers_list(db: Session, user_id: str, skip: int = 0, limit: int = 100):
    """사용자별 AI 인플루언서 목록 조회"""
    query = build_influencer_query(db, user_id)
    return query.offset(skip).limit(limit).all()


def get_influencer_by_id(db: Session, user_id: str, influencer_id: str):
    """특정 AI 인플루언서 조회"""
    query = build_influencer_query(db, user_id, influencer_id)
    influencer = query.first()
    
    if not influencer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Influencer not found"
        )
    
    return influencer


def create_influencer(db: Session, user_id: str, influencer_data: AIInfluencerCreate):
    """새 AI 인플루언서 생성"""
    # 스타일 프리셋 존재 확인
    style_preset = (
        db.query(StylePreset)
        .filter(StylePreset.style_preset_id == influencer_data.style_preset_id)
        .first()
    )
    if not style_preset:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, 
            detail="Style preset not found"
        )

    # MBTI 존재 확인 (선택사항)
    if influencer_data.mbti_id:
        mbti = (
            db.query(ModelMBTI)
            .filter(ModelMBTI.mbti_id == influencer_data.mbti_id)
            .first()
        )
        if not mbti:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="MBTI not found"
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


def update_influencer(db: Session, user_id: str, influencer_id: str, influencer_update: AIInfluencerUpdate):
    """AI 인플루언서 정보 수정"""
    influencer = get_influencer_by_id(db, user_id, influencer_id)

    # 업데이트할 필드들
    update_data = influencer_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(influencer, field, value)

    db.commit()
    db.refresh(influencer)
    return influencer


def delete_influencer(db: Session, user_id: str, influencer_id: str):
    """AI 인플루언서 삭제"""
    influencer = get_influencer_by_id(db, user_id, influencer_id)

    db.delete(influencer)
    db.commit()

    return {"message": "Influencer deleted successfully"}
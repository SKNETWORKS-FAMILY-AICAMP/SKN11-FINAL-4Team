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
    from app.services.influencers.style_presets import create_style_preset
    from app.schemas.influencer import StylePresetCreate
    
    # 스타일 프리셋 처리
    style_preset_id = influencer_data.style_preset_id
    
    if not style_preset_id:
        # 프리셋이 없으면 현재 값으로 자동 생성
        if not influencer_data.personality or not influencer_data.tone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="성격과 말투가 필요합니다. 프리셋을 지정하거나 성격과 말투를 입력해주세요."
            )
        
        # 모델 타입별 기본값 매핑
        model_type_mapping = {
            "character": 1,  # 캐릭터형
            "human": 2,      # 사람형 
            "objects": 3     # 사물형
        }
        
        gender_mapping = {
            "male": 1,
            "female": 2,
            "other": 3
        }
        
        # 나이 그룹 매핑 (기본값: 2)
        age_group = 2  # 20-30대
        if influencer_data.age:
            try:
                age_num = int(influencer_data.age)
                if age_num < 20:
                    age_group = 1
                elif age_num < 40:
                    age_group = 2  
                elif age_num < 60:
                    age_group = 3
                else:
                    age_group = 4
            except ValueError:
                age_group = 2
        
        # 프리셋 생성
        preset_data = StylePresetCreate(
            style_preset_name=f"{influencer_data.influencer_name}_자동생성프리셋",
            influencer_type=model_type_mapping.get(influencer_data.model_type, 2),
            influencer_gender=gender_mapping.get(influencer_data.gender, 2),
            influencer_age_group=age_group,
            influencer_hairstyle=influencer_data.hair_style or "기본 헤어스타일",
            influencer_style=influencer_data.mood or "자연스럽고 편안한",
            influencer_personality=influencer_data.personality,
            influencer_speech=influencer_data.tone
        )
        
        style_preset = create_style_preset(db, preset_data)
        style_preset_id = style_preset.style_preset_id
    else:
        # 기존 프리셋 존재 확인
        style_preset = (
            db.query(StylePreset)
            .filter(StylePreset.style_preset_id == style_preset_id)
            .first()
        )
        if not style_preset:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Style preset not found"
            )

    # MBTI 처리
    mbti_id = influencer_data.mbti_id
    if influencer_data.mbti and not mbti_id:
        # MBTI 문자열로부터 ID 찾기
        mbti_record = (
            db.query(ModelMBTI)
            .filter(ModelMBTI.mbti_name == influencer_data.mbti)
            .first()
        )
        if mbti_record:
            mbti_id = mbti_record.mbti_id
    
    # MBTI 존재 확인 (선택사항)
    if mbti_id:
        mbti = (
            db.query(ModelMBTI)
            .filter(ModelMBTI.mbti_id == mbti_id)
            .first()
        )
        if not mbti:
            # MBTI가 없으면 None으로 설정
            mbti_id = None

    # 인플루언서 생성 데이터 준비
    influencer_create_data = {
        "influencer_id": str(uuid.uuid4()),
        "user_id": user_id,
        "group_id": influencer_data.group_id,
        "style_preset_id": style_preset_id,
        "mbti_id": mbti_id,
        "influencer_name": influencer_data.influencer_name,
        "influencer_description": influencer_data.influencer_description,
        "image_url": influencer_data.image_url,
        "influencer_data_url": influencer_data.influencer_data_url,
        "learning_status": influencer_data.learning_status,
        "influencer_model_repo": influencer_data.influencer_model_repo,
        "chatbot_option": influencer_data.chatbot_option
    }

    influencer = AIInfluencer(**influencer_create_data)

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
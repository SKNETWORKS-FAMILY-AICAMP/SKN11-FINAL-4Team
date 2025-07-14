from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models.influencer import AIInfluencer, ModelMBTI, StylePreset
from app.schemas.influencer import AIInfluencerCreate, AIInfluencerUpdate
from fastapi import HTTPException, status
import uuid
import logging

logger = logging.getLogger(__name__)


def get_influencer_by_id(db: Session, user_id: str, influencer_id: str):
    """인플루언서 조회 (권한 체크 포함)"""
    from app.models.user import User

    # 사용자 정보 조회 (팀 정보 포함)
    user = db.query(User).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # 사용자가 속한 그룹 ID 목록
    user_group_ids = [team.group_id for team in user.teams] if user.teams else []

    # 인플루언서 조회 (권한 체크 포함)
    query = db.query(AIInfluencer).filter(AIInfluencer.influencer_id == influencer_id)

    # 권한 체크: 사용자가 속한 그룹의 인플루언서이거나 사용자가 직접 소유한 인플루언서
    if user_group_ids:
        query = query.filter(
            (AIInfluencer.group_id.in_(user_group_ids))
            | (AIInfluencer.user_id == user_id)
        )
    else:
        # 그룹이 없는 경우 사용자가 직접 소유한 인플루언서만
        query = query.filter(AIInfluencer.user_id == user_id)

    influencer = query.first()
    if not influencer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Influencer not found or access denied",
        )

    return influencer


def get_influencers_list(db: Session, user_id: str, skip: int = 0, limit: int = 100):
    # This part needs to be implemented based on your permission logic
    return db.query(AIInfluencer).offset(skip).limit(limit).all()


def create_influencer(db: Session, user_id: str, influencer_data: AIInfluencerCreate):
    """새 AI 인플루언서 생성"""
    logger.info(
        f"🎨 인플루언서 생성 시작 - user_id: {user_id}, name: {influencer_data.influencer_name}"
    )

    from app.services.influencers.style_presets import create_style_preset
    from app.schemas.influencer import StylePresetCreate

    # 스타일 프리셋 처리
    style_preset_id = influencer_data.style_preset_id
    logger.debug(f"선택된 프리셋 ID: {style_preset_id}")

    # 프리셋 ID가 제공되지 않은 경우, 직접 입력된 정보로 프리셋을 생성하거나 직접 필드를 사용
    if not style_preset_id:
        # 성격과 말투가 모두 제공된 경우에만 새로운 StylePreset을 생성
        if influencer_data.personality and influencer_data.tone:
            logger.info("📝 프리셋이 선택되지 않아 직접 입력된 정보로 자동 생성합니다")

            from app.utils.data_mapping import DataMapper

            # 데이터 매핑 유틸리티 사용
            age_group = DataMapper.map_age_to_group(influencer_data.age)

            # 프리셋 생성
            preset_data = StylePresetCreate(
                style_preset_name=f"{influencer_data.influencer_name}_자동생성프리셋",
                influencer_type=DataMapper.map_model_type_to_db(
                    influencer_data.model_type
                ),
                influencer_gender=DataMapper.map_gender_to_db(influencer_data.gender),
                influencer_age_group=age_group,
                influencer_hairstyle=influencer_data.hair_style or "기본 헤어스타일",
                influencer_style=influencer_data.mood or "자연스럽고 편안한",
                influencer_personality=influencer_data.personality,
                influencer_speech=influencer_data.tone,
            )

            style_preset = create_style_preset(db, preset_data)
            style_preset_id = style_preset.style_preset_id
            logger.info(f"✅ 자동 프리셋 생성 완료: {style_preset_id}")
        else:
            logger.info(
                "⚠️ 프리셋이 선택되지 않았고, 성격/말투 정보도 없어 프리셋을 생성하지 않습니다."
            )
            style_preset_id = None  # 명시적으로 None으로 설정
    else:
        logger.info(f"🎯 기존 프리셋 사용: {style_preset_id}")
        # 기존 프리셋 존재 확인
        style_preset = (
            db.query(StylePreset)
            .filter(StylePreset.style_preset_id == style_preset_id)
            .first()
        )
        if not style_preset:
            logger.error(f"❌ 프리셋을 찾을 수 없음: {style_preset_id}")
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Style preset not found"
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
        mbti = db.query(ModelMBTI).filter(ModelMBTI.mbti_id == mbti_id).first()
        if not mbti:
            # MBTI가 없으면 None으로 설정
            mbti_id = None

    # 허깅페이스 토큰 ID 검증 (빈 문자열이나 "none"인 경우 None으로 처리)
    hf_manage_id = influencer_data.hf_manage_id
    if hf_manage_id in ["", "none", None]:
        hf_manage_id = None
    else:
        # 허깅페이스 토큰 존재 확인
        from app.models.user import HFTokenManage

        hf_token = (
            db.query(HFTokenManage)
            .filter(HFTokenManage.hf_manage_id == hf_manage_id)
            .first()
        )
        if not hf_token:
            logger.warning(f"⚠️ 지정된 허깅페이스 토큰을 찾을 수 없음: {hf_manage_id}")
            hf_manage_id = None

    # 말투 정보 처리
    final_system_prompt = influencer_data.system_prompt
    if influencer_data.tone_type and influencer_data.tone_data:
        logger.info(f"📝 말투 정보 처리: type={influencer_data.tone_type}")
        final_system_prompt = influencer_data.tone_data

    # 인플루언서 생성 데이터 준비
    influencer_create_data = {
        "influencer_id": str(uuid.uuid4()),
        "user_id": user_id,
        "group_id": influencer_data.group_id,
        "style_preset_id": style_preset_id,  # 이제 None이 될 수 있음
        "mbti_id": mbti_id,
        "hf_manage_id": hf_manage_id,  # 검증된 허깅페이스 토큰 ID
        "influencer_name": influencer_data.influencer_name,
        "influencer_description": influencer_data.influencer_description,
        "image_url": influencer_data.image_url,
        "influencer_data_url": influencer_data.influencer_data_url,
        "learning_status": influencer_data.learning_status,
        "influencer_model_repo": influencer_data.influencer_model_repo,
        "chatbot_option": influencer_data.chatbot_option,
        # AIInfluencer 모델의 직접 필드 채우기
        "influencer_personality": influencer_data.personality,
        "influencer_tone": influencer_data.tone,
        "influencer_age_group": None,  # 초기화 후 아래에서 매핑
        "system_prompt": final_system_prompt,
    }

    # 스키마의 age를 모델의 influencer_age_group으로 매핑
    influencer_create_data["influencer_age_group"] = DataMapper.map_age_to_group(
        influencer_data.age
    )

    try:
        influencer = AIInfluencer(**influencer_create_data)
        db.add(influencer)
        db.commit()
        db.refresh(influencer)
    except IntegrityError as e:
        db.rollback()
        if "Duplicate entry" in str(e) and "influencer_name" in str(e):
            logger.error(
                f"❌ 중복된 인플루언서 이름: {influencer_data.influencer_name}"
            )
            raise HTTPException(
                status_code=400,
                detail=f"이미 존재하는 인플루언서 이름입니다: {influencer_data.influencer_name}",
            )
        else:
            logger.error(f"❌ 인플루언서 생성 중 데이터베이스 오류: {e}")
            raise HTTPException(
                status_code=500, detail="인플루언서 생성 중 오류가 발생했습니다."
            )

    logger.info(
        f"🎉 인플루언서 생성 완료 - ID: {influencer.influencer_id}, 이름: {influencer.influencer_name}"
    )
    return influencer


def update_influencer(
    db: Session, user_id: str, influencer_id: str, influencer_update: AIInfluencerUpdate
):
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

    # 연관된 BatchKey 데이터 삭제
    from app.models.influencer import BatchKey

    db.query(BatchKey).filter(BatchKey.influencer_id == influencer_id).delete()
    logger.info(f"🗑️ 인플루언서 {influencer_id}와 연관된 BatchKey 데이터 삭제 완료")

    db.delete(influencer)
    db.commit()

    logger.info(f"✅ 인플루언서 {influencer_id} 삭제 완료")
    return {"message": "Influencer deleted successfully"}

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timedelta

from app.core.social_auth import SocialAuthService
from app.models.influencer import AIInfluencer
from app.models.user import User


class InstagramConnectRequest(BaseModel):
    code: str
    redirect_uri: str


def get_user_with_teams(db: Session, user_id: str):
    """사용자 정보와 팀 정보를 조회"""
    from sqlalchemy.orm import joinedload
    
    user = db.query(User).options(joinedload(User.teams)).filter(User.user_id == user_id).first()
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found"
        )
    return user


def get_influencer_with_permission(db: Session, user_id: str, influencer_id: str):
    """권한 확인 후 인플루언서 조회"""
    user = get_user_with_teams(db, user_id)
    user_group_ids = [team.group_id for team in user.teams]
    
    query = db.query(AIInfluencer).filter(AIInfluencer.influencer_id == influencer_id)
    if user_group_ids:
        query = query.filter(
            (AIInfluencer.group_id.in_(user_group_ids)) |
            (AIInfluencer.user_id == user_id)
        )
    else:
        query = query.filter(AIInfluencer.user_id == user_id)
    
    influencer = query.first()
    if not influencer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Influencer not found or access denied"
        )
    
    return influencer


async def connect_instagram_account(db: Session, user_id: str, influencer_id: str, request: InstagramConnectRequest):
    """AI 인플루언서에 Instagram 비즈니스 계정 연동"""
    influencer = get_influencer_with_permission(db, user_id, influencer_id)
    
    # Instagram OAuth 토큰 교환
    social_auth = SocialAuthService()
    try:
        instagram_data = await social_auth.exchange_instagram_business_code(request.code, request.redirect_uri)
    except HTTPException as e:
        raise e
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Failed to connect Instagram account: {str(e)}"
        )
    
    # 디버깅 로그 추가
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"📋 Instagram 연동 데이터:")
    logger.info(f"   - 전체 instagram_data: {instagram_data}")
    logger.info(f"   - id: {instagram_data.get('id')}")
    logger.info(f"   - access_token 존재: {bool(instagram_data.get('access_token'))}")
    
    # Instagram 비즈니스 연동 데이터에서 바로 정보 추출
    # exchange_instagram_business_code에서 이미 모든 정보를 가져왔음
    instagram_id = instagram_data.get("id")
    instagram_page_id = instagram_data.get("page_id")  # Facebook 페이지 ID (웹훅용)
    instagram_username = instagram_data.get("username") or f"user_{instagram_id}"
    instagram_account_type = instagram_data.get("account_type", "BUSINESS")
    
    # 추가 정보들 (Instagram Graph API에서 가져온 정보)
    name = instagram_data.get("name")
    biography = instagram_data.get("biography")
    followers_count = instagram_data.get("followers_count", 0)
    follows_count = instagram_data.get("follows_count", 0)
    media_count = instagram_data.get("media_count", 0)
    profile_picture_url = instagram_data.get("profile_picture_url")
    website = instagram_data.get("website")
    
    logger.info(f"💾 데이터베이스에 저장할 값들:")
    print(f"🔍 DEBUG influencer: {instagram_data}")
    logger.info(f"   - instagram_id: {instagram_id}")
    logger.info(f"   - instagram_page_id: {instagram_page_id}")
    logger.info(f"   - instagram_username: {instagram_username}")
    logger.info(f"   - instagram_account_type: {instagram_account_type}")
    
    influencer.instagram_id = instagram_id
    influencer.instagram_page_id = instagram_page_id
    influencer.instagram_username = instagram_username
    influencer.instagram_account_type = instagram_account_type
    influencer.instagram_access_token = instagram_data.get("access_token")
    influencer.instagram_connected_at = datetime.utcnow()
    influencer.instagram_is_active = True
    
    # 토큰 만료 시간 계산 (expires_in은 초 단위)
    expires_in_seconds = instagram_data.get("expires_in", 3600)
    influencer.instagram_token_expires_at = datetime.utcnow() + timedelta(seconds=expires_in_seconds)
    
    db.commit()
    db.refresh(influencer)
    
    # Instagram 연동 완료 후 vLLM 어댑터 로드 요청
    await _load_vllm_adapter_for_influencer(influencer, db)
    
    # 실시간으로 Instagram 사용자 정보 조회
    try:
        user_info = await social_auth.get_instagram_user_info(
            influencer.instagram_id, 
            influencer.instagram_access_token
        )
        
        return {
            "message": "Instagram business account connected successfully",
            "instagram_info": user_info
        }
    except Exception:
        return {
            "message": "Instagram business account connected successfully",
            "instagram_info": None
        }


def disconnect_instagram_account(db: Session, user_id: str, influencer_id: str):
    """AI 인플루언서에서 Instagram 비즈니스 계정 연동 해제"""
    influencer = get_influencer_with_permission(db, user_id, influencer_id)
    
    # Instagram 연동 정보 제거 (모든 필드)
    influencer.instagram_id = None
    influencer.instagram_page_id = None
    influencer.instagram_username = None
    influencer.instagram_account_type = None
    influencer.instagram_access_token = None
    influencer.instagram_connected_at = None
    influencer.instagram_token_expires_at = None
    influencer.instagram_is_active = False
    
    db.commit()
    
    return {"message": "Instagram business account disconnected successfully"}


async def get_instagram_status(db: Session, user_id: str, influencer_id: str):
    """AI 인플루언서의 Instagram 연동 상태 조회"""
    influencer = get_influencer_with_permission(db, user_id, influencer_id)
    
    # 토큰 만료 확인
    token_expired = False
    if influencer.instagram_token_expires_at:
        token_expired = datetime.utcnow() > influencer.instagram_token_expires_at
    
    # 연동되어 있고 토큰이 유효한 경우 실시간 정보 조회
    instagram_info = None
    if influencer.instagram_is_active and not token_expired and influencer.instagram_access_token:
        try:
            social_auth = SocialAuthService()
            instagram_info = await social_auth.get_instagram_user_info(
                influencer.instagram_id, 
                influencer.instagram_access_token
            )
        except Exception:
            # API 호출 실패 시 토큰 만료로 간주
            token_expired = True
    
    return {
        "is_connected": influencer.instagram_is_active or False,
        "instagram_id": influencer.instagram_id,
        "instagram_page_id": influencer.instagram_page_id,
        "instagram_username": influencer.instagram_username,
        "instagram_account_type": influencer.instagram_account_type,
        "connected_at": influencer.instagram_connected_at.isoformat() if influencer.instagram_connected_at else None,
        "token_expires_at": influencer.instagram_token_expires_at.isoformat() if influencer.instagram_token_expires_at else None,
        "token_expired": token_expired,
        "instagram_info": instagram_info
    }


async def _load_vllm_adapter_for_influencer(influencer, db: Session):
    """Instagram 연동된 인플루언서의 vLLM 어댑터 로드"""
    import logging
    logger = logging.getLogger(__name__)
    
    # 파인튜닝된 모델이 있는지 확인
    if not influencer.influencer_model_repo:
        logger.info(f"🤖 {influencer.influencer_name}: 파인튜닝된 모델이 없어 어댑터 로드를 건너뜁니다.")
        return False
    
    try:
        # vLLM 클라이언트 및 어댑터 로드 함수 import
        from app.services.vllm_operations import vllm_load_adapter_if_needed, get_hf_token_from_influencer_group
        
        logger.info(f"📲 {influencer.influencer_name}: Instagram 연동 완료, vLLM 어댑터 로드 시작")
        logger.info(f"   - 모델 리포지토리: {influencer.influencer_model_repo}")
        
        # 허깅페이스 토큰 조회
        hf_token = await get_hf_token_from_influencer_group(influencer, db)
        
        # 어댑터 로드 요청
        adapter_loaded = await vllm_load_adapter_if_needed(
            model_id=str(influencer.influencer_id),  # 인플루언서 ID를 어댑터 식별자로 사용
            hf_repo_name=influencer.influencer_model_repo,  # 실제 HuggingFace 레포지토리 경로
            hf_token=hf_token
        )
        
        if adapter_loaded:
            logger.info(f"✅ {influencer.influencer_name}: vLLM 어댑터 로드 성공")
        else:
            logger.warning(f"⚠️ {influencer.influencer_name}: vLLM 어댑터 로드 실패")
        
        return adapter_loaded
        
    except Exception as e:
        logger.error(f"❌ {influencer.influencer_name}: vLLM 어댑터 로드 중 오류 발생: {str(e)}")
        return False


async def load_adapters_for_active_instagram_influencers(db: Session):
    """활성화된 Instagram 연동 인플루언서들의 vLLM 어댑터 자동 로드"""
    import logging
    logger = logging.getLogger(__name__)
    
    try:
        # Instagram이 활성화되고 파인튜닝된 모델이 있는 인플루언서 조회
        from app.models.influencer import AIInfluencer
        
        active_influencers = (
            db.query(AIInfluencer)
            .filter(
                AIInfluencer.instagram_is_active == True,
                AIInfluencer.influencer_model_repo.isnot(None),
                AIInfluencer.influencer_model_repo != ""
            )
            .all()
        )
        
        if not active_influencers:
            logger.info("📱 Instagram 연동된 파인튜닝 인플루언서가 없습니다.")
            return
        
        logger.info(f"📱 Instagram 활성화된 인플루언서 {len(active_influencers)}개의 vLLM 어댑터 로드 시작")
        
        # 각 인플루언서의 어댑터 로드
        for influencer in active_influencers:
            await _load_vllm_adapter_for_influencer(influencer, db)
        
        logger.info("✅ Instagram 연동 인플루언서들의 vLLM 어댑터 로드 완료")
        
    except Exception as e:
        logger.error(f"❌ Instagram 연동 인플루언서 어댑터 로드 중 오류: {str(e)}")
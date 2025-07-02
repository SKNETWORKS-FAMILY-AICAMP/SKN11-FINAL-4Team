from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Dict

from app.database import get_db
from app.models.influencer import AIInfluencer
from app.schemas.instagram import (
    InstagramConnectRequest, 
    InstagramConnectResponse, 
    InstagramDisconnectRequest,
    InstagramStatus,
    InstagramAccountInfo
)
from app.core.instagram_service import InstagramService
from app.core.security import get_current_user

router = APIRouter()
instagram_service = InstagramService()

@router.post("/connect", response_model=InstagramConnectResponse)
async def connect_instagram_account(
    request: InstagramConnectRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """AI 인플루언서 모델에 인스타그램 계정 연동"""
    try:
        # 인플루언서 모델 존재 및 소유권 확인
        influencer = (
            db.query(AIInfluencer)
            .filter(
                AIInfluencer.influencer_id == request.influencer_id,
                AIInfluencer.user_id == current_user.get("sub")
            )
            .first()
        )
        
        if not influencer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="AI 인플루언서 모델을 찾을 수 없거나 접근 권한이 없습니다."
            )
        
        # 이미 연동된 계정이 있는지 확인
        if influencer.instagram_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이미 인스타그램 계정이 연동되어 있습니다. 먼저 연동을 해제하세요."
            )
        
        # 인스타그램 계정 정보 가져오기
        account_info = await instagram_service.connect_instagram_account(
            request.code, 
            request.redirect_uri
        )
        
        # 다른 인플루언서가 같은 인스타그램 계정을 사용하는지 확인
        existing_connection = (
            db.query(AIInfluencer)
            .filter(AIInfluencer.instagram_id == account_info["instagram_id"])
            .first()
        )
        
        if existing_connection:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="이 인스타그램 계정은 이미 다른 AI 인플루언서에 연동되어 있습니다."
            )
        
        # 인플루언서 모델에 인스타그램 정보 저장
        influencer.instagram_id = account_info["instagram_id"]
        influencer.instagram_username = account_info["username"]
        influencer.instagram_access_token = account_info["access_token"]
        influencer.instagram_account_type = account_info["account_type"]
        influencer.instagram_connected_at = datetime.utcnow()
        influencer.instagram_is_active = True
        
        db.commit()
        db.refresh(influencer)
        
        return InstagramConnectResponse(
            success=True,
            message="인스타그램 계정이 성공적으로 연동되었습니다.",
            account_info=InstagramAccountInfo(
                instagram_id=account_info["instagram_id"],
                username=account_info["username"],
                account_type=account_info["account_type"],
                media_count=account_info["media_count"],
                is_business_account=account_info["is_business_account"]
            )
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"인스타그램 계정 연동에 실패했습니다: {str(e)}"
        )

@router.post("/disconnect")
async def disconnect_instagram_account(
    request: InstagramDisconnectRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """AI 인플루언서 모델에서 인스타그램 계정 연동 해제"""
    try:
        # 인플루언서 모델 존재 및 소유권 확인
        influencer = (
            db.query(AIInfluencer)
            .filter(
                AIInfluencer.influencer_id == request.influencer_id,
                AIInfluencer.user_id == current_user.get("sub")
            )
            .first()
        )
        
        if not influencer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="AI 인플루언서 모델을 찾을 수 없거나 접근 권한이 없습니다."
            )
        
        if not influencer.instagram_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="연동된 인스타그램 계정이 없습니다."
            )
        
        # 인스타그램 연동 정보 제거
        influencer.instagram_id = None
        influencer.instagram_username = None
        influencer.instagram_access_token = None
        influencer.instagram_account_type = None
        influencer.instagram_connected_at = None
        influencer.instagram_is_active = False
        
        db.commit()
        
        return {"success": True, "message": "인스타그램 계정 연동이 해제되었습니다."}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"인스타그램 계정 연동 해제에 실패했습니다: {str(e)}"
        )

@router.get("/status/{influencer_id}", response_model=InstagramStatus)
async def get_instagram_status(
    influencer_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """AI 인플루언서의 인스타그램 연동 상태 조회"""
    try:
        # 인플루언서 모델 존재 및 소유권 확인
        influencer = (
            db.query(AIInfluencer)
            .filter(
                AIInfluencer.influencer_id == influencer_id,
                AIInfluencer.user_id == current_user.get("sub")
            )
            .first()
        )
        
        if not influencer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="AI 인플루언서 모델을 찾을 수 없거나 접근 권한이 없습니다."
            )
        
        return InstagramStatus(
            is_connected=bool(influencer.instagram_id),
            instagram_username=influencer.instagram_username,
            account_type=influencer.instagram_account_type,
            connected_at=influencer.instagram_connected_at,
            is_active=influencer.instagram_is_active or False
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"인스타그램 연동 상태 조회에 실패했습니다: {str(e)}"
        )

@router.post("/verify/{influencer_id}")
async def verify_instagram_connection(
    influencer_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """인스타그램 연동 상태 검증"""
    try:
        # 인플루언서 모델 존재 및 소유권 확인
        influencer = (
            db.query(AIInfluencer)
            .filter(
                AIInfluencer.influencer_id == influencer_id,
                AIInfluencer.user_id == current_user.get("sub")
            )
            .first()
        )
        
        if not influencer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="AI 인플루언서 모델을 찾을 수 없거나 접근 권한이 없습니다."
            )
        
        if not influencer.instagram_id or not influencer.instagram_access_token:
            return {"is_valid": False, "message": "인스타그램 계정이 연동되어 있지 않습니다."}
        
        # 토큰 유효성 검증
        is_valid = await instagram_service.verify_instagram_token(
            influencer.instagram_access_token,
            influencer.instagram_id
        )
        
        if not is_valid:
            # 토큰이 무효하면 연동 비활성화
            influencer.instagram_is_active = False
            db.commit()
            
            return {"is_valid": False, "message": "인스타그램 토큰이 만료되었습니다. 다시 연동해주세요."}
        
        return {"is_valid": True, "message": "인스타그램 연동이 정상적으로 작동합니다."}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"인스타그램 연동 검증에 실패했습니다: {str(e)}"
        )
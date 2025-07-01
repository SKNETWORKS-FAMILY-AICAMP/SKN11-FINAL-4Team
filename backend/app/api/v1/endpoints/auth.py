from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from datetime import timedelta
from typing import Dict
import uuid

from app.database import get_db
from app.models.user import User
from app.schemas.user import User as UserSchema, UserWithTeams
from app.schemas.auth import SocialLoginRequest, TokenResponse, UserInfo
from app.core.config import settings
from app.core.security import create_access_token, generate_jwt_payload, get_current_user
from app.core.social_auth import SocialAuthService

router = APIRouter()

social_auth_service = SocialAuthService()


@router.post("/social-login", response_model=TokenResponse)
async def social_login(request: SocialLoginRequest, db: Session = Depends(get_db)):
    """Social login with Google and Naver support"""
    try:
        user_info = await social_auth_service.process_social_login(
            provider=request.provider,
            code=request.code,
            redirect_uri=request.redirect_uri,
            user_info=request.user_info
        )
        
        # 먼저 provider_id와 provider로 기존 사용자 확인
        user = (
            db.query(User)
            .filter(User.provider_id == user_info["id"], User.provider == request.provider)
            .first()
        )
        
        if not user:
            # 이메일로 기존 사용자 확인 (다른 소셜 제공자로 가입한 경우)
            if user_info.get("email"):
                existing_user_by_email = (
                    db.query(User)
                    .filter(User.email == user_info["email"])
                    .first()
                )
                
                if existing_user_by_email:
                    # 기존 사용자가 있으면 해당 사용자 정보 업데이트
                    existing_user_by_email.provider_id = user_info["id"]
                    existing_user_by_email.provider = request.provider
                    existing_user_by_email.user_name = user_info.get("name") or user_info.get("username", existing_user_by_email.user_name)
                    db.commit()
                    db.refresh(existing_user_by_email)
                    user = existing_user_by_email
                else:
                    # 새 사용자 생성
                    try:
                        user = User(
                            user_id=str(uuid.uuid4()),
                            provider_id=user_info["id"],
                            provider=request.provider,
                            user_name=user_info.get("name") or user_info.get("username", f"User_{request.provider}"),
                            email=user_info.get("email") or f"{user_info['id']}_{request.provider}@example.com",
                        )
                        db.add(user)
                        db.commit()
                        db.refresh(user)
                    except Exception as db_error:
                        db.rollback()
                        # 혹시 동시성 문제로 중복이 발생한 경우 다시 조회
                        user = (
                            db.query(User)
                            .filter(User.provider_id == user_info["id"], User.provider == request.provider)
                            .first()
                        )
                        if not user:
                            raise HTTPException(
                                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail=f"Failed to create user: {str(db_error)}"
                            )
            else:
                # 이메일이 없는 경우 새 사용자 생성
                try:
                    user = User(
                        user_id=str(uuid.uuid4()),
                        provider_id=user_info["id"],
                        provider=request.provider,
                        user_name=user_info.get("name") or user_info.get("username", f"User_{request.provider}"),
                        email=user_info.get("email") or f"{user_info['id']}_{request.provider}@example.com",
                    )
                    db.add(user)
                    db.commit()
                    db.refresh(user)
                except Exception as db_error:
                    db.rollback()
                    # 혹시 동시성 문제로 중복이 발생한 경우 다시 조회
                    user = (
                        db.query(User)
                        .filter(User.provider_id == user_info["id"], User.provider == request.provider)
                        .first()
                    )
                    if not user:
                        raise HTTPException(
                            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail=f"Failed to create user: {str(db_error)}"
                        )
        
        # Generate JWT payload with social auth features and team information
        jwt_payload = generate_jwt_payload(user_info, request.provider)
        jwt_payload["sub"] = user.user_id  # Use database user_id as subject
        
        # Add team information to JWT payload
        team_names = [team.group_name for team in user.groups]
        jwt_payload["groups"] = team_names if team_names else ["default"]
        
        # Create access token
        access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data=jwt_payload, expires_delta=access_token_expires
        )
        
        return TokenResponse(
            access_token=access_token,
            token_type="bearer",
            expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
            user=jwt_payload
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Social login failed: {str(e)}"
        )



@router.get("/me", response_model=UserWithTeams)
async def get_current_user_info(
    current_user: dict = Depends(get_current_user), db: Session = Depends(get_db)
):
    """현재 로그인한 사용자 정보 조회 (DB에서, 팀 정보 포함)"""
    user_id = current_user.get("sub")
    user = db.query(User).filter(User.user_id == user_id).first()
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found in database",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


@router.options("/social-login")
async def social_login_options():
    """소셜 로그인 OPTIONS 요청 처리"""
    return {"message": "CORS preflight OK"}


@router.get("/me/enhanced")
async def get_current_user_enhanced(current_user: dict = Depends(get_current_user)):
    """현재 로그인한 사용자 정보 조회 (소셜 로그인 정보 포함)"""
    return current_user


@router.post("/logout")
async def logout(current_user: dict = Depends(get_current_user)):
    """사용자 로그아웃"""
    return {"message": "Logout successful"}

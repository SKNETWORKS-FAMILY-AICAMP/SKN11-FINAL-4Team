from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional
from jose import JWTError, jwt
import uuid

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, User as UserSchema
from app.core.config import settings
from app.core.security import create_access_token, verify_password, get_password_hash

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


@router.post("/register", response_model=UserSchema)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """사용자 회원가입"""
    # 이메일 중복 확인
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Email already registered"
        )

    # provider_id 중복 확인
    existing_provider_user = (
        db.query(User)
        .filter(
            User.provider_id == user_data.provider_id,
            User.provider == user_data.provider,
        )
        .first()
    )
    if existing_provider_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User already exists with this provider",
        )

    # 새 사용자 생성
    user = User(
        user_id=str(uuid.uuid4()),
        provider_id=user_data.provider_id,
        provider=user_data.provider,
        user_name=user_data.user_name,
        email=user_data.email,
    )

    db.add(user)
    db.commit()
    db.refresh(user)

    return user


@router.post("/login")
async def login(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
):
    """사용자 로그인 (소셜 로그인 시뮬레이션)"""
    # 실제 구현에서는 소셜 로그인 토큰 검증 로직이 들어감
    user = db.query(User).filter(User.email == form_data.username).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 액세스 토큰 생성
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.user_id}, expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer", "user": user}


@router.post("/social-login")
async def social_login(
    provider: str, provider_token: str, db: Session = Depends(get_db)
):
    """소셜 로그인"""
    # 실제 구현에서는 각 소셜 플랫폼의 토큰 검증 로직이 들어감
    # 여기서는 시뮬레이션을 위해 간단한 로직 사용

    # provider_token을 검증하여 사용자 정보 추출 (실제로는 각 플랫폼 API 호출)
    # 예시: Google, Facebook, Kakao 등

    # 임시 사용자 정보 (실제로는 토큰에서 추출)
    user_info = {
        "provider_id": f"{provider}_user_123",
        "user_name": f"User_{provider}",
        "email": f"user_{provider}@example.com",
    }

    # 기존 사용자 확인
    user = (
        db.query(User)
        .filter(User.provider_id == user_info["provider_id"], User.provider == provider)
        .first()
    )

    if not user:
        # 새 사용자 생성
        user = User(
            user_id=str(uuid.uuid4()),
            provider_id=user_info["provider_id"],
            provider=provider,
            user_name=user_info["user_name"],
            email=user_info["email"],
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    # 액세스 토큰 생성
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.user_id}, expires_delta=access_token_expires
    )

    return {"access_token": access_token, "token_type": "bearer", "user": user}


@router.get("/me", response_model=UserSchema)
async def get_current_user(
    token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)
):
    """현재 로그인한 사용자 정보 조회"""
    try:
        payload = jwt.decode(
            token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM]
        )
        user_id = payload.get("sub")
        if user_id is None or not isinstance(user_id, str):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user

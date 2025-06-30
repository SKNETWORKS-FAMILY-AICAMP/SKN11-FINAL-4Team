from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, Dict
from jose import JWTError, jwt
import uuid
import httpx
import os
from pydantic import BaseModel, EmailStr

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserCreate, User as UserSchema
from app.core.config import settings
from app.core.security import create_access_token, verify_password, get_password_hash

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# Social Auth Models
class SocialLoginRequest(BaseModel):
    provider: str
    code: Optional[str] = None
    redirect_uri: Optional[str] = None
    state: Optional[str] = None
    user_info: Optional[Dict] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: Dict

class UserInfo(BaseModel):
    id: str
    email: Optional[EmailStr] = None
    name: Optional[str] = None
    picture: Optional[str] = None
    provider: str
    username: Optional[str] = None
    account_type: Optional[str] = None

# Social Auth Service
class SocialAuthService:
    def __init__(self):
        self.google_client_id = os.getenv("GOOGLE_CLIENT_ID")
        self.google_client_secret = os.getenv("GOOGLE_CLIENT_SECRET")
        self.instagram_app_id = os.getenv("INSTAGRAM_APP_ID")
        self.instagram_app_secret = os.getenv("INSTAGRAM_APP_SECRET")
    
    async def exchange_google_code(self, code: str, redirect_uri: str) -> Dict:
        async with httpx.AsyncClient() as client:
            token_data = {
                "client_id": self.google_client_id,
                "client_secret": self.google_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
            }
            
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data=token_data
            )
            
            if token_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to exchange Google authorization code"
                )
            
            token_json = token_response.json()
            access_token = token_json.get("access_token")
            
            user_response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            if user_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to get Google user info"
                )
            
            user_data = user_response.json()
            return {
                "id": user_data.get("id"),
                "email": user_data.get("email"),
                "name": user_data.get("name"),
                "picture": user_data.get("picture"),
                "provider": "google"
            }
    
    async def exchange_instagram_code(self, code: str, redirect_uri: str) -> Dict:
        async with httpx.AsyncClient() as client:
            token_data = {
                "client_id": self.instagram_app_id,
                "client_secret": self.instagram_app_secret,
                "grant_type": "authorization_code",
                "redirect_uri": redirect_uri,
                "code": code,
            }
            
            token_response = await client.post(
                "https://api.instagram.com/oauth/access_token",
                data=token_data
            )
            
            if token_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to exchange Instagram authorization code"
                )
            
            token_json = token_response.json()
            access_token = token_json.get("access_token")
            user_id = token_json.get("user_id")
            
            user_response = await client.get(
                f"https://graph.instagram.com/{user_id}",
                params={
                    "fields": "id,username,account_type,media_count",
                    "access_token": access_token
                }
            )
            
            if user_response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Failed to get Instagram user info"
                )
            
            user_data = user_response.json()
            return {
                "id": str(user_data.get("id")),
                "username": user_data.get("username"),
                "account_type": user_data.get("account_type", "PERSONAL"),
                "media_count": user_data.get("media_count", 0),
                "access_token": access_token,
                "provider": "instagram"
            }
    
    async def process_social_login(self, provider: str, code: Optional[str] = None, redirect_uri: Optional[str] = None, user_info: Optional[Dict] = None) -> Dict:
        if provider == "google":
            if user_info:
                return {
                    "id": user_info.get("id"),
                    "email": user_info.get("email"),
                    "name": user_info.get("name"),
                    "picture": user_info.get("picture"),
                    "provider": "google"
                }
            elif code and redirect_uri:
                return await self.exchange_google_code(code, redirect_uri)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Either user_info or code with redirect_uri is required for Google login"
                )
        elif provider == "instagram":
            if code and redirect_uri:
                return await self.exchange_instagram_code(code, redirect_uri)
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Code and redirect_uri are required for Instagram login"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported provider: {provider}"
            )

# Social auth service instance
social_auth_service = SocialAuthService()

# JWT payload generation
def generate_jwt_payload(user_info: Dict, provider: str) -> Dict:
    is_business = False
    business_features = {}
    
    if provider == "instagram":
        account_type = user_info.get("account_type", "PERSONAL")
        is_business = account_type in ["BUSINESS", "CREATOR"]
        business_features = {
            "insights": is_business,
            "content_publishing": is_business,
            "message_management": is_business,
            "comment_management": True
        }
    
    payload = {
        "sub": user_info.get("id"),
        "email": user_info.get("email"),
        "name": user_info.get("name"),
        "provider": provider,
        "company": f"{provider.title()} Business User" if is_business else f"{provider.title()} User",
        "groups": ["business", "user"] if is_business else ["user"],
        "permissions": [
            "post:read", "post:write", "model:read", "model:write", 
            "insights:read", "business:manage"
        ] if is_business else ["post:read", "model:read"],
    }
    
    if provider == "instagram":
        payload["instagram"] = {
            "username": user_info.get("username"),
            "account_type": user_info.get("account_type"),
            "is_business_verified": is_business,
            "business_features": business_features
        }
    
    return payload


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


@router.post("/social-login", response_model=TokenResponse)
async def enhanced_social_login(request: SocialLoginRequest, db: Session = Depends(get_db)):
    """Enhanced social login with Google and Instagram support"""
    try:
        user_info = await social_auth_service.process_social_login(
            provider=request.provider,
            code=request.code,
            redirect_uri=request.redirect_uri,
            user_info=request.user_info
        )
        
        # Check if user exists in database
        user = (
            db.query(User)
            .filter(User.provider_id == user_info["id"], User.provider == request.provider)
            .first()
        )
        
        if not user:
            # Create new user
            user = User(
                user_id=str(uuid.uuid4()),
                provider_id=user_info["id"],
                provider=request.provider,
                user_name=user_info.get("name") or user_info.get("username", f"User_{request.provider}"),
                email=user_info.get("email", f"user_{request.provider}@example.com"),
            )
            db.add(user)
            db.commit()
            db.refresh(user)
        
        # Generate JWT payload with social auth features
        jwt_payload = generate_jwt_payload(user_info, request.provider)
        jwt_payload["sub"] = user.user_id  # Use database user_id as subject
        
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

@router.post("/social-login-legacy")
async def social_login(
    provider: str, provider_token: str, db: Session = Depends(get_db)
):
    """Legacy social login (deprecated - use /social-login instead)"""
    # Keep original implementation for backward compatibility
    user_info = {
        "provider_id": f"{provider}_user_123",
        "user_name": f"User_{provider}",
        "email": f"user_{provider}@example.com",
    }

    user = (
        db.query(User)
        .filter(User.provider_id == user_info["provider_id"], User.provider == provider)
        .first()
    )

    if not user:
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

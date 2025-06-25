from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.schemas.auth import Token, UserLogin
from app.core.security import create_access_token, verify_password

router = APIRouter()

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


@router.post("/login", response_model=Token)
async def login(user_credentials: UserLogin, db: Session = Depends(get_db)):
    """사용자 로그인"""
    # 실제 구현에서는 소셜 로그인 처리
    # 현재는 간단한 이메일 기반 로그인으로 구현
    user = db.query(User).filter(User.email == user_credentials.email).first()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 실제 구현에서는 비밀번호 검증
    # if not verify_password(user_credentials.password, user.hashed_password):
    #     raise HTTPException(
    #         status_code=status.HTTP_401_UNAUTHORIZED,
    #         detail="Incorrect email or password",
    #         headers={"WWW-Authenticate": "Bearer"},
    #     )

    access_token = create_access_token(data={"sub": user.user_uuid})
    return {"access_token": access_token, "token_type": "bearer"}


@router.post("/register")
async def register(user_data: dict, db: Session = Depends(get_db)):
    """사용자 등록 (소셜 로그인)"""
    # 소셜 로그인 사용자 정보 저장
    user = User(
        provider_id=user_data.get("provider_id"),
        provider=user_data.get("provider"),
        user_name=user_data.get("user_name"),
        email=user_data.get("email"),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return {"message": "User registered successfully", "user_uuid": user.user_uuid}

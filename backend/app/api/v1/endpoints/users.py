from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.user import User
from app.schemas.user import UserResponse

router = APIRouter()


@router.get("/", response_model=List[UserResponse])
def get_users(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """사용자 목록 조회"""
    users = db.query(User).offset(skip).limit(limit).all()
    return users


@router.get("/{user_uuid}", response_model=UserResponse)
def get_user(user_uuid: str, db: Session = Depends(get_db)):
    """특정 사용자 조회"""
    user = db.query(User).filter(User.user_uuid == user_uuid).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
import uuid

from app.database import get_db
from app.models.user import User, Team
from app.schemas.user import (
    UserCreate,
    UserUpdate,
    User as UserSchema,
)
from app.api.v1.endpoints.auth import get_current_user

router = APIRouter()


def check_admin_permission(current_user: User, db: Session):
    """관리자 권한 체크 - 그룹 0번에 속한 사용자를 관리자로 간주"""
    # 그룹 0번이 관리자 그룹이라고 가정
    admin_team = db.query(Team).filter(Team.group_id == 0).first()
    if admin_team:
        # 현재 사용자가 관리자 그룹에 속해있는지 확인
        user_in_admin_team = (
            db.query(Team)
            .join(Team.users)
            .filter(Team.group_id == 0, User.user_id == str(current_user.user_id))
            .first()
        )
        if user_in_admin_team:
            return True
    return False


@router.post("/", response_model=UserSchema)
async def create_user(
    user_data: UserCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """새 사용자 생성 (관리자만 가능)"""
    if not check_admin_permission(current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create users",
        )

    # 이메일 중복 체크
    existing_user = db.query(User).filter(User.email == user_data.email).first()
    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email already registered",
        )

    # provider_id 중복 체크
    existing_provider_user = (
        db.query(User).filter(User.provider_id == user_data.provider_id).first()
    )
    if existing_provider_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provider ID already exists",
        )

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


@router.get("/", response_model=List[UserSchema])
async def get_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_user),  # 임시로 주석 처리
):
    """사용자 목록 조회 (임시로 인증 없이 접근 가능)"""
    # if not check_admin_permission(current_user, db):  # 임시로 주석 처리
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Only administrators can view all users",
    #     )

    users = db.query(User).offset(skip).limit(limit).all()
    return users


@router.get("/{user_id}", response_model=UserSchema)
async def get_user(
    user_id: str,
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_user),  # 임시로 주석 처리
):
    """특정 사용자 조회 (임시로 인증 없이 접근 가능)"""
    # 본인이거나 관리자인 경우만 조회 가능
    # if str(current_user.user_id) != user_id and not check_admin_permission(
    #     current_user, db
    # ):  # 임시로 주석 처리
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Not authorized to view this user",
    #     )

    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return user


@router.put("/{user_id}", response_model=UserSchema)
async def update_user(
    user_id: str,
    user_update: UserUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """사용자 정보 수정"""
    # 본인이거나 관리자인 경우만 수정 가능
    if str(current_user.user_id) != user_id and not check_admin_permission(
        current_user, db
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to update this user",
        )

    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    # 업데이트할 필드들
    update_data = user_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(user, field, value)

    db.commit()
    db.refresh(user)
    return user


@router.delete("/{user_id}")
async def delete_user(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """사용자 삭제 (관리자만 가능)"""
    if not check_admin_permission(current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can delete users",
        )

    # 본인 삭제 방지
    if str(current_user.user_id) == user_id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete yourself",
        )

    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    db.delete(user)
    db.commit()

    return {"message": "User deleted successfully"}


# 팀 관련 API
@router.get("/teams/", response_model=List[dict])
async def get_user_teams(
    db: Session = Depends(get_db), current_user: User = Depends(get_current_user)
):
    """현재 사용자의 팀 목록 조회"""
    user = db.query(User).filter(User.user_id == current_user.user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return [
        {
            "group_id": team.group_id,
            "group_name": team.group_name,
            "group_description": team.group_description,
        }
        for team in user.groups
    ]


@router.get("/{user_id}/teams/", response_model=List[dict])
async def get_user_teams_by_id(
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """특정 사용자의 팀 목록 조회 (관리자만 가능)"""
    if not check_admin_permission(current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can view other users' teams",
        )

    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )
    return [
        {
            "group_id": team.group_id,
            "group_name": team.group_name,
            "group_description": team.group_description,
        }
        for team in user.groups
    ]

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.group import Group
from app.models.user import User
from app.models.user_group import UserGroup
from app.models.hf_token_manage import HFTokenManage
from app.schemas.group import GroupCreate, GroupResponse
from app.schemas.user_group import UserGroupCreate, UserGroupResponse
from app.schemas.hf_token import HFTokenCreate, HFTokenResponse

router = APIRouter()


@router.get("/", response_model=List[GroupResponse])
def get_groups(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """그룹 목록 조회"""
    groups = db.query(Group).offset(skip).limit(limit).all()
    return groups


@router.get("/{group_uuid}", response_model=GroupResponse)
def get_group(group_uuid: str, db: Session = Depends(get_db)):
    """특정 그룹 조회"""
    group = db.query(Group).filter(Group.group_uuid == group_uuid).first()
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")
    return group


@router.post("/", response_model=GroupResponse)
def create_group(group: GroupCreate, db: Session = Depends(get_db)):
    """새 그룹 생성"""
    db_group = Group(**group.model_dump())
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group


@router.post("/{group_uuid}/users", response_model=UserGroupResponse)
def add_user_to_group(
    group_uuid: str, user_group: UserGroupCreate, db: Session = Depends(get_db)
):
    """특정 그룹에 사용자 추가"""
    # 그룹 존재 확인
    group = db.query(Group).filter(Group.group_uuid == group_uuid).first()
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")

    # 사용자 존재 확인
    user = db.query(User).filter(User.user_uuid == user_group.user_uuid).first()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    # 이미 그룹에 속해있는지 확인
    existing_user_group = (
        db.query(UserGroup)
        .filter(
            UserGroup.user_uuid == user_group.user_uuid,
            UserGroup.group_uuid == group_uuid,
        )
        .first()
    )
    if existing_user_group:
        raise HTTPException(status_code=400, detail="User is already in this group")

    # 사용자를 그룹에 추가
    db_user_group = UserGroup(user_uuid=user_group.user_uuid, group_uuid=group_uuid)
    db.add(db_user_group)
    db.commit()
    db.refresh(db_user_group)
    return db_user_group


@router.delete("/{group_uuid}/users/{user_uuid}")
def remove_user_from_group(
    group_uuid: str, user_uuid: str, db: Session = Depends(get_db)
):
    """그룹에서 사용자 제거"""
    user_group = (
        db.query(UserGroup)
        .filter(UserGroup.user_uuid == user_uuid, UserGroup.group_uuid == group_uuid)
        .first()
    )
    if user_group is None:
        raise HTTPException(status_code=404, detail="User not found in this group")

    db.delete(user_group)
    db.commit()
    return {"message": "User removed from group successfully"}


@router.get("/{group_uuid}/users", response_model=List[dict])
def get_group_users(group_uuid: str, db: Session = Depends(get_db)):
    """그룹에 속한 사용자 목록 조회"""
    # 그룹 존재 확인
    group = db.query(Group).filter(Group.group_uuid == group_uuid).first()
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")

    # 그룹에 속한 사용자들 조회
    user_groups = db.query(UserGroup).filter(UserGroup.group_uuid == group_uuid).all()
    users = []
    for user_group in user_groups:
        user = db.query(User).filter(User.user_uuid == user_group.user_uuid).first()
        if user:
            users.append(
                {
                    "user_uuid": user.user_uuid,
                    "user_name": user.user_name,
                    "email": user.email,
                }
            )
    return users


@router.post("/{group_uuid}/hf-tokens", response_model=HFTokenResponse)
def add_hf_token_to_group(
    group_uuid: str, hf_token: HFTokenCreate, db: Session = Depends(get_db)
):
    """특정 그룹에 허깅페이스 토큰 부여"""
    # 그룹 존재 확인
    group = db.query(Group).filter(Group.group_uuid == group_uuid).first()
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")

    # 토큰 닉네임 중복 확인
    existing_token = (
        db.query(HFTokenManage)
        .filter(
            HFTokenManage.group_uuid == group_uuid,
            HFTokenManage.hf_token_nickname == hf_token.hf_token_nickname,
        )
        .first()
    )
    if existing_token:
        raise HTTPException(
            status_code=400, detail="Token nickname already exists for this group"
        )

    # 허깅페이스 토큰 생성
    db_hf_token = HFTokenManage(
        group_uuid=group_uuid,
        hf_token_value=hf_token.hf_token_value,
        hf_token_nickname=hf_token.hf_token_nickname,
        hf_user_name=hf_token.hf_user_name,
    )
    db.add(db_hf_token)
    db.commit()
    db.refresh(db_hf_token)
    return db_hf_token


@router.post("/{group_uuid}/hf-tokens/{hf_manage_uuid}/assign")
def assign_hf_token_to_group(
    group_uuid: str, hf_manage_uuid: str, db: Session = Depends(get_db)
):
    """기존 허깅페이스 토큰을 그룹에 할당"""
    # 그룹 존재 확인
    group = db.query(Group).filter(Group.group_uuid == group_uuid).first()
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")

    # 토큰 존재 확인
    hf_token = (
        db.query(HFTokenManage)
        .filter(HFTokenManage.hf_manage_uuid == hf_manage_uuid)
        .first()
    )
    if hf_token is None:
        raise HTTPException(status_code=404, detail="HF Token not found")

    # 이미 다른 그룹에 할당되어 있는지 확인
    if hf_token.group_uuid is not None:
        raise HTTPException(
            status_code=400, detail="Token is already assigned to another group"
        )

    # 토큰을 그룹에 할당
    setattr(hf_token, "group_uuid", group_uuid)
    db.commit()
    db.refresh(hf_token)

    return {
        "message": "HF Token assigned to group successfully",
        "hf_manage_uuid": hf_manage_uuid,
    }


@router.delete("/{group_uuid}/hf-tokens/{hf_manage_uuid}/unassign")
def unassign_hf_token_from_group(
    group_uuid: str, hf_manage_uuid: str, db: Session = Depends(get_db)
):
    """그룹에서 허깅페이스 토큰 할당 해제"""
    # 그룹 존재 확인
    group = db.query(Group).filter(Group.group_uuid == group_uuid).first()
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")

    # 토큰 존재 확인
    hf_token = (
        db.query(HFTokenManage)
        .filter(
            HFTokenManage.hf_manage_uuid == hf_manage_uuid,
            HFTokenManage.group_uuid == group_uuid,
        )
        .first()
    )
    if hf_token is None:
        raise HTTPException(status_code=404, detail="HF Token not found in this group")

    # 토큰 할당 해제
    setattr(hf_token, "group_uuid", None)
    db.commit()

    return {"message": "HF Token unassigned from group successfully"}


@router.get("/{group_uuid}/hf-tokens", response_model=List[HFTokenResponse])
def get_group_hf_tokens(group_uuid: str, db: Session = Depends(get_db)):
    """그룹의 허깅페이스 토큰 목록 조회"""
    # 그룹 존재 확인
    group = db.query(Group).filter(Group.group_uuid == group_uuid).first()
    if group is None:
        raise HTTPException(status_code=404, detail="Group not found")

    # 그룹의 허깅페이스 토큰들 조회
    hf_tokens = (
        db.query(HFTokenManage).filter(HFTokenManage.group_uuid == group_uuid).all()
    )
    return hf_tokens

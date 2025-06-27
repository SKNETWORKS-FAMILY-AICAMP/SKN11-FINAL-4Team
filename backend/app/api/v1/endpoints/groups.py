from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List
from pydantic import BaseModel

from app.database import get_db
from app.models.user import Group, User
from app.schemas.user import (
    GroupCreate,
    GroupUpdate,
    Group as GroupSchema,
    GroupWithUsers,
)
from app.api.v1.endpoints.auth import get_current_user

router = APIRouter()


class BulkUserOperation(BaseModel):
    """일괄 사용자 작업을 위한 스키마"""

    user_ids: List[str]


def check_admin_permission(current_user: User, db: Session):
    """관리자 권한 체크 - 그룹 0번에 속한 사용자를 관리자로 간주"""
    # 그룹 0번이 관리자 그룹이라고 가정
    admin_group = db.query(Group).filter(Group.group_id == 0).first()
    if admin_group:
        # 현재 사용자가 관리자 그룹에 속해있는지 확인
        user_in_admin_group = (
            db.query(Group)
            .join(Group.users)
            .filter(Group.group_id == 0, User.user_id == str(current_user.user_id))
            .first()
        )
        if user_in_admin_group:
            return True
    return False


@router.get("/", response_model=List[GroupSchema])
async def get_groups(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_user),  # 임시로 주석 처리
):
    """그룹 목록 조회 (임시로 인증 없이 접근 가능)"""
    # 관리자는 모든 그룹 조회 가능, 일반 사용자는 자신이 속한 그룹만 조회
    # if check_admin_permission(current_user, db):  # 임시로 주석 처리
    groups = db.query(Group).offset(skip).limit(limit).all()
    # else:  # 임시로 주석 처리
    #     groups = (
    #         db.query(Group)
    #         .join(Group.users)
    #         .filter(User.user_id == str(current_user.user_id))
    #         .offset(skip)
    #         .limit(limit)
    #         .all()
    #     )

    return groups


@router.get("/{group_id}", response_model=GroupWithUsers)
async def get_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """특정 그룹 조회"""
    group = db.query(Group).filter(Group.group_id == group_id).first()
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )

    # 관리자가 아니고 해당 그룹에 속하지 않은 경우 접근 거부
    if not check_admin_permission(current_user, db) and current_user not in group.users:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this group",
        )

    return group


@router.post("/", response_model=GroupSchema)
async def create_group(
    group_data: GroupCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """새 그룹 생성 (관리자만 가능)"""
    if not check_admin_permission(current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can create groups",
        )

    group = Group(**group_data.dict())
    db.add(group)
    db.commit()
    db.refresh(group)

    return group


@router.put("/{group_id}", response_model=GroupSchema)
async def update_group(
    group_id: int,
    group_update: GroupUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """그룹 정보 수정 (관리자만 가능)"""
    if not check_admin_permission(current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can update groups",
        )

    group = db.query(Group).filter(Group.group_id == group_id).first()
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )

    # 관리자 그룹(0번)은 수정 불가
    if group_id == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot modify admin group (group_id: 0)",
        )

    # 업데이트할 필드들
    update_data = group_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(group, field, value)

    db.commit()
    db.refresh(group)
    return group


@router.delete("/{group_id}")
async def delete_group(
    group_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """그룹 삭제 (관리자만 가능)"""
    if not check_admin_permission(current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can delete groups",
        )

    group = db.query(Group).filter(Group.group_id == group_id).first()
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )

    # 관리자 그룹(0번)은 삭제 불가
    if group_id == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete admin group (group_id: 0)",
        )

    db.delete(group)
    db.commit()

    return {"message": "Group deleted successfully"}


@router.post("/{group_id}/users/{user_id}")
async def add_user_to_group(
    group_id: int,
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """그룹에 사용자 추가 (관리자만 가능)"""
    if not check_admin_permission(current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can add users to groups",
        )

    group = db.query(Group).filter(Group.group_id == group_id).first()
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )

    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if user in group.users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User is already in this group",
        )

    group.users.append(user)
    db.commit()

    return {"message": "User added to group successfully"}


@router.post("/{group_id}/users/bulk-add")
async def bulk_add_users_to_group(
    group_id: int,
    user_operation: BulkUserOperation,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """그룹에 여러 사용자 일괄 추가 (관리자만 가능)"""
    if not check_admin_permission(current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can add users to groups",
        )

    group = db.query(Group).filter(Group.group_id == group_id).first()
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )

    added_users = []
    already_in_group = []
    not_found_users = []

    for user_id in user_operation.user_ids:
        user = db.query(User).filter(User.user_id == user_id).first()
        if user is None:
            not_found_users.append(user_id)
        elif user in group.users:
            already_in_group.append(user_id)
        else:
            group.users.append(user)
            added_users.append(user_id)

    db.commit()

    return {
        "message": "Bulk user operation completed",
        "added_users": added_users,
        "already_in_group": already_in_group,
        "not_found_users": not_found_users,
    }


@router.delete("/{group_id}/users/{user_id}")
async def remove_user_from_group(
    group_id: int,
    user_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """그룹에서 사용자 제거 (관리자만 가능)"""
    if not check_admin_permission(current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can remove users from groups",
        )

    group = db.query(Group).filter(Group.group_id == group_id).first()
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )

    user = db.query(User).filter(User.user_id == user_id).first()
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="User not found"
        )

    if user not in group.users:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="User is not in this group"
        )

    # 관리자 그룹(0번)에서 마지막 관리자를 제거할 수 없음
    if group_id == 0 and len(group.users) == 1:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot remove the last administrator from admin group",
        )

    group.users.remove(user)
    db.commit()

    return {"message": "User removed from group successfully"}


@router.post("/{group_id}/users/bulk-remove")
async def bulk_remove_users_from_group(
    group_id: int,
    user_operation: BulkUserOperation,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """그룹에서 여러 사용자 일괄 제거 (관리자만 가능)"""
    if not check_admin_permission(current_user, db):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only administrators can remove users from groups",
        )

    group = db.query(Group).filter(Group.group_id == group_id).first()
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )

    removed_users = []
    not_in_group = []
    not_found_users = []

    for user_id in user_operation.user_ids:
        user = db.query(User).filter(User.user_id == user_id).first()
        if user is None:
            not_found_users.append(user_id)
        elif user not in group.users:
            not_in_group.append(user_id)
        else:
            # 관리자 그룹(0번)에서 마지막 관리자를 제거할 수 없음
            if group_id == 0 and len(group.users) == 1:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot remove the last administrator from admin group",
                )

            group.users.remove(user)
            removed_users.append(user_id)

    db.commit()

    return {
        "message": "Bulk user removal completed",
        "removed_users": removed_users,
        "not_in_group": not_in_group,
        "not_found_users": not_found_users,
    }


@router.get("/{group_id}/users/", response_model=List[dict])
async def get_group_users(
    group_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """그룹의 사용자 목록 조회"""
    group = db.query(Group).filter(Group.group_id == group_id).first()
    if group is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
        )

    # 관리자가 아니고 해당 그룹에 속하지 않은 경우 접근 거부
    if not check_admin_permission(current_user, db) and current_user not in group.users:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Not authorized to access this group",
        )

    users = group.users[skip : skip + limit]
    return [
        {
            "user_id": user.user_id,
            "user_name": user.user_name,
            "email": user.email,
            "provider": user.provider,
        }
        for user in users
    ]

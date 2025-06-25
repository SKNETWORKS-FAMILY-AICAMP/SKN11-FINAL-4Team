from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.group import Group
from app.schemas.group import GroupCreate, GroupResponse

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
    db_group = Group(**group.dict())
    db.add(db_group)
    db.commit()
    db.refresh(db_group)
    return db_group

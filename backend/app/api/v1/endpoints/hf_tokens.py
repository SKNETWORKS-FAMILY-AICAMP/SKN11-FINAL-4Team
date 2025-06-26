from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.hf_token_manage import HFTokenManage
from app.schemas.hf_token import HFTokenCreate, HFTokenResponse, HFTokenUpdate

router = APIRouter()


@router.get("/", response_model=List[HFTokenResponse])
def get_hf_tokens(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """허깅페이스 토큰 목록 조회"""
    hf_tokens = db.query(HFTokenManage).offset(skip).limit(limit).all()
    return hf_tokens


@router.get("/{hf_manage_uuid}", response_model=HFTokenResponse)
def get_hf_token(hf_manage_uuid: str, db: Session = Depends(get_db)):
    """특정 허깅페이스 토큰 조회"""
    hf_token = (
        db.query(HFTokenManage)
        .filter(HFTokenManage.hf_manage_uuid == hf_manage_uuid)
        .first()
    )
    if hf_token is None:
        raise HTTPException(status_code=404, detail="HF Token not found")
    return hf_token


@router.post("/", response_model=HFTokenResponse)
def create_hf_token(hf_token: HFTokenCreate, db: Session = Depends(get_db)):
    """새 허깅페이스 토큰 생성 (그룹에 할당되지 않은 상태)"""
    # 토큰 닉네임 중복 확인 (같은 그룹 내에서)
    existing_token = (
        db.query(HFTokenManage)
        .filter(
            HFTokenManage.group_uuid == hf_token.group_uuid,
            HFTokenManage.hf_token_nickname == hf_token.hf_token_nickname,
        )
        .first()
    )
    if existing_token:
        raise HTTPException(
            status_code=400, detail="Token nickname already exists for this group"
        )

    db_hf_token = HFTokenManage(**hf_token.model_dump())
    db.add(db_hf_token)
    db.commit()
    db.refresh(db_hf_token)
    return db_hf_token


@router.put("/{hf_manage_uuid}", response_model=HFTokenResponse)
def update_hf_token(
    hf_manage_uuid: str, hf_token_update: HFTokenUpdate, db: Session = Depends(get_db)
):
    """허깅페이스 토큰 수정"""
    db_hf_token = (
        db.query(HFTokenManage)
        .filter(HFTokenManage.hf_manage_uuid == hf_manage_uuid)
        .first()
    )
    if db_hf_token is None:
        raise HTTPException(status_code=404, detail="HF Token not found")

    for field, value in hf_token_update.model_dump(exclude_unset=True).items():
        if hasattr(db_hf_token, field):
            setattr(db_hf_token, field, value)

    db.commit()
    db.refresh(db_hf_token)
    return db_hf_token


@router.delete("/{hf_manage_uuid}")
def delete_hf_token(hf_manage_uuid: str, db: Session = Depends(get_db)):
    """허깅페이스 토큰 삭제"""
    db_hf_token = (
        db.query(HFTokenManage)
        .filter(HFTokenManage.hf_manage_uuid == hf_manage_uuid)
        .first()
    )
    if db_hf_token is None:
        raise HTTPException(status_code=404, detail="HF Token not found")

    db.delete(db_hf_token)
    db.commit()
    return {"message": "HF Token deleted successfully"}


@router.get("/available/", response_model=List[HFTokenResponse])
def get_available_hf_tokens(db: Session = Depends(get_db)):
    """사용 가능한 허깅페이스 토큰 목록 조회 (그룹에 할당되지 않은 토큰들)"""
    # group_uuid가 null이거나 빈 값인 토큰들 조회
    available_tokens = (
        db.query(HFTokenManage).filter(HFTokenManage.group_uuid.is_(None)).all()
    )
    return available_tokens

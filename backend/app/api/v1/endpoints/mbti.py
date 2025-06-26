from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.model_mbti import ModelMBTI
from app.schemas.mbti import MBTIResponse, MBTICreate, MBTIUpdate

router = APIRouter()


@router.get("/", response_model=List[MBTIResponse])
def get_mbti_list(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """MBTI 목록 조회"""
    mbti_list = db.query(ModelMBTI).offset(skip).limit(limit).all()
    return mbti_list


@router.get("/{mbti_id}", response_model=MBTIResponse)
def get_mbti(mbti_id: int, db: Session = Depends(get_db)):
    """특정 MBTI 조회"""
    mbti = db.query(ModelMBTI).filter(ModelMBTI.mbti_id == mbti_id).first()
    if mbti is None:
        raise HTTPException(status_code=404, detail="MBTI not found")
    return mbti


@router.post("/", response_model=MBTIResponse)
def create_mbti(mbti: MBTICreate, db: Session = Depends(get_db)):
    """새 MBTI 생성"""
    db_mbti = ModelMBTI(**mbti.model_dump())
    db.add(db_mbti)
    db.commit()
    db.refresh(db_mbti)
    return db_mbti


@router.put("/{mbti_id}", response_model=MBTIResponse)
def update_mbti(mbti_id: int, mbti_update: MBTIUpdate, db: Session = Depends(get_db)):
    """MBTI 수정"""
    db_mbti = db.query(ModelMBTI).filter(ModelMBTI.mbti_id == mbti_id).first()
    if db_mbti is None:
        raise HTTPException(status_code=404, detail="MBTI not found")

    update_data = mbti_update.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(db_mbti, field, value)

    db.commit()
    db.refresh(db_mbti)
    return db_mbti


@router.delete("/{mbti_id}")
def delete_mbti(mbti_id: int, db: Session = Depends(get_db)):
    """MBTI 삭제"""
    db_mbti = db.query(ModelMBTI).filter(ModelMBTI.mbti_id == mbti_id).first()
    if db_mbti is None:
        raise HTTPException(status_code=404, detail="MBTI not found")

    db.delete(db_mbti)
    db.commit()
    return {"message": "MBTI deleted successfully"}

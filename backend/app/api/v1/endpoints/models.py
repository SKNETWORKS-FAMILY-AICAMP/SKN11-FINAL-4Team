from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.database import get_db
from app.models.ml import ML
from app.schemas.model import ModelCreate, ModelResponse

router = APIRouter()


@router.get("/", response_model=List[ModelResponse])
def get_models(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """AI 모델 목록 조회"""
    models = db.query(ML).offset(skip).limit(limit).all()
    return models


@router.get("/{model_uuid}", response_model=ModelResponse)
def get_model(model_uuid: str, db: Session = Depends(get_db)):
    """특정 AI 모델 조회"""
    model = db.query(ML).filter(ML.model_uuid == model_uuid).first()
    if model is None:
        raise HTTPException(status_code=404, detail="Model not found")
    return model


@router.post("/", response_model=ModelResponse)
def create_model(model: ModelCreate, db: Session = Depends(get_db)):
    """새 AI 모델 생성"""
    # 모델명 중복 체크
    existing_model = db.query(ML).filter(ML.model_name == model.model_name).first()
    if existing_model:
        raise HTTPException(status_code=400, detail="Model name already exists")

    db_model = ML(**model.dict())
    db.add(db_model)
    db.commit()
    db.refresh(db_model)
    return db_model


@router.put("/{model_uuid}", response_model=ModelResponse)
def update_model(model_uuid: str, model_update: dict, db: Session = Depends(get_db)):
    """AI 모델 수정"""
    db_model = db.query(ML).filter(ML.model_uuid == model_uuid).first()
    if db_model is None:
        raise HTTPException(status_code=404, detail="Model not found")

    for field, value in model_update.items():
        if hasattr(db_model, field):
            setattr(db_model, field, value)

    db.commit()
    db.refresh(db_model)
    return db_model


@router.delete("/{model_uuid}")
def delete_model(model_uuid: str, db: Session = Depends(get_db)):
    """AI 모델 삭제"""
    db_model = db.query(ML).filter(ML.model_uuid == model_uuid).first()
    if db_model is None:
        raise HTTPException(status_code=404, detail="Model not found")

    db.delete(db_model)
    db.commit()
    return {"message": "Model deleted successfully"}

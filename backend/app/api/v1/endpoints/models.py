from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from typing import List, Optional
import logging
from datetime import datetime
from app.database import get_db
from app.models.ml import ML
from app.models.group import Group
from app.models.model_mbti import ModelMBTI
from app.models.board import Board
from app.models.ml_api import MLAPI
from app.schemas.model import ModelCreate, ModelResponse, ModelUpdate
from fastapi.responses import JSONResponse

# 로깅 설정
logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/", response_model=List[ModelResponse])
def get_models(
    skip: int = 0,
    limit: int = 100,
    group_uuid: Optional[str] = None,
    status_filter: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """AI 모델 목록 조회 (필터링 지원)"""
    try:
        query = db.query(ML)

        # 그룹별 필터링
        if group_uuid:
            query = query.filter(ML.group_uuid == group_uuid)

        # 상태별 필터링
        if status_filter is not None:
            query = query.filter(ML.model_status == status_filter)

        models = query.offset(skip).limit(limit).all()
        logger.info(f"Retrieved {len(models)} models")
        return models
    except Exception as e:
        logger.error(f"Error retrieving models: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve models",
        )


@router.get("/{model_uuid}", response_model=ModelResponse)
def get_model(model_uuid: str, db: Session = Depends(get_db)):
    """특정 AI 모델 조회"""
    try:
        model = db.query(ML).filter(ML.model_uuid == model_uuid).first()
        if model is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Model not found"
            )
        return model
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error retrieving model {model_uuid}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to retrieve model",
        )


@router.post("/", response_model=ModelResponse)
def create_model(
    model: ModelCreate, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    """새 AI 모델 생성 (개선된 검증 및 에러 핸들링)"""
    try:
        # 1. 그룹 존재 여부 확인
        group = db.query(Group).filter(Group.group_uuid == model.group_uuid).first()
        if not group:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Group not found"
            )

        # 2. MBTI 존재 여부 확인
        mbti = db.query(ModelMBTI).filter(ModelMBTI.mbti_id == model.mbti_id).first()
        if not mbti:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="MBTI not found"
            )

        # 3. 모델명 중복 체크 (대소문자 구분 없이)
        existing_model = (
            db.query(ML).filter(ML.model_name.ilike(model.model_name)).first()
        )
        if existing_model:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Model name already exists",
            )

        # 4. 모델 생성
        db_model = ML(**model.model_dump())
        db.add(db_model)
        db.commit()
        db.refresh(db_model)

        # 5. 백그라운드 작업 (로깅 등)
        background_tasks.add_task(
            logger.info,
            f"Created new model: {db_model.model_uuid} - {db_model.model_name}",
        )

        logger.info(f"Successfully created model: {db_model.model_uuid}")
        return db_model

    except HTTPException:
        raise
    except IntegrityError as e:
        db.rollback()
        logger.error(f"Database integrity error creating model: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid data provided"
        )
    except Exception as e:
        db.rollback()
        logger.error(f"Error creating model: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create model",
        )


@router.put("/{model_uuid}", response_model=ModelResponse)
def update_model(
    model_uuid: str, model_update: ModelUpdate, db: Session = Depends(get_db)
):
    """AI 모델 수정 (개선된 검증)"""
    try:
        db_model = db.query(ML).filter(ML.model_uuid == model_uuid).first()
        if db_model is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Model not found"
            )

        # 모델명 변경 시 중복 체크
        if model_update.model_name and model_update.model_name != db_model.model_name:
            existing_model = (
                db.query(ML)
                .filter(
                    ML.model_name.ilike(model_update.model_name),
                    ML.model_uuid != model_uuid,
                )
                .first()
            )
            if existing_model:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Model name already exists",
                )

        # 업데이트할 필드만 처리
        update_data = model_update.model_dump(exclude_unset=True)
        for field, value in update_data.items():
            setattr(db_model, field, value)

        # updated_at은 데이터베이스에서 자동으로 처리되므로 제거
        db.commit()
        db.refresh(db_model)

        logger.info(f"Successfully updated model: {model_uuid}")
        return db_model

    except HTTPException:
        raise
    except Exception as e:
        db.rollback()
        logger.error(f"Error updating model {model_uuid}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to update model",
        )


@router.delete("/{model_uuid}")
def delete_model(
    model_uuid: str, force_delete: bool = False, db: Session = Depends(get_db)
):
    """AI 모델 삭제 (매우 단순한 버전)"""
    try:
        # 1. 모델 존재 여부 확인
        db_model = db.query(ML).filter(ML.model_uuid == model_uuid).first()
        if db_model is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Model not found"
            )

        model_name = db_model.model_name

        # 2. 강제 삭제가 아닌 경우 관련 데이터 확인
        if not force_delete:
            related_boards = (
                db.query(Board).filter(Board.model_uuid == model_uuid).count()
            )
            related_apis = (
                db.query(MLAPI).filter(MLAPI.model_uuid == model_uuid).count()
            )

            if related_boards > 0 or related_apis > 0:
                return {
                    "message": "Model has related data",
                    "related_boards": related_boards,
                    "related_apis": related_apis,
                    "solution": "Use force_delete=true to delete anyway",
                }

        # 3. 단순 삭제 (CASCADE에 의존)
        db.delete(db_model)
        db.commit()

        logger.info(f"Successfully deleted model: {model_uuid} - {model_name}")
        return {
            "message": "Model deleted successfully",
            "model_uuid": model_uuid,
            "model_name": model_name,
            "force_delete": force_delete,
        }

    except Exception as e:
        db.rollback()
        logger.error(f"Error deleting model {model_uuid}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete model: {str(e)}",
        )


@router.get("/{model_uuid}/security-audit")
def audit_model_security(model_uuid: str, db: Session = Depends(get_db)):
    """모델 보안 감사 (단순화된 버전)"""
    try:
        # 1. 모델 존재 여부 확인
        db_model = db.query(ML).filter(ML.model_uuid == model_uuid).first()
        if db_model is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, detail="Model not found"
            )

        # 2. 관련 데이터 확인
        related_boards = db.query(Board).filter(Board.model_uuid == model_uuid).count()
        related_apis = db.query(MLAPI).filter(MLAPI.model_uuid == model_uuid).count()

        # 3. 삭제 가능 여부 판단
        requires_force_delete = related_boards > 0 or related_apis > 0
        can_delete = not requires_force_delete

        return {
            "model_uuid": model_uuid,
            "model_name": db_model.model_name,
            "related_boards": related_boards,
            "related_apis": related_apis,
            "can_delete": can_delete,
            "requires_force_delete": requires_force_delete,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error auditing model {model_uuid}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to audit model security",
        )

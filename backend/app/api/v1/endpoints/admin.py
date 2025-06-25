from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.models.ml import ML
from app.models.board import Board

router = APIRouter()


@router.get("/dashboard")
def get_dashboard_stats(db: Session = Depends(get_db)):
    """관리자 대시보드 통계"""
    total_users = db.query(User).count()
    total_models = db.query(ML).count()
    total_posts = db.query(Board).count()

    return {
        "total_users": total_users,
        "total_models": total_models,
        "total_posts": total_posts,
    }


@router.get("/system-logs")
def get_system_logs(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    """시스템 로그 조회"""
    # TODO: SystemLog 모델 구현 후 실제 로그 조회
    return {"message": "System logs endpoint", "skip": skip, "limit": limit}

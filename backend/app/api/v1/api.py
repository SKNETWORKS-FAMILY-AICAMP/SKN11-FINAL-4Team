from fastapi import APIRouter
from app.api.v1.endpoints import (
    auth,
    users,
    models,
    boards,
    groups,
    admin,
    hf_tokens,
    mbti,
)

api_router = APIRouter()

# 각 엔드포인트 라우터 등록
api_router.include_router(auth.router, prefix="/auth", tags=["authentication"])
api_router.include_router(users.router, prefix="/users", tags=["users"])
api_router.include_router(models.router, prefix="/models", tags=["models"])
api_router.include_router(mbti.router, prefix="/models/mbti", tags=["mbti"])
api_router.include_router(boards.router, prefix="/boards", tags=["boards"])
api_router.include_router(groups.router, prefix="/groups", tags=["groups"])
api_router.include_router(admin.router, prefix="/admin", tags=["admin"])
api_router.include_router(hf_tokens.router, prefix="/hf-tokens", tags=["hf-tokens"])

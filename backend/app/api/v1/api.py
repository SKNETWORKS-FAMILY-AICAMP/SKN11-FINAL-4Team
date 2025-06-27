from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    users,
    groups,
    influencers,
    boards,
    chat,
    analytics,
    system,
)

api_router = APIRouter()

# 인증 관련 API
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])

# 사용자 관리 API
api_router.include_router(users.router, prefix="/users", tags=["Users"])

# 그룹 관리 API
api_router.include_router(groups.router, prefix="/groups", tags=["Groups"])

# AI 인플루언서 관리 API
api_router.include_router(
    influencers.router, prefix="/influencers", tags=["AI Influencers"]
)

# 게시글 관리 API
api_router.include_router(boards.router, prefix="/boards", tags=["Boards"])

# 채팅 API
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])

# 분석 및 집계 API
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])

# 시스템 관리 API
api_router.include_router(system.router, prefix="/system", tags=["System"])

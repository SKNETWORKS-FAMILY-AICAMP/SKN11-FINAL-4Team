from fastapi import APIRouter

from app.api.v1.endpoints import (
    auth,
    users,
    teams,
    influencers,
    boards,
    chat,
    analytics,
    system,
    instagram,
    model_test,
    content_enhancement,
    hf_tokens,
    admin,
    # chatbot,  # 임시 비활성화
    comfyui,
    user_sessions,
    image_generation,
    unified_images,
)
from app.api.v1.endpoints.public import mbti as public_mbti

api_router = APIRouter()

# 인증 관련 API
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])

# 사용자 관리 API
api_router.include_router(users.router, prefix="/users", tags=["Users"])

# 그룹 관리 API
api_router.include_router(teams.router, prefix="/teams", tags=["Teams"])

# AI 인플루언서 관리 API
api_router.include_router(
    influencers.router, prefix="/influencers", tags=["AI Influencers"]
)

# 게시글 관리 API
api_router.include_router(boards.router, prefix="/boards", tags=["Boards"])

# 채팅 API
api_router.include_router(chat.router, prefix="/chat", tags=["Chat"])

# 챗봇 WebSocket API (임시 비활성화)
# api_router.include_router(chatbot.router, prefix="/chatbot", tags=["Chatbot"])

# 분석 및 집계 API
api_router.include_router(analytics.router, prefix="/analytics", tags=["Analytics"])

# 시스템 관리 API
api_router.include_router(system.router, prefix="/system", tags=["System"])

# 인스타그램 연동 API
api_router.include_router(instagram.router, prefix="/instagram", tags=["Instagram"])

# Model Test API
api_router.include_router(model_test.router, prefix="/model-test", tags=["ModelTest"])

# 게시글  API
api_router.include_router(content_enhancement.router, prefix="/content-enhancement", tags=["Content Enhancement"])

# 공개 API (인증 불필요)
api_router.include_router(public_mbti.router, prefix="/public", tags=["Public APIs"])

# 허깅페이스 토큰 관리 API
api_router.include_router(hf_tokens.router, prefix="/hf-tokens", tags=["HuggingFace Tokens"])

# 관리자 페이지 API
api_router.include_router(admin.router, prefix="/admin", tags=["Administrator"])

# ComfyUI 이미지 생성 API
api_router.include_router(comfyui.router, prefix="/comfyui", tags=["ComfyUI"])

# 사용자 세션 관리 API
api_router.include_router(user_sessions.router, prefix="/user-sessions", tags=["User Sessions"])

# 이미지 생성 API
api_router.include_router(image_generation.router, prefix="/image-generation", tags=["Image Generation"])

# 통합 이미지 API
api_router.include_router(unified_images.router, prefix="/api/images", tags=["Unified Images"])

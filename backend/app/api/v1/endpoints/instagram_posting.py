from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Dict, List
import logging

from app.database import get_db
from app.models.influencer import AIInfluencer
from app.models.board import Board
from app.schemas.instagram_posting import (
    InstagramPostRequest,
    InstagramPostResponse,
    InstagramPostStatus,
)
from app.services.instagram_posting_service import InstagramPostingService
from app.core.security import get_current_user

router = APIRouter()
instagram_posting_service = InstagramPostingService()
logger = logging.getLogger(__name__)


@router.get("/debug/{influencer_id}")
async def debug_instagram_connection(
    influencer_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """인스타그램 연동 상태 디버깅"""
    try:
        # 인플루언서 정보 조회
        influencer = (
            db.query(AIInfluencer)
            .filter(
                AIInfluencer.influencer_id == influencer_id,
                AIInfluencer.user_id == current_user.get("sub"),
            )
            .first()
        )

        if not influencer:
            return {"error": "인플루언서를 찾을 수 없습니다."}

        # 필드 값들을 안전하게 추출
        instagram_is_active = (
            bool(influencer.instagram_is_active)
            if influencer.instagram_is_active is not None
            else False
        )
        instagram_access_token = (
            str(influencer.instagram_access_token)
            if influencer.instagram_access_token
            else None
        )
        instagram_id = str(influencer.instagram_id) if influencer.instagram_id else None

        return {
            "influencer_id": influencer.influencer_id,
            "instagram_id": instagram_id,
            "instagram_is_active": instagram_is_active,
            "has_access_token": bool(instagram_access_token),
            "access_token_preview": (
                instagram_access_token[:20] + "..." if instagram_access_token else None
            ),
            "instagram_username": influencer.instagram_username,
            "instagram_account_type": influencer.instagram_account_type,
            "connected_at": (
                influencer.instagram_connected_at.isoformat()
                if influencer.instagram_connected_at
                else None
            ),
        }

    except Exception as e:
        logger.error(f"Debug error: {str(e)}")
        return {"error": str(e)}


@router.post("/{influencer_id}/post", response_model=InstagramPostResponse)
async def post_to_instagram(
    influencer_id: str,
    request: InstagramPostRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """인스타그램에 게시글 업로드"""
    try:
        # 1. 인플루언서 정보 조회
        influencer = (
            db.query(AIInfluencer)
            .filter(
                AIInfluencer.influencer_id == influencer_id,
                AIInfluencer.user_id == current_user.get("sub"),
            )
            .first()
        )

        if not influencer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="AI 인플루언서를 찾을 수 없거나 접근 권한이 없습니다.",
            )

        # 2. 인스타그램 연동 확인 - 안전한 필드 접근
        instagram_is_active = (
            bool(influencer.instagram_is_active)
            if influencer.instagram_is_active is not None
            else False
        )
        instagram_access_token = (
            str(influencer.instagram_access_token)
            if influencer.instagram_access_token
            else None
        )
        instagram_id = str(influencer.instagram_id) if influencer.instagram_id else None

        if not instagram_is_active or not instagram_access_token:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="인스타그램 계정이 연동되지 않았습니다. 먼저 인스타그램 계정을 연동해주세요.",
            )

        logger.info(
            f"Instagram connection check: is_active={instagram_is_active}, has_token={bool(instagram_access_token)}"
        )

        # 3. 게시글 정보 조회
        board = (
            db.query(Board)
            .filter(
                Board.board_id == request.board_id, Board.influencer_id == influencer_id
            )
            .first()
        )

        if not board:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="게시글을 찾을 수 없습니다.",
            )

        # 4. 인스타그램 권한 확인
        permissions_valid = (
            await instagram_posting_service.verify_instagram_permissions(
                instagram_access_token, instagram_id
            )
        )

        if not permissions_valid:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="인스타그램 권한이 유효하지 않습니다. 계정을 다시 연동해주세요.",
            )

        # 5. 캡션 생성
        caption = request.caption or str(board.board_description) or ""

        # 해시태그 추가
        if request.hashtags:
            hashtag_text = " ".join([f"#{tag}" for tag in request.hashtags])
            caption += f"\n\n{hashtag_text}"
        elif board.board_hash_tag:
            caption += f"\n\n{str(board.board_hash_tag)}"

        # 6. 인스타그램에 업로드
        result = await instagram_posting_service.post_to_instagram(
            instagram_id=instagram_id,
            access_token=instagram_access_token,
            image_url=str(board.image_url),
            caption=caption,
        )

        # 7. 게시글 상태 업데이트
        board.board_status = 3  # 발행됨
        board.published_at = datetime.utcnow()
        db.commit()

        logger.info(f"Instagram post successful: {result.get('instagram_post_id')}")

        return InstagramPostResponse(
            success=True,
            instagram_post_id=result.get("instagram_post_id"),
            message=result.get("message", "인스타그램에 성공적으로 업로드되었습니다."),
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Instagram posting error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"인스타그램 업로드 중 오류가 발생했습니다: {str(e)}",
        )


@router.get("/{influencer_id}/posts", response_model=List[InstagramPostStatus])
async def get_instagram_posts(
    influencer_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """인플루언서의 인스타그램 게시글 목록 조회"""
    try:
        # 인플루언서 권한 확인
        influencer = (
            db.query(AIInfluencer)
            .filter(
                AIInfluencer.influencer_id == influencer_id,
                AIInfluencer.user_id == current_user.get("sub"),
            )
            .first()
        )

        if not influencer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="AI 인플루언서를 찾을 수 없거나 접근 권한이 없습니다.",
            )

        # 발행된 게시글 조회
        published_boards = (
            db.query(Board)
            .filter(
                Board.influencer_id == influencer_id,
                Board.board_status == 3,  # 발행됨
                Board.published_at.isnot(None),
            )
            .order_by(Board.published_at.desc())
            .all()
        )

        posts = []
        for board in published_boards:
            posts.append(
                InstagramPostStatus(
                    board_id=board.board_id,
                    instagram_post_id=None,  # 실제 Instagram post ID는 별도 저장 필요
                    status="published",
                    created_at=board.created_at,
                    published_at=board.published_at,
                )
            )

        return posts

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Instagram posts fetch error: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"인스타그램 게시글 조회 중 오류가 발생했습니다: {str(e)}",
        )

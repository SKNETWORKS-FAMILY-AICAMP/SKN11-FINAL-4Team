from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from app.database import get_db
from app.models.user import User
from app.api.v1.endpoints.auth import get_current_user
from app.schemas.content_enhancement import (
    ContentEnhancementRequest,
    ContentEnhancementResponse,
    ContentEnhancementApproval,
    ContentEnhancementList
)
from app.services.content_enhancement_service import ContentEnhancementService

router = APIRouter()
content_service = ContentEnhancementService()


@router.post("/enhance", response_model=ContentEnhancementResponse)
async def enhance_content(
    request: ContentEnhancementRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """게시글 설명 향상"""
    try:
        user_id = current_user.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication required"
            )
        
        enhancement = await content_service.enhance_content(
            db=db, 
            user_id=user_id, 
            request=request
        )
        return enhancement
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Content enhancement failed: {str(e)}"
        )


@router.post("/approve", response_model=ContentEnhancementResponse)
async def approve_enhancement(
    approval: ContentEnhancementApproval,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """게시글 설명 향상 승인/거부"""
    try:
        enhancement = content_service.approve_enhancement(
            db=db,
            enhancement_id=approval.enhancement_id,
            approved=approval.approved,
            improvement_notes=approval.improvement_notes
        )
        return enhancement
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Approval failed: {str(e)}"
        )


@router.get("/history", response_model=ContentEnhancementList)
async def get_enhancement_history(
    page: int = 1,
    page_size: int = 10,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """사용자의 게시글 향상 이력 조회"""
    try:
        user_id = current_user.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication required"
            )
        
        result = content_service.get_user_enhancements(
            db=db,
            user_id=user_id,
            page=page,
            page_size=page_size
        )
        return result
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get enhancement history: {str(e)}"
        )


@router.get("/{enhancement_id}", response_model=ContentEnhancementResponse)
async def get_enhancement(
    enhancement_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user)
):
    """특정 게시글 향상 내역 조회"""
    user_id = current_user.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User authentication required"
        )
    
    from app.models.content_enhancement import ContentEnhancement
    
    enhancement = db.query(ContentEnhancement).filter(
        ContentEnhancement.enhancement_id == enhancement_id,
        ContentEnhancement.user_id == user_id
    ).first()
    
    if not enhancement:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Enhancement not found"
        )
    
    return enhancement
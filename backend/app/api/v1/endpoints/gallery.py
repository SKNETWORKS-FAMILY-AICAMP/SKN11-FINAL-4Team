from typing import Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
import logging

from app.database import get_async_db
from app.core.security import get_current_user
from app.services.generated_image_service import get_generated_image_service
from app.services.s3_service import get_s3_service

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/images", response_model=Dict[str, Any])
async def get_gallery_images(
    page: int = Query(1, ge=1, description="페이지 번호"),
    page_size: int = Query(10, ge=1, le=100, description="페이지당 항목 수"),
    team_id: Optional[int] = Query(None, description="팀 ID 필터"),
    user_id: Optional[str] = Query(None, description="사용자 ID 필터"),
    db: AsyncSession = Depends(get_async_db),
    current_user: Dict = Depends(get_current_user)
):
    """
    갤러리 이미지 목록 조회 (페이지네이션)
    
    Returns:
        {
            "images": [
                {
                    "id": 1,
                    "storage_id": "uuid",
                    "team_id": 1,
                    "user_id": "user123",
                    "prompt": "A beautiful landscape",
                    "width": 512,
                    "height": 512,
                    "created_at": "2024-01-01T00:00:00",
                    "s3_url": "https://presigned-url..."
                }
            ],
            "pagination": {
                "page": 1,
                "page_size": 10,
                "total_count": 100,
                "total_pages": 10
            }
        }
    """
    try:
        # 사용자가 속한 팀 확인 (JWT payload에서)
        teams = current_user.get("teams", [])
        if not teams:
            return {
                "images": [],
                "pagination": {
                    "page": page,
                    "page_size": page_size,
                    "total_count": 0,
                    "total_pages": 0
                }
            }
        
        # team_id 필터 검증 - 임시로 team_id가 제공되지 않으면 기본 값 1 사용
        if team_id:
            target_team_id = team_id
        else:
            # team_id가 없으면 기본값 1 사용 (실제로는 JWT에서 추출해야 함)
            target_team_id = 1
        
        # 이미지 목록 조회
        generated_image_service = get_generated_image_service()
        result = await generated_image_service.get_images_by_team(
            db=db,
            team_id=target_team_id,
            page=page,
            page_size=page_size,
            user_id=user_id
        )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"갤러리 이미지 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"이미지 목록 조회 실패: {str(e)}")


@router.delete("/images/{storage_id}")
async def delete_gallery_image(
    storage_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: Dict = Depends(get_current_user)
):
    """
    갤러리 이미지 삭제
    """
    try:
        generated_image_service = get_generated_image_service()
        
        # 이미지 조회
        image = await generated_image_service.get_image_by_storage_id(db, storage_id)
        if not image:
            raise HTTPException(status_code=404, detail="이미지를 찾을 수 없습니다.")
        
        # 권한 확인 (임시로 통과시킴 - 실제로는 JWT에서 팀 정보 확인)
        # teams = current_user.get("teams", [])
        # if image.team_id not in teams:
        #     raise HTTPException(status_code=403, detail="이미지 삭제 권한이 없습니다.")
        
        # S3에서 삭제
        s3_service = get_s3_service()
        s3_key = f"generate_image/team_{image.team_id}/{image.user_id}/{image.storage_id}.png"
        
        try:
            await s3_service.delete_file(s3_key)
        except Exception as e:
            logger.warning(f"S3 파일 삭제 실패 (계속 진행): {e}")
        
        # DB에서 삭제
        success = await generated_image_service.delete_image(
            db=db,
            storage_id=storage_id,
            team_id=image.team_id
        )
        
        if success:
            return {"message": "이미지가 삭제되었습니다."}
        else:
            raise HTTPException(status_code=500, detail="이미지 삭제 실패")
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"이미지 삭제 실패: {e}")
        raise HTTPException(status_code=500, detail=f"이미지 삭제 실패: {str(e)}")


@router.get("/images/{storage_id}")
async def get_gallery_image_detail(
    storage_id: str,
    db: AsyncSession = Depends(get_async_db),
    current_user: Dict = Depends(get_current_user)
):
    """
    갤러리 이미지 상세 조회
    """
    try:
        generated_image_service = get_generated_image_service()
        
        # 이미지 조회
        image = await generated_image_service.get_image_by_storage_id(db, storage_id)
        if not image:
            raise HTTPException(status_code=404, detail="이미지를 찾을 수 없습니다.")
        
        # 권한 확인 (임시로 통과시킴 - 실제로는 JWT에서 팀 정보 확인)
        # teams = current_user.get("teams", [])
        # if image.team_id not in teams:
        #     raise HTTPException(status_code=403, detail="이미지 조회 권한이 없습니다.")
        
        # S3 presigned URL 생성
        s3_service = get_s3_service()
        s3_key = f"generate_image/team_{image.team_id}/{image.user_id}/{image.storage_id}.png"
        presigned_url = await s3_service.generate_presigned_url(s3_key)
        
        return {
            "id": image.id,
            "storage_id": image.storage_id,
            "team_id": image.team_id,
            "user_id": image.user_id,
            "prompt": image.prompt,
            "negative_prompt": image.negative_prompt,
            "width": image.width,
            "height": image.height,
            "seed": image.seed,
            "workflow_name": image.workflow_name,
            "model_name": image.model_name,
            "metadata": image.metadata,
            "file_size": image.file_size,
            "mime_type": image.mime_type,
            "created_at": image.created_at.isoformat() if image.created_at else None,
            "s3_url": presigned_url
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"이미지 상세 조회 실패: {e}")
        raise HTTPException(status_code=500, detail=f"이미지 상세 조회 실패: {str(e)}")
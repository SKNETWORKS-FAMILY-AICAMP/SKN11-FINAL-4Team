"""
이미지 생성 API 엔드포인트 - 새로운 플로우 구현

사용자 세션 + ComfyUI + S3 저장을 통합한 이미지 생성 API

"""

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel
from typing import Optional, Dict, Any, List
import logging
import asyncio

from app.database import get_db, get_async_db
from app.core.security import get_current_user
from app.services.user_session_service import get_user_session_service
from app.services.image_storage_service import get_image_storage_service
from app.services.comfyui_flux_service import get_comfyui_flux_service
from app.services.prompt_optimization_service import get_prompt_optimization_service
from app.services.s3_service import get_s3_service
from app.models.user import User

logger = logging.getLogger(__name__)

router = APIRouter()


# 요청/응답 스키마
class ImageGenerationRequest(BaseModel):
    """이미지 생성 요청 - Flux 워크플로우 전용"""
    prompt: str
    selected_styles: Optional[Dict[str, str]] = {}  # 스타일 선택 정보
    width: int = 1024
    height: int = 1024
    steps: int = 8  # Flux 기본 스텝 수
    guidance: float = 3.5  # Flux 가이던스 스케일
    seed: Optional[int] = None


class ImageGenerationResponse(BaseModel):
    """이미지 생성 응답"""
    success: bool
    storage_id: Optional[str] = None
    s3_url: Optional[str] = None
    group_id: Optional[int] = None
    generation_time: Optional[float] = None
    session_status: Dict[str, Any] = {}
    message: str


class ImageListResponse(BaseModel):
    """이미지 목록 응답"""
    success: bool
    images: List[Dict[str, Any]] = []
    total_count: int = 0
    message: str


@router.post("/generate", response_model=ImageGenerationResponse)
async def generate_image(
    request: ImageGenerationRequest,
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    이미지 생성 - 새로운 통합 플로우
    
    1. 세션 확인 및 이미지 생성 시작 (10분 타이머)
    2. ComfyUI로 이미지 생성
    3. S3에 저장 및 URL 반환
    4. 세션 상태 리셋 (10분 연장)
    """
    import time
    start_time = time.time()
    
    try:
        user_id = current_user.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="사용자 ID를 찾을 수 없습니다.")
        
        logger.info(f"Starting image generation for user {user_id}")
        logger.info(f"Request data: prompt='{request.prompt[:50]}...', styles={request.selected_styles}, width={request.width}, height={request.height}, steps={request.steps}, guidance={request.guidance}, seed={request.seed}")
        
        # 1. 사용자 및 그룹 정보 조회
        user = await _get_user_with_groups(user_id, db)
        logger.info(f"User lookup result for {user_id}: user={user is not None}, teams={len(user.teams) if user and user.teams else 0}")
        
        if not user:
            raise HTTPException(status_code=400, detail="사용자를 찾을 수 없습니다.")
        
        if not user.teams:
            raise HTTPException(status_code=400, detail="사용자가 그룹에 속해있지 않습니다.")
        
        # 첫 번째 그룹을 기본 그룹으로 사용
        group_id = user.teams[0].group_id
        
        # 2. 세션 확인 및 이미지 생성 시작
        user_session_service = get_user_session_service()
        session_started = await user_session_service.start_image_generation(user_id, db)
        
        if not session_started:
            raise HTTPException(
                status_code=400, 
                detail="이미지 생성을 시작할 수 없습니다. 활성 세션이 없거나 Pod가 준비되지 않았습니다. 페이지를 새로고침해주세요."
            )
        
        # 3. OpenAI로 프롬프트 최적화
        try:
            prompt_service = get_prompt_optimization_service()
            
            # 한국어 + 스타일 선택 → 영문 ComfyUI 최적화 프롬프트
            optimized_prompt = await prompt_service.optimize_flux_prompt(
                user_prompt=request.prompt,
                selected_styles=request.selected_styles
            )
            
            logger.info(f"🤖 프롬프트 최적화 완료:")
            logger.info(f"   원본: '{request.prompt}'")
            logger.info(f"   최적화: '{optimized_prompt}'")
            
        except Exception as e:
            logger.error(f"❌ 프롬프트 최적화 실패: {e}")
            # 최적화 실패 시 원본 프롬프트 사용
            optimized_prompt = request.prompt
        
        # 4. Flux 워크플로우로 이미지 생성
        try:
            flux_service = get_comfyui_flux_service()
            
            # 사용자 세션에서 ComfyUI 엔드포인트 가져오기
            session_status = await user_session_service.get_session_status(user_id, db)
            pod_status = session_status.get("pod_status") if session_status else None
            
            # Pod이 ready, running, processing 상태일 때 이미지 생성 허용
            allowed_statuses = ["ready", "running", "processing"]
            if not session_status or pod_status not in allowed_statuses:
                raise Exception(f"ComfyUI 세션이 준비되지 않았습니다 (현재 상태: {pod_status})")
            
            # ComfyUI 엔드포인트 구성 (RunPod TCP 포트 사용)
            pod_id = session_status.get("pod_id")
            if not pod_id:
                raise Exception("Pod ID를 찾을 수 없습니다")
            
            # RunPod API에서 Pod 정보 조회
            from app.services.runpod_service import get_runpod_service
            runpod_service = get_runpod_service()
            pod_info = await runpod_service.get_pod_status(pod_id)
            
            if not pod_info or not hasattr(pod_info, 'runtime') or not pod_info.runtime:
                raise Exception("ComfyUI 엔드포인트를 찾을 수 없습니다")
            
            # endpoint_url이 이미 RunPodPodResponse에 구성되어 있음
            if not pod_info.endpoint_url:
                raise Exception("ComfyUI 엔드포인트 URL을 구성할 수 없습니다")
            
            comfyui_endpoint = pod_info.endpoint_url
            logger.info(f"🚀 Flux 워크플로우 실행: {comfyui_endpoint}")
            
            # 최적화된 프롬프트로 Flux 워크플로우 실행
            flux_result = await flux_service.generate_image_with_prompt(
                prompt=optimized_prompt,  # 최적화된 프롬프트 사용
                comfyui_endpoint=comfyui_endpoint,
                width=request.width,
                height=request.height,
                guidance=request.guidance,
                steps=request.steps
            )
            
            if not flux_result:
                raise Exception("Flux 워크플로우 실행 실패")
            
            # 생성된 이미지 다운로드
            image_data = await flux_service.download_generated_image(
                comfyui_endpoint=comfyui_endpoint,
                image_info=flux_result
            )
            
            if not image_data:
                raise Exception("생성된 이미지 다운로드 실패")
            
            logger.info(f"✅ Flux 이미지 생성 완료: {len(image_data)} bytes")
        
        except Exception as e:
            logger.error(f"ComfyUI generation failed: {e}")
            # 실패시에도 세션 상태를 ready로 리셋
            await user_session_service.complete_image_generation(user_id, db)
            raise HTTPException(status_code=500, detail=f"이미지 생성 실패: {str(e)}")
        
        # 4. S3에 이미지 업로드
        try:
            s3_service = get_s3_service()
            
            # S3 키 생성 (user_id/timestamp_uuid.png)
            import uuid
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            image_filename = f"{user_id}/{timestamp}_{str(uuid.uuid4())[:8]}.png"
            
            # S3 업로드
            s3_url = await s3_service.upload_image_data(
                image_data=image_data,
                key=image_filename,
                content_type="image/png"
            )
            
            if not s3_url:
                raise Exception("S3 업로드 실패")
            
        except Exception as e:
            logger.error(f"S3 upload failed: {e}")
            # 실패시에도 세션 상태를 ready로 리셋
            await user_session_service.complete_image_generation(user_id, db)
            raise HTTPException(status_code=500, detail=f"이미지 저장 실패: {str(e)}")
        
        # 5. 이미지 저장 레코드 생성
        try:
            image_storage_service = get_image_storage_service()
            storage_id = await image_storage_service.save_generated_image_url(
                s3_url=s3_url,
                group_id=group_id,
                db=db
            )
            
            if not storage_id:
                logger.warning(f"Failed to save image storage record for {s3_url}")
            
        except Exception as e:
            logger.warning(f"Failed to save image storage record: {e}")
            # 저장 레코드 실패해도 이미지 생성은 성공으로 처리
            storage_id = None
        
        # 6. 세션 완료 처리 (10분 연장)
        await user_session_service.complete_image_generation(user_id, db)
        
        # 7. 현재 세션 상태 조회
        session_status = await user_session_service.get_session_status(user_id, db)
        
        generation_time = time.time() - start_time
        
        logger.info(f"Image generation completed for user {user_id}, time: {generation_time:.2f}s")
        
        return ImageGenerationResponse(
            success=True,
            storage_id=storage_id,
            s3_url=s3_url,
            group_id=group_id,
            generation_time=generation_time,
            session_status=session_status or {},
            message=f"이미지가 성공적으로 생성되었습니다. (소요시간: {generation_time:.1f}초)"
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Image generation failed for user {user_id}: {e}")
        # 예외 발생시에도 세션 상태 리셋 시도
        try:
            user_session_service = get_user_session_service()
            await user_session_service.complete_image_generation(user_id, db)
        except:
            pass
        
        raise HTTPException(status_code=500, detail=f"이미지 생성 중 오류 발생: {str(e)}")


@router.get("/my-images", response_model=ImageListResponse)
async def get_my_images(
    limit: int = 20,
    offset: int = 0,
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    사용자의 생성된 이미지 목록 조회
    """
    try:
        user_id = current_user.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="사용자 ID를 찾을 수 없습니다.")
        
        # 이미지 저장 서비스로 사용자 이미지 조회
        image_storage_service = get_image_storage_service()
        images = await image_storage_service.get_user_images(
            user_id=user_id,
            db=db,
            limit=limit,
            offset=offset
        )
        
        return ImageListResponse(
            success=True,
            images=images,
            total_count=len(images),
            message=f"{len(images)}개의 이미지를 조회했습니다."
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get images for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"이미지 목록 조회 중 오류 발생: {str(e)}")


@router.delete("/images/{storage_id}")
async def delete_my_image(
    storage_id: str,
    delete_from_s3: bool = False,
    current_user: Dict = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_db)
):
    """
    사용자의 이미지 삭제
    """
    try:
        user_id = current_user.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="사용자 ID를 찾을 수 없습니다.")
        
        # 이미지 저장 서비스로 이미지 삭제
        image_storage_service = get_image_storage_service()
        success = await image_storage_service.delete_image(
            storage_id=storage_id,
            user_id=user_id,
            db=db,
            delete_from_s3=delete_from_s3
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="이미지를 찾을 수 없거나 삭제 권한이 없습니다.")
        
        return {
            "success": True,
            "storage_id": storage_id,
            "message": "이미지가 성공적으로 삭제되었습니다."
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to delete image {storage_id} for user {user_id}: {e}")
        raise HTTPException(status_code=500, detail=f"이미지 삭제 중 오류 발생: {str(e)}")


@router.get("/health")
async def image_generation_health_check():
    """
    이미지 생성 서비스 상태 확인
    """
    try:
        # 각 서비스 상태 확인
        services_status = {}
        
        try:
            user_session_service = get_user_session_service()
            services_status["user_session"] = "healthy"
        except Exception as e:
            services_status["user_session"] = f"error: {str(e)}"
        
        try:
            image_storage_service = get_image_storage_service()
            services_status["image_storage"] = "healthy"
        except Exception as e:
            services_status["image_storage"] = f"error: {str(e)}"
        
        try:
            comfyui_service = get_comfyui_service()
            services_status["comfyui"] = "healthy"
        except Exception as e:
            services_status["comfyui"] = f"error: {str(e)}"
        
        try:
            s3_service = get_s3_service()
            services_status["s3"] = "healthy"
        except Exception as e:
            services_status["s3"] = f"error: {str(e)}"
        
        return {
            "success": True,
            "service": "image_generation",
            "status": "healthy",
            "services": services_status,
            "message": "이미지 생성 서비스가 정상 작동 중입니다."
        }
        
    except Exception as e:
        logger.error(f"Image generation health check failed: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"이미지 생성 서비스 상태 확인 실패: {str(e)}"
        )


async def _get_user_with_groups(user_id: str, db: AsyncSession) -> Optional[User]:
    """사용자 및 그룹 정보 조회"""
    from sqlalchemy import select
    from sqlalchemy.orm import selectinload
    
    try:
        logger.info(f"Looking up user with ID: {user_id}")
        result = await db.execute(
            select(User)
            .options(selectinload(User.teams))
            .where(User.user_id == user_id)
        )
        user = result.scalar_one_or_none()
        
        if user:
            logger.info(f"Found user: {user.user_id}, teams count: {len(user.teams) if user.teams else 0}")
            if user.teams:
                for team in user.teams:
                    logger.info(f"Team: group_id={team.group_id}, group_name={team.group_name}")
        else:
            logger.warning(f"User not found: {user_id}")
        
        return user
    except Exception as e:
        logger.error(f"Failed to get user with groups {user_id}: {e}")
        return None
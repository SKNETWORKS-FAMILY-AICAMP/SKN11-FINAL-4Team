from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File
from sqlalchemy.orm import Session
from typing import List
import uuid
from sqlalchemy import update
import json
import logging
import os
import shutil
from pathlib import Path

from app.database import get_db
from app.models.board import Board
from app.models.user import User
from app.schemas.board import (
    BoardCreate,
    BoardUpdate,
    Board as BoardSchema,
    BoardWithInfluencer,
    AIContentGenerationRequest,
    AIContentGenerationResponse,
    SimpleContentRequest,
    SimpleContentResponse,
)
from app.api.v1.endpoints.auth import get_current_user
from app.services.content_generation_service import (
    get_content_generation_workflow,
    generate_content_for_board,
    FullContentGenerationRequest
)
from app.services.image_generation_workflow import (
    get_image_generation_workflow_service,
    FullImageGenerationRequest,
    FullImageGenerationResponse
)

router = APIRouter()
logger = logging.getLogger(__name__)

# 파일 업로드 경로 설정
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.post("/upload-image")
async def upload_image(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """이미지 파일 업로드"""
    try:
        user_id = current_user.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication required"
            )
        
        uploaded_files = []
        
        for file in files:
            # 파일 확장자 및 크기 검증
            if not file.content_type.startswith("image/"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid file type: {file.content_type}. Only images are allowed."
                )
            
            # 파일 크기 제한 (10MB)
            file_size = 0
            file_content = await file.read()
            file_size = len(file_content)
            
            if file_size > 10 * 1024 * 1024:  # 10MB
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File too large: {file_size} bytes. Maximum size is 10MB."
                )
            
            # 고유 파일명 생성
            file_extension = file.filename.split(".")[-1] if "." in file.filename else "jpg"
            unique_filename = f"{user_id}_{uuid.uuid4()}.{file_extension}"
            file_path = UPLOAD_DIR / unique_filename
            
            # 파일 저장
            with open(file_path, "wb") as buffer:
                buffer.write(file_content)
            
            # 파일 URL 생성 (상대 경로)
            file_url = f"/uploads/{unique_filename}"
            
            uploaded_files.append({
                "filename": file.filename,
                "saved_filename": unique_filename,
                "file_url": file_url,
                "file_size": file_size,
                "content_type": file.content_type
            })
            
            logger.info(f"File uploaded: {file.filename} -> {unique_filename} ({file_size} bytes)")
        
        return {
            "success": True,
            "message": f"{len(uploaded_files)} files uploaded successfully",
            "files": uploaded_files
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"File upload failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File upload failed: {str(e)}"
        )


@router.get("/", response_model=List[BoardSchema])
async def get_boards(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """게시글 목록 조회"""
    user_id = current_user.get("sub")
    
    boards = (
        db.query(Board)
        .filter(Board.user_id == user_id)
        .offset(skip)
        .limit(limit)
        .all()
    )
    return boards


@router.get("/{board_id}", response_model=BoardWithInfluencer)
async def get_board(
    board_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """특정 게시글 조회"""
    user_id = current_user.get("sub")
    board = (
        db.query(Board)
        .filter(Board.board_id == board_id, Board.user_id == user_id)
        .first()
    )

    if board is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Board not found"
        )
    return board


@router.post("/", response_model=BoardSchema)
async def create_board(
    board_data: BoardCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """새 게시글 생성"""
    user_id = current_user.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User authentication required"
        )
    
    board = Board(
        board_id=str(uuid.uuid4()), 
        user_id=user_id, 
        **board_data.dict(exclude={'user_id'})
    )

    db.add(board)
    db.commit()
    db.refresh(board)

    return board


@router.put("/{board_id}", response_model=BoardSchema)
async def update_board(
    board_id: str,
    board_update: BoardUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """게시글 정보 수정"""
    user_id = current_user.get("sub")
    board = (
        db.query(Board)
        .filter(Board.board_id == board_id, Board.user_id == user_id)
        .first()
    )

    if board is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Board not found"
        )

    # 업데이트할 필드들
    update_data = board_update.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(board, field, value)

    db.commit()
    db.refresh(board)
    return board


@router.delete("/{board_id}")
async def delete_board(
    board_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """게시글 삭제"""
    user_id = current_user.get("sub")
    board = (
        db.query(Board)
        .filter(Board.board_id == board_id, Board.user_id == user_id)
        .first()
    )

    if board is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Board not found"
        )

    db.delete(board)
    db.commit()

    return {"message": "Board deleted successfully"}


@router.post("/{board_id}/publish")
async def publish_board(
    board_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """게시글 발행"""
    user_id = current_user.get("sub")
    board = (
        db.query(Board)
        .filter(Board.board_id == board_id, Board.user_id == user_id)
        .first()
    )

    if board is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Board not found"
        )

    # 게시글 상태를 발행됨으로 변경
    stmt = update(Board).where(Board.board_id == board_id).values(board_status=2)
    db.execute(stmt)
    db.commit()

    return {"message": "Board published successfully"}


# ===================================================================
# 새로운 AI 콘텐츠 생성 엔드포인트들
# ===================================================================

@router.post("/generate-content", response_model=SimpleContentResponse)
async def generate_content_simple(
    request: SimpleContentRequest,
    db: Session = Depends(get_db),
    # current_user: User = Depends(get_current_user),  # 임시로 주석 처리 (테스트용)
):
    """
    간단한 AI 콘텐츠 생성 (프론트엔드 테스트용)
    
    이 엔드포인트는 프론트엔드에서 사용자 입력을 받아
    OpenAI + ComfyUI로 콘텐츠를 생성하는 핵심 워크플로우입니다.
    """
    try:
        logger.info(f"Starting content generation for topic: {request.topic}")
        
        # 플랫폼 번호 매핑
        platform_mapping = {
            "instagram": 0,
            "facebook": 1, 
            "twitter": 2,
            "tiktok": 3
        }
        
        platform_num = platform_mapping.get(request.platform.lower(), 0)
        
        # AI 콘텐츠 생성 서비스 호출
        content_response = await generate_content_for_board(
            topic=request.topic,
            platform=request.platform,
            influencer_id=request.influencer_id,
            user_id="test_user",  # 임시 사용자 ID (인증 활성화 시 current_user.user_id 사용)
            team_id=1,  # 임시 팀 ID
            include_content=request.include_content,
            hashtags=request.hashtags,
            generate_image=request.generate_image
        )
        
        return SimpleContentResponse(
            social_media_content=content_response.social_media_content,
            hashtags=content_response.hashtags,
            images=content_response.generated_images,
            comfyui_prompt=content_response.comfyui_prompt,
            generation_time=content_response.total_generation_time,
            metadata=content_response.metadata
        )
        
    except Exception as e:
        logger.error(f"Content generation failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Content generation failed: {str(e)}"
        )


@router.post("/generate-and-save", response_model=AIContentGenerationResponse)
async def generate_and_save_board(
    request: AIContentGenerationRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),  # 인증 활성화
):
    """
    AI 콘텐츠 생성 + 게시글 DB 저장
    
    완전한 워크플로우:
    1. 사용자 입력 받기
    2. OpenAI로 소셜 미디어 콘텐츠 생성
    3. ComfyUI로 이미지 생성
    4. 게시글 DB에 저장
    5. 결과 반환
    """
    try:
        logger.info(f"Starting full workflow for topic: {request.board_topic}")
        
        # 인증된 사용자 ID 가져오기
        user_id = current_user.get("sub")
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication required"
            )
        
        # 사용자가 해당 팀에 속해 있는지 확인 (eager loading 사용)
        from app.models.user import User
        from sqlalchemy.orm import selectinload
        
        user = db.query(User).options(selectinload(User.teams)).filter(User.user_id == user_id).first()
        if not user:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="User not found"
            )
        
        user_team_ids = [team.group_id for team in user.teams]
        logger.info(f"User {user_id} belongs to teams: {user_team_ids}")
        
        if request.team_id not in user_team_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"User is not a member of team {request.team_id}. User teams: {user_team_ids}"
            )
        
        # 플랫폼 문자열 매핑
        platform_names = {0: "instagram", 1: "facebook", 2: "twitter", 3: "tiktok"}
        platform_name = platform_names.get(request.board_platform, "instagram")
        
        # AI 콘텐츠 생성
        content_response = await generate_content_for_board(
            topic=request.board_topic,
            platform=platform_name,
            influencer_id=request.influencer_id,
            user_id=user_id,  # 실제 사용자 ID 사용
            team_id=request.team_id,
            include_content=request.include_content,
            hashtags=request.hashtags,
            generate_image=request.generate_image
        )
        
        # 게시글 DB 저장
        board_id = str(uuid.uuid4())
        
        # 생성된 이미지 URL들을 JSON 형태로 저장
        image_urls = json.dumps(content_response.generated_images) if content_response.generated_images else "[]"
        
        # 해시태그를 문자열로 변환
        hashtag_str = " ".join(content_response.hashtags) if content_response.hashtags else ""
        
        new_board = Board(
            board_id=board_id,
            influencer_id=request.influencer_id,
            user_id=user_id,  # 실제 사용자 ID 사용
            team_id=request.team_id,  # 스키마에서는 team_id이지만 DB에서는 group_id로 매핑됨
            board_topic=request.board_topic,
            board_description=content_response.social_media_content,
            board_platform=request.board_platform,
            board_hash_tag=hashtag_str,
            board_status=0,  # 최초 생성 상태
            image_url=image_urls,
            reservation_at=request.reservation_at
        )
        
        db.add(new_board)
        db.commit()
        db.refresh(new_board)
        
        logger.info(f"Board saved successfully: {board_id}")
        
        return AIContentGenerationResponse(
            board_id=board_id,
            generated_content=content_response.social_media_content,
            generated_hashtags=content_response.hashtags,
            generated_images=content_response.generated_images,
            comfyui_prompt=content_response.comfyui_prompt,
            generation_id=content_response.generation_id,
            generation_time=content_response.total_generation_time,
            created_at=content_response.created_at,
            openai_metadata=content_response.openai_response.metadata if content_response.openai_response else {},
            comfyui_metadata=content_response.comfyui_response.metadata if content_response.comfyui_response else {}
        )
        
    except Exception as e:
        logger.error(f"Full workflow failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Full workflow failed: {str(e)}"
        )


@router.post("/test-openai")
async def test_openai_only(
    request: SimpleContentRequest,
    db: Session = Depends(get_db),
):
    """OpenAI API만 테스트 (디버깅용)"""
    try:
        from app.services.openai_service_simple import get_openai_service, ContentGenerationRequest
        
        openai_service = get_openai_service()
        
        openai_request = ContentGenerationRequest(
            topic=request.topic,
            platform=request.platform,
            include_content=request.include_content,
            hashtags=request.hashtags
        )
        
        result = await openai_service.generate_social_content(openai_request)
        
        return {
            "content": result.social_media_content,
            "comfyui_prompt": result.english_prompt_for_comfyui,
            "hashtags": result.hashtags,
            "metadata": result.metadata
        }
        
    except Exception as e:
        logger.error(f"OpenAI test failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OpenAI test failed: {str(e)}"
        )


@router.post("/test-comfyui")
async def test_comfyui_only(
    prompt: str = "beautiful landscape, high quality, realistic",
    db: Session = Depends(get_db),
):
    """ComfyUI API만 테스트 (디버깅용)"""
    try:
        from app.services.comfyui_service_simple import get_comfyui_service, ImageGenerationRequest
        
        comfyui_service = get_comfyui_service()
        
        request = ImageGenerationRequest(
            prompt=prompt,
            width=1024,
            height=1024
        )
        
        result = await comfyui_service.generate_image(request)
        
        return {
            "job_id": result.job_id,
            "status": result.status,
            "images": result.images,
            "prompt_used": result.prompt_used,
            "metadata": result.metadata
        }
        
    except Exception as e:
        logger.error(f"ComfyUI test failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"ComfyUI test failed: {str(e)}"
        )


@router.get("/test-user-teams")
async def test_user_teams(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """사용자의 팀 정보 확인 (테스트용)"""
    user_id = current_user.get("sub")
    
    from app.models.user import User
    from sqlalchemy.orm import selectinload
    
    user = db.query(User).options(selectinload(User.teams)).filter(User.user_id == user_id).first()
    if not user:
        return {"error": "User not found"}
    
    user_teams = [{
        "group_id": team.group_id,
        "group_name": team.group_name,
        "group_description": team.group_description
    } for team in user.teams]
    
    return {
        "user_id": user_id,
        "user_name": user.user_name,
        "user_email": user.email,
        "teams": user_teams,
        "team_count": len(user_teams)
    }


# ===================================================================
# RunPod + ComfyUI 이미지 생성 워크플로우 엔드포인트
# ===================================================================

@router.post("/generate-image-full", response_model=FullImageGenerationResponse)
async def generate_image_full_workflow(
    request: FullImageGenerationRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """
    완전한 이미지 생성 워크플로우
    
    전체 흐름:
    1. 사용자 이미지 생성 요청 → DB 저장
    2. RunPod 서버 실행 요청 (ComfyUI 설치된 이미지)
    3. ComfyUI API 준비 상태 확인
    4. OpenAI로 프롬프트 최적화
    5. ComfyUI 워크플로우에 삽입하여 이미지 생성
    6. 생성된 이미지 반환
    7. 작업 완료 후 서버 자동 종료
    """
    try:
        logger.info(f"Starting full image generation workflow for user: {current_user.get('sub')}")
        
        # 사용자 ID 설정
        request.user_id = current_user.get("sub")
        if not request.user_id:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication required"
            )
        
        # 워크플로우 서비스 실행
        workflow_service = get_image_generation_workflow_service()
        result = await workflow_service.generate_image_full_workflow(request, db)
        
        return result
        
    except Exception as e:
        logger.error(f"Full image generation workflow failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Image generation workflow failed: {str(e)}"
        )


@router.get("/generate-image-status/{request_id}", response_model=FullImageGenerationResponse)
async def get_image_generation_status(
    request_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """이미지 생성 상태 조회"""
    try:
        workflow_service = get_image_generation_workflow_service()
        result = await workflow_service.get_generation_status(request_id, db)
        
        if result.status == "not_found":
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Image generation request not found"
            )
        
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get image generation status: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get status: {str(e)}"
        )


@router.post("/cancel-image-generation/{request_id}")
async def cancel_image_generation(
    request_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """이미지 생성 취소"""
    try:
        workflow_service = get_image_generation_workflow_service()
        success = await workflow_service.cancel_generation(request_id, db)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot cancel image generation"
            )
        
        return {"message": "Image generation cancelled successfully"}
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel image generation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel: {str(e)}"
        )


# ===================================================================
# RunPod 관리 엔드포인트 (수동 정리용)
# ===================================================================

@router.get("/runpod/list-active-pods")
async def list_active_runpod_pods(
    current_user: dict = Depends(get_current_user),
):
    """활성 RunPod 목록 조회 (관리자용)"""
    try:
        from app.services.runpod_service import get_runpod_service
        
        runpod_service = get_runpod_service()
        
        if runpod_service.use_mock:
            return {
                "message": "Mock 모드 - 실제 RunPod API 키가 설정되지 않음",
                "active_pods": []
            }
        
        # TODO: RunPod API로 활성 Pod 목록 조회
        # 현재는 DB에서 종료되지 않은 요청들 확인
        from app.models.image_generation import ImageGenerationRequest as DBImageRequest
        from app.database import get_db
        
        db = next(get_db())
        active_requests = db.query(DBImageRequest).filter(
            DBImageRequest.runpod_pod_id.isnot(None),
            DBImageRequest.status.in_(["pending", "processing"])
        ).all()
        
        active_pods = [{
            "request_id": req.request_id,
            "pod_id": req.runpod_pod_id,
            "status": req.status,
            "created_at": req.created_at.isoformat() if req.created_at else None,
            "user_id": req.user_id
        } for req in active_requests]
        
        return {
            "active_pods": active_pods,
            "count": len(active_pods)
        }
        
    except Exception as e:
        logger.error(f"Failed to list active pods: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to list pods: {str(e)}"
        )


@router.post("/runpod/force-cleanup/{pod_id}")
async def force_cleanup_runpod_pod(
    pod_id: str,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """RunPod 강제 정리 (관리자용)"""
    try:
        from app.services.runpod_service import get_runpod_service
        
        runpod_service = get_runpod_service()
        
        logger.info(f"관리자 {current_user.get('sub')}이 Pod {pod_id} 강제 정리 요청")
        
        # Pod 종료 시도
        success = await runpod_service.terminate_pod(pod_id)
        
        # DB에서 해당 요청 찾아서 상태 업데이트
        from app.models.image_generation import ImageGenerationRequest as DBImageRequest
        
        db_request = db.query(DBImageRequest).filter(
            DBImageRequest.runpod_pod_id == pod_id
        ).first()
        
        if db_request:
            db_request.status = "cancelled" if success else "failed"
            db_request.error_message = f"관리자에 의해 강제 {'정리' if success else '정리시도'}됨"
            db_request.completed_at = datetime.utcnow()
            db.commit()
        
        return {
            "success": success,
            "pod_id": pod_id,
            "message": f"Pod {pod_id} {'정리 완료' if success else '정리 시도 (실패 가능)'}"
        }
        
    except Exception as e:
        logger.error(f"Failed to force cleanup pod {pod_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cleanup pod: {str(e)}"
        )


@router.post("/runpod/cleanup-all-orphaned")
async def cleanup_all_orphaned_pods(
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """모든 고아 Pod 정리 (관리자용)"""
    try:
        from app.services.runpod_service import get_runpod_service
        from app.models.image_generation import ImageGenerationRequest as DBImageRequest
        
        runpod_service = get_runpod_service()
        
        logger.info(f"관리자 {current_user.get('sub')}이 모든 고아 Pod 정리 요청")
        
        # 30분 이상 된 처리 중인 요청들 찾기
        from datetime import datetime, timedelta
        
        cutoff_time = datetime.utcnow() - timedelta(minutes=30)
        
        orphaned_requests = db.query(DBImageRequest).filter(
            DBImageRequest.runpod_pod_id.isnot(None),
            DBImageRequest.status.in_(["pending", "processing"]),
            DBImageRequest.created_at < cutoff_time
        ).all()
        
        cleanup_results = []
        
        for req in orphaned_requests:
            try:
                success = await runpod_service.terminate_pod(req.runpod_pod_id)
                
                req.status = "cancelled"
                req.error_message = "30분 이상 지연으로 자동 정리됨"
                req.completed_at = datetime.utcnow()
                
                cleanup_results.append({
                    "request_id": req.request_id,
                    "pod_id": req.runpod_pod_id,
                    "success": success,
                    "age_minutes": (datetime.utcnow() - req.created_at).total_seconds() / 60
                })
                
            except Exception as e:
                logger.error(f"Failed to cleanup orphaned pod {req.runpod_pod_id}: {e}")
                cleanup_results.append({
                    "request_id": req.request_id,
                    "pod_id": req.runpod_pod_id,
                    "success": False,
                    "error": str(e)
                })
        
        db.commit()
        
        successful_cleanups = sum(1 for r in cleanup_results if r.get("success", False))
        
        return {
            "total_orphaned": len(orphaned_requests),
            "successful_cleanups": successful_cleanups,
            "cleanup_results": cleanup_results,
            "message": f"고아 Pod 정리 완료: {successful_cleanups}/{len(orphaned_requests)}"
        }
        
    except Exception as e:
        logger.error(f"Failed to cleanup orphaned pods: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cleanup orphaned pods: {str(e)}"
        )

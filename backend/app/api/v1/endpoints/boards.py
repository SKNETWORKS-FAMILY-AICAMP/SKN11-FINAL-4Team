from fastapi import APIRouter, Depends, HTTPException, status, Query, UploadFile, File, Request
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
from app.services.scheduler_service import scheduler_service

router = APIRouter()
logger = logging.getLogger(__name__)

# 파일 업로드 경로 설정
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)


@router.get("/test-auth")
async def test_auth(
    current_user: dict = Depends(get_current_user),
):
    """인증 테스트 엔드포인트"""
    try:
        user_id = current_user.get("sub")
        logger.info(f"Auth test successful for user: {user_id}")
        return {
            "success": True,
            "user_id": user_id,
            "user_data": current_user
        }
    except Exception as e:
        logger.error(f"Auth test failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Authentication failed: {str(e)}"
        )


@router.post("/upload-test")
async def upload_test(request: Request):
    """인증 없는 업로드 테스트"""
    logger.info("=== UPLOAD TEST ENDPOINT REACHED ===")
    logger.info(f"Request method: {request.method}")
    logger.info(f"Request URL: {request.url}")
    logger.info(f"Request headers: {dict(request.headers)}")
    return {"success": True, "message": "Upload endpoint is working"}


@router.get("/upload-test-get")
async def upload_test_get():
    """GET 테스트"""
    logger.info("GET test endpoint reached!")
    return {"success": True, "message": "GET endpoint is working"}


@router.post("/upload-image-simple")
async def upload_image_simple(
    file: UploadFile = File(...),
    current_user: dict = Depends(get_current_user),
):
    """단순 이미지 업로드"""
    try:
        logger.info("=== Simple upload starting ===")
        
        user_id = current_user.get("sub")
        if not user_id:
            logger.error("Authentication failed in upload")
            raise HTTPException(status_code=401, detail="Authentication required")
        
        logger.info(f"User {user_id} uploading file: {file.filename}")
        logger.info(f"File content type: {file.content_type}")
        
        # 파일 내용 읽기
        content = await file.read()
        logger.info(f"File read successfully: {len(content)} bytes")
        
        # 파일 확장자 확인
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="Only image files are allowed")
        
        # 고유 파일명 생성
        file_extension = file.filename.split(".")[-1] if "." in file.filename else "jpg"
        unique_filename = f"{user_id}_{uuid.uuid4()}.{file_extension}"
        file_path = UPLOAD_DIR / unique_filename
        
        # 파일 저장
        UPLOAD_DIR.mkdir(exist_ok=True)
        with open(file_path, "wb") as buffer:
            buffer.write(content)
        
        # 파일 URL 생성
        file_url = f"/uploads/{unique_filename}"
        
        result = {
            "success": True,
            "filename": file.filename,
            "saved_filename": unique_filename,
            "file_url": file_url,
            "size": len(content),
            "content_type": file.content_type
        }
        
        logger.info(f"=== Upload completed: {file_url} ===")
        return result
        
    except Exception as e:
        logger.error(f"Simple upload failed: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/upload-image")
async def upload_image(
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """이미지 파일 업로드"""
    try:
        logger.info("Starting image upload process")
        
        # 사용자 인증 확인
        user_id = current_user.get("sub")
        if not user_id:
            logger.error("User authentication failed - no user_id")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication required"
            )
        
        logger.info(f"User {user_id} is uploading {len(files)} files")
        
        # 업로드 디렉토리 확인 및 생성
        try:
            UPLOAD_DIR.mkdir(exist_ok=True)
            logger.info(f"Upload directory ensured: {UPLOAD_DIR}")
        except Exception as e:
            logger.error(f"Failed to create upload directory: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Upload directory creation failed"
            )
        
        uploaded_files = []
        
        for i, file in enumerate(files):
            logger.info(f"Processing file {i+1}/{len(files)}: {file.filename}")
            
            # 파일 이름 검증
            if not file.filename:
                logger.error(f"File {i+1} has no filename")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File {i+1} has no filename"
                )
            
            # 파일 확장자 및 크기 검증
            if not file.content_type or not file.content_type.startswith("image/"):
                logger.error(f"Invalid file type: {file.content_type}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid file type: {file.content_type}. Only images are allowed."
                )
            
            # 파일 내용 읽기
            try:
                file_content = await file.read()
                file_size = len(file_content)
                logger.info(f"File {file.filename} read successfully: {file_size} bytes")
            except Exception as e:
                logger.error(f"Failed to read file {file.filename}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Failed to read file {file.filename}"
                )
            
            # 파일 크기 제한 (10MB)
            if file_size > 10 * 1024 * 1024:  # 10MB
                logger.error(f"File too large: {file_size} bytes")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"File too large: {file_size} bytes. Maximum size is 10MB."
                )
            
            # 고유 파일명 생성
            file_extension = file.filename.split(".")[-1] if "." in file.filename else "jpg"
            unique_filename = f"{user_id}_{uuid.uuid4()}.{file_extension}"
            file_path = UPLOAD_DIR / unique_filename
            
            # 파일 저장
            try:
                with open(file_path, "wb") as buffer:
                    buffer.write(file_content)
                logger.info(f"File saved to: {file_path}")
            except Exception as e:
                logger.error(f"Failed to save file {file.filename}: {e}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to save file {file.filename}"
                )
            
            # 파일 URL 생성 (상대 경로)
            file_url = f"/uploads/{unique_filename}"
            
            uploaded_files.append({
                "filename": file.filename,
                "saved_filename": unique_filename,
                "file_url": file_url,
                "file_size": file_size,
                "content_type": file.content_type
            })
            
            logger.info(f"File uploaded successfully: {file.filename} -> {unique_filename} ({file_size} bytes)")
        
        result = {
            "success": True,
            "message": f"{len(uploaded_files)} files uploaded successfully",
            "files": uploaded_files
        }
        
        logger.info(f"Upload process completed successfully for user {user_id}")
        return result
        
    except HTTPException as e:
        logger.error(f"HTTP Exception in upload: {e.detail}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error in file upload: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File upload failed: {str(e)}"
        )


@router.get("", response_model=List[BoardSchema])
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


@router.post("", response_model=BoardSchema)
async def create_board(
    board_data: BoardCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """새 게시글 생성"""
    try:
        logger.info("=== Creating new board ===")
        
        # SQLAlchemy 메타데이터 캐시 강제 초기화
        from app.models.board import Board
        from sqlalchemy import text
        
        user_id = current_user.get("sub")
        if not user_id:
            logger.error("User authentication failed - no user_id")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User authentication required"
            )
        
        logger.info(f"User {user_id} creating board")
        logger.info(f"Board data: {board_data.dict()}")
        
        # Raw SQL로 직접 INSERT하여 SQLAlchemy 메타데이터 캐시 문제 완전 회피
        board_id = str(uuid.uuid4())
        board_dict = board_data.dict()
        
        # 예약 발행인 경우 reservation_at 필드 포함
        if board_dict.get('board_status') == 2 and board_dict.get('scheduled_at'):
            insert_sql = text("""
                INSERT INTO BOARD (
                    board_id, influencer_id, user_id, team_id, group_id, board_topic, 
                    board_description, board_platform, board_hash_tag, 
                    board_status, image_url, reservation_at, created_at, updated_at
                ) VALUES (
                    :board_id, :influencer_id, :user_id, :team_id, :group_id, :board_topic,
                    :board_description, :board_platform, :board_hash_tag,
                    :board_status, :image_url, :reservation_at, NOW(), NOW()
                )
            """)
            
            insert_params = {
                'board_id': board_id,
                'influencer_id': board_dict['influencer_id'],
                'user_id': user_id,
                'team_id': board_dict['team_id'],
                'group_id': board_dict['team_id'],
                'board_topic': board_dict['board_topic'],
                'board_description': board_dict.get('board_description'),
                'board_platform': board_dict['board_platform'],
                'board_hash_tag': board_dict.get('board_hash_tag'),
                'board_status': board_dict.get('board_status', 1),
                'image_url': board_dict['image_url'],
                'reservation_at': board_dict.get('scheduled_at')
            }
        else:
            # 즉시 발행 또는 임시저장인 경우
            insert_sql = text("""
                INSERT INTO BOARD (
                    board_id, influencer_id, user_id, team_id, group_id, board_topic, 
                    board_description, board_platform, board_hash_tag, 
                    board_status, image_url, created_at, updated_at
                ) VALUES (
                    :board_id, :influencer_id, :user_id, :team_id, :group_id, :board_topic,
                    :board_description, :board_platform, :board_hash_tag,
                    :board_status, :image_url, NOW(), NOW()
                )
            """)
            
            insert_params = {
                'board_id': board_id,
                'influencer_id': board_dict['influencer_id'],
                'user_id': user_id,
                'team_id': board_dict['team_id'],
                'group_id': board_dict['team_id'],
                'board_topic': board_dict['board_topic'],
                'board_description': board_dict.get('board_description'),
                'board_platform': board_dict['board_platform'],
                'board_hash_tag': board_dict.get('board_hash_tag'),
                'board_status': board_dict.get('board_status', 1),
                'image_url': board_dict['image_url']
            }
        
        db.execute(insert_sql, insert_params)
        
        db.commit()
        logger.info(f"Board created with raw SQL: {board_id}")
        
        # 예약 발행인 경우 스케줄러에 등록
        if board_dict.get('board_status') == 2 and board_dict.get('scheduled_at'):
            try:
                from datetime import datetime, timezone
                import pytz
                
                # 프론트엔드에서 받은 로컬 시간을 한국 시간으로 처리
                scheduled_time_str = board_dict.get('scheduled_at')
                
                # ISO 형식 문자열을 datetime으로 변환
                if scheduled_time_str.endswith(':00'):
                    # 이미 초가 포함된 경우
                    scheduled_time = datetime.fromisoformat(scheduled_time_str)
                else:
                    # 초가 없는 경우 추가
                    scheduled_time = datetime.fromisoformat(scheduled_time_str + ':00')
                
                # 한국 시간대로 설정 (naive datetime을 한국 시간으로 가정)
                korea_tz = pytz.timezone('Asia/Seoul')
                if scheduled_time.tzinfo is None:
                    scheduled_time = korea_tz.localize(scheduled_time)
                
                await scheduler_service.schedule_post(board_id, scheduled_time)
                logger.info(f"게시글 {board_id} 스케줄링 등록 완료: {scheduled_time} (한국시간)")
            except Exception as e:
                logger.error(f"게시글 {board_id} 스케줄링 등록 실패: {str(e)}")
                # 스케줄링 실패해도 게시글 생성은 성공으로 처리
        
        # 생성된 레코드를 다시 조회하여 반환
        board = db.query(Board).filter(Board.board_id == board_id).first()
        if not board:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Board creation failed - record not found after insert"
            )
        
        logger.info(f"Board created successfully: {board.board_id}")
        return board
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error creating board: {e}", exc_info=True)
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create board: {str(e)}"
        )


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
            image_url=image_urls
            # reservation_at=request.reservation_at  # 나중에 구현
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


@router.get("/comfyui/models")
async def get_comfyui_models(
    db: Session = Depends(get_db),
):
    """ComfyUI 모델 목록 조회"""
    try:
        from app.core.config import settings
        import httpx
        
        # ComfyUI 서버에서 모델 정보 가져오기
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(f"{settings.COMFYUI_SERVER_URL}/object_info")
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="ComfyUI server is not available"
                )
            
            data = response.json()
            
            # 체크포인트 모델 목록 추출
            checkpoint_models = data.get("CheckpointLoaderSimple", {}).get("input", {}).get("required", {}).get("ckpt_name", [[]])[0]
            
            # 모델 목록을 프론트엔드에서 사용하기 쉬운 형태로 변환
            models = [
                {
                    "id": model,
                    "name": model.replace(".ckpt", "").replace(".safetensors", ""),
                    "type": "checkpoint",
                    "description": f"Checkpoint model: {model}"
                }
                for model in checkpoint_models
            ]
            
            return {
                "success": True,
                "models": models
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to fetch ComfyUI models: {e}")
        # 기본 모델들 반환 (ComfyUI가 연결되지 않은 경우)
        return {
            "success": False,
            "error": "Failed to fetch models from ComfyUI",
            "models": [
                {"id": "sd_xl_base_1.0", "name": "Stable Diffusion XL Base", "type": "checkpoint", "description": "Base SDXL model"},
                {"id": "sd_v1-5", "name": "Stable Diffusion v1.5", "type": "checkpoint", "description": "SD 1.5 model"}
            ]
        }


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


# ===================================================================
# 스케줄링 관리 엔드포인트
# ===================================================================

@router.post("/{board_id}/schedule")
async def schedule_board(
    board_id: str,
    scheduled_time: str,  # ISO format datetime string
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """게시글 예약 발행 스케줄링"""
    try:
        user_id = current_user.get("sub")
        
        # 게시글 소유권 확인
        board = (
            db.query(Board)
            .filter(Board.board_id == board_id, Board.user_id == user_id)
            .first()
        )

        if board is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Board not found"
            )
        
        # 날짜 파싱
        from datetime import datetime
        try:
            scheduled_datetime = datetime.fromisoformat(scheduled_time.replace('Z', '+00:00'))
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid datetime format. Use ISO format."
            )
        
        # 현재 시간보다 이후인지 확인
        if scheduled_datetime <= datetime.now():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Scheduled time must be in the future"
            )
        
        # 게시글 상태를 예약으로 변경
        stmt = update(Board).where(Board.board_id == board_id).values(
            board_status=2,  # 예약 상태
            reservation_at=scheduled_datetime
        )
        db.execute(stmt)
        db.commit()
        
        # 스케줄러에 등록
        await scheduler_service.schedule_post(board_id, scheduled_datetime)
        
        logger.info(f"게시글 {board_id} 예약 발행 스케줄링 완료: {scheduled_datetime}")
        
        return {
            "message": "Board scheduled successfully",
            "board_id": board_id,
            "scheduled_time": scheduled_datetime.isoformat()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to schedule board {board_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to schedule board: {str(e)}"
        )


@router.delete("/{board_id}/schedule")
async def cancel_scheduled_board(
    board_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """게시글 예약 발행 취소"""
    try:
        user_id = current_user.get("sub")
        
        # 게시글 소유권 확인
        board = (
            db.query(Board)
            .filter(Board.board_id == board_id, Board.user_id == user_id)
            .first()
        )

        if board is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND, 
                detail="Board not found"
            )
        
        # 예약 상태인지 확인
        if board.board_status != 2:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Board is not scheduled"
            )
        
        # 게시글 상태를 임시저장으로 변경
        stmt = update(Board).where(Board.board_id == board_id).values(
            board_status=1,  # 임시저장 상태
            reservation_at=None
        )
        db.execute(stmt)
        db.commit()
        
        # 스케줄러에서 제거
        success = await scheduler_service.cancel_scheduled_post(board_id)
        
        logger.info(f"게시글 {board_id} 예약 발행 취소 완료")
        
        return {
            "message": "Board schedule cancelled successfully",
            "board_id": board_id,
            "scheduler_cancelled": success
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to cancel scheduled board {board_id}: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to cancel scheduled board: {str(e)}"
        )


@router.get("/scheduler/status")
async def get_scheduler_status(
    current_user: dict = Depends(get_current_user),
):
    """스케줄러 상태 조회"""
    try:
        status = scheduler_service.get_scheduler_status()
        scheduled_jobs = scheduler_service.get_scheduled_jobs()
        
        return {
            "scheduler_status": status,
            "scheduled_jobs": scheduled_jobs,
            "total_scheduled": len(scheduled_jobs)
        }
        
    except Exception as e:
        logger.error(f"Failed to get scheduler status: {str(e)}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get scheduler status: {str(e)}"
        )

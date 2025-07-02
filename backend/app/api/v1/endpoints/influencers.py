from fastapi import APIRouter, Depends, Query, BackgroundTasks
from sqlalchemy.orm import Session
from typing import List, Optional

from app.database import get_db
from app.schemas.influencer import (
    AIInfluencer as AIInfluencerSchema,
    AIInfluencerWithDetails,
    AIInfluencerCreate,
    AIInfluencerUpdate,
    StylePreset as StylePresetSchema,
    StylePresetCreate,
    ModelMBTI as ModelMBTISchema,
)
from app.core.security import get_current_user
from app.services.influencers.crud import (
    get_influencers_list,
    get_influencer_by_id,
    create_influencer,
    update_influencer,
    delete_influencer,
)
from app.services.influencers.style_presets import get_style_presets, create_style_preset
from app.services.influencers.mbti import get_mbti_list
from app.services.influencers.instagram import (
    InstagramConnectRequest,
    connect_instagram_account,
    disconnect_instagram_account,
    get_instagram_status,
)
from app.services.background_tasks import (
    generate_influencer_qa_background,
    get_background_task_manager,
    BackgroundTaskManager
)
from app.services.influencers.qa_generator import QAGenerationTask
from app.services.finetuning_service import get_finetuning_service, InfluencerFineTuningService

router = APIRouter()


@router.get("/", response_model=List[AIInfluencerSchema])
async def get_influencers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """사용자별 AI 인플루언서 목록 조회"""
    user_id = current_user.get("sub")
    return get_influencers_list(db, user_id, skip, limit)


@router.get("/{influencer_id}", response_model=AIInfluencerWithDetails)
async def get_influencer(
    influencer_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """특정 AI 인플루언서 조회"""
    user_id = current_user.get("sub")
    return get_influencer_by_id(db, user_id, influencer_id)


@router.post("/", response_model=AIInfluencerSchema)
async def create_new_influencer(
    influencer_data: AIInfluencerCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """새 AI 인플루언서 생성"""
    user_id = current_user.get("sub")
    
    # 인플루언서 생성
    influencer = create_influencer(db, user_id, influencer_data)
    
    # 백그라운드에서 QA 생성 작업 시작
    background_tasks.add_task(
        generate_influencer_qa_background,
        influencer.influencer_id
    )
    
    return influencer


@router.put("/{influencer_id}", response_model=AIInfluencerSchema)
async def update_existing_influencer(
    influencer_id: str,
    influencer_update: AIInfluencerUpdate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """AI 인플루언서 정보 수정"""
    user_id = current_user.get("sub")
    return update_influencer(db, user_id, influencer_id, influencer_update)


@router.delete("/{influencer_id}")
async def delete_existing_influencer(
    influencer_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """AI 인플루언서 삭제"""
    user_id = current_user.get("sub")
    return delete_influencer(db, user_id, influencer_id)


# 스타일 프리셋 관련 API
@router.get("/style-presets/", response_model=List[StylePresetSchema])
async def get_style_presets_list(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """스타일 프리셋 목록 조회"""
    return get_style_presets(db, skip, limit)


@router.post("/style-presets/", response_model=StylePresetSchema)
async def create_new_style_preset(
    preset_data: StylePresetCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """새 스타일 프리셋 생성"""
    return create_style_preset(db, preset_data)


# MBTI 관련 API
@router.get("/mbti/", response_model=List[ModelMBTISchema])
async def get_mbti_options(
    db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)
):
    """MBTI 목록 조회"""
    return get_mbti_list(db)


# Instagram 비즈니스 계정 연동 관련 API
@router.post("/{influencer_id}/instagram/connect")
async def connect_instagram_business(
    influencer_id: str,
    request: InstagramConnectRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """AI 인플루언서에 Instagram 비즈니스 계정 연동"""
    user_id = current_user.get("sub")
    return await connect_instagram_account(db, user_id, influencer_id, request)


@router.delete("/{influencer_id}/instagram/disconnect")
async def disconnect_instagram_business(
    influencer_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """AI 인플루언서에서 Instagram 비즈니스 계정 연동 해제"""
    user_id = current_user.get("sub")
    return disconnect_instagram_account(db, user_id, influencer_id)


@router.get("/{influencer_id}/instagram/status")
async def get_instagram_connection_status(
    influencer_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """AI 인플루언서의 Instagram 연동 상태 조회"""
    user_id = current_user.get("sub")
    return await get_instagram_status(db, user_id, influencer_id)


# QA 생성 관련 API
@router.post("/{influencer_id}/qa/generate")
async def trigger_qa_generation(
    influencer_id: str,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """AI 인플루언서의 QA 생성 수동 트리거"""
    user_id = current_user.get("sub")
    
    # 인플루언서 존재 확인
    influencer = get_influencer_by_id(db, user_id, influencer_id)
    if not influencer:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="인플루언서를 찾을 수 없습니다")
    
    # 백그라운드에서 QA 생성 작업 시작
    background_tasks.add_task(
        generate_influencer_qa_background,
        influencer_id
    )
    
    return {"message": "QA 생성 작업이 시작되었습니다", "influencer_id": influencer_id}


@router.get("/{influencer_id}/qa/status")
async def get_qa_generation_status(
    influencer_id: str,
    task_id: Optional[str] = Query(None, description="특정 작업 ID로 조회"),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    task_manager: BackgroundTaskManager = Depends(get_background_task_manager),
):
    """AI 인플루언서의 QA 생성 상태 조회"""
    user_id = current_user.get("sub")
    
    # 인플루언서 존재 확인
    influencer = get_influencer_by_id(db, user_id, influencer_id)
    if not influencer:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="인플루언서를 찾을 수 없습니다")
    
    if task_id:
        # 특정 작업 상태 조회
        task = task_manager.get_qa_task_status(task_id)
        if not task or task.influencer_id != influencer_id:
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
        
        return {
            "task_id": task.task_id,
            "influencer_id": task.influencer_id,
            "status": task.status.value,
            "batch_id": task.batch_id,
            "total_qa_pairs": task.total_qa_pairs,
            "generated_qa_pairs": task.generated_qa_pairs,
            "error_message": task.error_message,
            "s3_urls": task.s3_urls,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "is_running": task_manager.is_task_running(task.task_id)
        }
    else:
        # 해당 인플루언서의 모든 작업 조회
        all_tasks = task_manager.get_all_qa_tasks()
        influencer_tasks = [
            {
                "task_id": task.task_id,
                "status": task.status.value,
                "batch_id": task.batch_id,
                "total_qa_pairs": task.total_qa_pairs,
                "generated_qa_pairs": task.generated_qa_pairs,
                "error_message": task.error_message,
                "s3_urls": task.s3_urls,
                "created_at": task.created_at,
                "updated_at": task.updated_at,
                "is_running": task_manager.is_task_running(task.task_id)
            }
            for task in all_tasks.values()
            if task.influencer_id == influencer_id
        ]
        
        return {
            "influencer_id": influencer_id,
            "tasks": influencer_tasks,
            "total_tasks": len(influencer_tasks),
            "running_tasks": len([t for t in influencer_tasks if t["is_running"]])
        }


@router.delete("/{influencer_id}/qa/tasks/{task_id}")
async def cancel_qa_generation(
    influencer_id: str,
    task_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    task_manager: BackgroundTaskManager = Depends(get_background_task_manager),
):
    """AI 인플루언서의 QA 생성 작업 취소"""
    user_id = current_user.get("sub")
    
    # 인플루언서 존재 확인
    influencer = get_influencer_by_id(db, user_id, influencer_id)
    if not influencer:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="인플루언서를 찾을 수 없습니다")
    
    # 작업 존재 확인
    task = task_manager.get_qa_task_status(task_id)
    if not task or task.influencer_id != influencer_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
    
    # 작업 취소
    success = task_manager.cancel_task(task_id)
    
    return {
        "message": "작업 취소 요청이 처리되었습니다" if success else "작업을 취소할 수 없습니다",
        "task_id": task_id,
        "cancelled": success
    }


@router.get("/qa/tasks/status")
async def get_all_qa_tasks_status(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    task_manager: BackgroundTaskManager = Depends(get_background_task_manager),
):
    """모든 QA 생성 작업 상태 조회 (관리자용)"""
    all_tasks = task_manager.get_all_qa_tasks()
    
    return {
        "total_tasks": len(all_tasks),
        "running_tasks": task_manager.get_running_tasks_count(),
        "tasks": [
            {
                "task_id": task.task_id,
                "influencer_id": task.influencer_id,
                "status": task.status.value,
                "batch_id": task.batch_id,
                "total_qa_pairs": task.total_qa_pairs,
                "generated_qa_pairs": task.generated_qa_pairs,
                "error_message": task.error_message,
                "s3_urls": task.s3_urls,
                "created_at": task.created_at,
                "updated_at": task.updated_at,
                "is_running": task_manager.is_task_running(task.task_id)
            }
            for task in all_tasks.values()
        ]
    }


# 파인튜닝 관련 API
@router.get("/{influencer_id}/finetuning/status")
async def get_finetuning_status(
    influencer_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    finetuning_service: InfluencerFineTuningService = Depends(get_finetuning_service),
):
    """AI 인플루언서의 파인튜닝 상태 조회"""
    user_id = current_user.get("sub")
    
    # 인플루언서 존재 확인
    influencer = get_influencer_by_id(db, user_id, influencer_id)
    if not influencer:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="인플루언서를 찾을 수 없습니다")
    
    # 해당 인플루언서의 파인튜닝 작업 조회
    tasks = finetuning_service.get_tasks_by_influencer(influencer_id)
    
    return {
        "influencer_id": influencer_id,
        "finetuning_tasks": [
            {
                "task_id": task.task_id,
                "qa_task_id": task.qa_task_id,
                "status": task.status.value,
                "model_name": task.model_name,
                "hf_repo_id": task.hf_repo_id,
                "hf_model_url": task.hf_model_url,
                "error_message": task.error_message,
                "training_epochs": task.training_epochs,
                "created_at": task.created_at,
                "updated_at": task.updated_at
            }
            for task in tasks
        ],
        "total_tasks": len(tasks),
        "latest_task": tasks[-1].__dict__ if tasks else None
    }


@router.get("/finetuning/tasks/status")
async def get_all_finetuning_tasks_status(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    finetuning_service: InfluencerFineTuningService = Depends(get_finetuning_service),
):
    """모든 파인튜닝 작업 상태 조회 (관리자용)"""
    all_tasks = finetuning_service.get_all_tasks()
    
    return {
        "total_tasks": len(all_tasks),
        "tasks": [
            {
                "task_id": task.task_id,
                "influencer_id": task.influencer_id,
                "qa_task_id": task.qa_task_id,
                "status": task.status.value,
                "model_name": task.model_name,
                "hf_repo_id": task.hf_repo_id,
                "hf_model_url": task.hf_model_url,
                "error_message": task.error_message,
                "training_epochs": task.training_epochs,
                "created_at": task.created_at,
                "updated_at": task.updated_at
            }
            for task in all_tasks.values()
        ]
    }

from fastapi import APIRouter, Depends, Query, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import logging

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
from fastapi import Request
from app.services.influencers.qa_generator import QAGenerationTask, QAGenerationStatus
from app.services.finetuning_service import get_finetuning_service, InfluencerFineTuningService
from datetime import datetime
from app.models import StylePreset, BatchKey

router = APIRouter()
logger = logging.getLogger(__name__)


# 스타일 프리셋 관련 API (구체적인 경로를 먼저 정의)
@router.get("/style-presets", response_model=List[StylePresetSchema])
async def get_style_presets_list(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """스타일 프리셋 목록 조회"""
    logger.info(f"🎯 스타일 프리셋 목록 조회 API 호출됨 - skip: {skip}, limit: {limit}")
    try:
        # StylePreset 모델만 직접 사용하여 순환 참조 문제 회피
        from app.models.influencer import StylePreset
        presets = db.query(StylePreset).offset(skip).limit(limit).all()
        logger.info(f"✅ 프리셋 조회 성공 - 개수: {len(presets)}")
        return presets
    except Exception as e:
        logger.error(f"❌ 프리셋 조회 실패: {str(e)}")
        raise HTTPException(status_code=500, detail=f"프리셋 조회 중 오류 발생: {str(e)}")


@router.post("/style-presets", response_model=StylePresetSchema)
async def create_new_style_preset(
    preset_data: StylePresetCreate,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """새 스타일 프리셋 생성"""
    return create_style_preset(db, preset_data)


@router.get("/style-presets/{style_preset_id}", response_model=StylePresetSchema)
async def get_style_preset_by_id(
    style_preset_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """특정 스타일 프리셋 단일 조회"""
    preset = (
        db.query(StylePreset)
        .filter(StylePreset.style_preset_id == style_preset_id)
        .first()
    )
    if not preset:
        raise HTTPException(status_code=404, detail="StylePreset not found")
    return preset


# MBTI 관련 API
@router.get("/mbti", response_model=List[ModelMBTISchema])
async def get_mbti_options(
    db: Session = Depends(get_db), current_user: dict = Depends(get_current_user)
):
    """MBTI 목록 조회"""
    return get_mbti_list(db)


# 인플루언서 관련 API
@router.get("", response_model=List[AIInfluencerSchema])
async def get_influencers(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """사용자별 AI 인플루언서 목록 조회"""
    user_id = current_user.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")

    return get_influencers_list(db, user_id, skip, limit)


@router.get("/{influencer_id}", response_model=AIInfluencerWithDetails)
async def get_influencer(
    influencer_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """특정 AI 인플루언서 조회"""
    user_id = current_user.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")
    return get_influencer_by_id(db, user_id, influencer_id)


@router.post("", response_model=AIInfluencerSchema)
async def createnew_influencer(
    influencer_data: AIInfluencerCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """새 AI 인플루언서 생성"""
    user_id = current_user.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")
    
    logger.info(f"🚀 API: 인플루언서 생성 요청 - user_id: {user_id}, name: {influencer_data.influencer_name}")
    
    # 인플루언서 생성
    influencer = create_influencer(db, user_id, influencer_data)
    
    # 환경변수로 자동 QA 생성 제어
    auto_qa_enabled = os.getenv('AUTO_FINETUNING_ENABLED', 'true').lower() == 'true'
    logger.info(f"🔧 자동 QA 생성 설정: {auto_qa_enabled}")
    
    if auto_qa_enabled:
        logger.info(f"⚡ 백그라운드 QA 생성 작업 시작 - influencer_id: {influencer.influencer_id}")
        # 백그라운드에서 QA 생성 작업 시작
        background_tasks.add_task(
            generate_influencer_qa_background,
            str(influencer.influencer_id)
        )
    else:
        logger.info("⏸️ 자동 QA 생성이 비활성화되어 있습니다")
    
    logger.info(f"✅ API: 인플루언서 생성 완료 - ID: {influencer.influencer_id}")
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
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")
    return update_influencer(db, user_id, influencer_id, influencer_update)


@router.delete("/{influencer_id}")
async def delete_existing_influencer(
    influencer_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """AI 인플루언서 삭제"""
    user_id = current_user.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")
    return delete_influencer(db, user_id, influencer_id)


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
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")
    print(f"🔍 DEBUG request: {request}")
    return await connect_instagram_account(db, user_id, influencer_id, request)


@router.delete("/{influencer_id}/instagram/disconnect")
async def disconnect_instagram_business(
    influencer_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """AI 인플루언서에서 Instagram 비즈니스 계정 연동 해제"""
    user_id = current_user.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")
    return disconnect_instagram_account(db, user_id, influencer_id)


@router.get("/{influencer_id}/instagram/status")
async def get_instagram_connection_status(
    influencer_id: str,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """AI 인플루언서의 Instagram 연동 상태 조회"""
    user_id = current_user.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")
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
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")
    
    # 인플루언서 존재 확인
    influencer = get_influencer_by_id(db, user_id, influencer_id)
    if not influencer:
        raise HTTPException(status_code=404, detail="인플루언서를 찾을 수 없습니다")
    
    # 환경변수로 자동 QA 생성 제어
    auto_qa_enabled = os.getenv('AUTO_FINETUNING_ENABLED', 'true').lower() == 'true'
    
    if not auto_qa_enabled:
        raise HTTPException(status_code=403, detail="자동 QA 생성이 비활성화되어 있습니다")
    
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
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")
    
    # 인플루언서 존재 확인
    influencer = get_influencer_by_id(db, user_id, influencer_id)
    if not influencer:
        raise HTTPException(status_code=404, detail="인플루언서를 찾을 수 없습니다")
    
    if task_id:
        # 특정 작업 상태 조회 (DB에서)
        batch_key_entry = db.query(BatchKey).filter(BatchKey.task_id == task_id).first()
        
        if not batch_key_entry or str(batch_key_entry.influencer_id) != influencer_id:
            raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")
        
        # 실시간 OpenAI 배치 상태 확인
        openai_batch_status = None
        if batch_key_entry.openai_batch_id:
            try:
                openai_batch_status = task_manager.qa_generator.check_batch_status(str(batch_key_entry.openai_batch_id))
            except Exception as e:
                openai_batch_status = {"error": f"OpenAI 상태 조회 실패: {str(e)}"}
        
        s3_urls = {}
        if batch_key_entry.s3_qa_file_url:
            s3_urls["processed_qa_url"] = str(batch_key_entry.s3_qa_file_url)
        if batch_key_entry.s3_processed_file_url:
            s3_urls["raw_results_url"] = str(batch_key_entry.s3_processed_file_url)

        return {
            "task_id": batch_key_entry.task_id,
            "influencer_id": str(batch_key_entry.influencer_id),
            "status": batch_key_entry.status, # DB에서 직접 상태 가져옴
            "batch_id": batch_key_entry.openai_batch_id,
            "total_qa_pairs": batch_key_entry.total_qa_pairs,
            "generated_qa_pairs": batch_key_entry.generated_qa_pairs,
            "error_message": batch_key_entry.error_message,
            "s3_urls": s3_urls,
            "created_at": batch_key_entry.created_at,
            "updated_at": batch_key_entry.updated_at,
            "is_running": task_manager.is_task_running(task_id), # 백그라운드 태스크 매니저에서 실행 여부 확인
            "openai_batch_status": openai_batch_status  # 실제 OpenAI 상태 추가
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
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")
    
    # 인플루언서 존재 확인
    influencer = get_influencer_by_id(db, user_id, influencer_id)
    if not influencer:
        raise HTTPException(status_code=404, detail="인플루언서를 찾을 수 없습니다")
    
    # 작업 존재 확인
    task = task_manager.qa_generator.get_task_status(task_id)
    if not task or task.influencer_id != influencer_id:
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
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")
    
    # 인플루언서 존재 확인
    influencer = get_influencer_by_id(db, user_id, influencer_id)
    if not influencer:
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


@router.post("/webhooks/openai/batch-complete")
async def handle_openai_batch_webhook(
    request: Request,
    db: Session = Depends(get_db),
    task_manager: BackgroundTaskManager = Depends(get_background_task_manager),
):
    """OpenAI 배치 작업 완료 웹훅 처리"""
    try:
        # 웹훅 데이터 파싱
        webhook_data = await request.json()
        
        # 배치 ID와 상태 추출
        batch_id = webhook_data.get("data", {}).get("id")
        batch_status = webhook_data.get("data", {}).get("status")
        
        if not batch_id:
            return {"error": "배치 ID가 없습니다"}
        
        print(f"🎯 OpenAI 웹훅 수신: batch_id={batch_id}, status={batch_status}")
        
        # 해당 배치 ID를 가진 작업 찾기
        all_tasks = task_manager.get_all_qa_tasks()
        matching_task = None
        task_id = None
        
        for tid, task in all_tasks.items():
            if task.batch_id == batch_id:
                matching_task = task
                task_id = tid
                break
        
        if not matching_task:
            print(f"⚠️ 해당 배치 ID를 가진 작업을 찾을 수 없음: batch_id={batch_id}")
            return {"error": "작업을 찾을 수 없습니다"}
        
        print(f"✅ 작업 발견: task_id={task_id}, influencer_id={matching_task.influencer_id}")
        
        # 배치 완료 시 즉시 처리
        if batch_status == "completed":
            print(f"🚀 배치 완료, 즉시 결과 처리 시작: task_id={task_id}")
            
            # 환경변수로 자동 처리 제어
            auto_qa_enabled = os.getenv('AUTO_FINETUNING_ENABLED', 'true').lower() == 'true'
            
            if not auto_qa_enabled:
                print(f"🔒 자동 QA 처리가 비활성화되어 있습니다 (AUTO_FINETUNING_ENABLED=false)")
                return {"message": "자동 QA 처리가 비활성화되어 있습니다", "task_id": task_id}
            
            # 상태 업데이트
            matching_task.status = QAGenerationStatus.BATCH_COMPLETED
            matching_task.updated_at = datetime.now()
            
            # 백그라운드에서 결과 처리 및 S3 업로드 실행
            import asyncio
            from app.database import get_db
            
            async def process_webhook_result():
                """웹훅 결과 처리를 위한 별도 DB 세션 사용"""
                webhook_db = next(get_db())
                try:
                    await task_manager._process_and_upload_results(task_id, webhook_db)
                finally:
                    webhook_db.close()
            
            asyncio.create_task(process_webhook_result())
            
            return {"message": "배치 완료 웹훅 처리 시작", "task_id": task_id}
        
        elif batch_status == "failed":
            print(f"❌ 배치 실패: task_id={task_id}")
            matching_task.status = QAGenerationStatus.FAILED
            matching_task.error_message = "OpenAI 배치 작업 실패"
            matching_task.updated_at = datetime.now()
            
            return {"message": "배치 실패 처리 완료", "task_id": task_id}
        
        return {"message": "웹훅 수신", "batch_id": batch_id, "status": batch_status}
        
    except Exception as e:
        print(f"❌ 웹훅 처리 중 오류: {str(e)}")
        import traceback
        print(f"상세 오류: {traceback.format_exc()}")
        return {"error": f"웹훅 처리 실패: {str(e)}"}
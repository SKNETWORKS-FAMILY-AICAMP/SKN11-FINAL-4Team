from fastapi import APIRouter, Depends, Query, BackgroundTasks, HTTPException
from sqlalchemy.orm import Session
from typing import List, Optional
import os
import logging
import json
from app.database import get_db
from app.schemas.influencer import (
    AIInfluencer as AIInfluencerSchema,
    AIInfluencerWithDetails,
    AIInfluencerCreate,
    AIInfluencerUpdate,
    StylePreset as StylePresetSchema,
    StylePresetCreate,
    ModelMBTI as ModelMBTISchema,
    FinetuningWebhookRequest,
    ToneGenerationRequest,
    SystemPromptSaveRequest,
)
from app.core.security import get_current_user
from app.services.influencers.crud import (
    get_influencers_list,
    get_influencer_by_id,
    create_influencer,
    update_influencer,
    delete_influencer,
)
from app.services.influencers.style_presets import (
    get_style_presets,
    create_style_preset,
)
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
    BackgroundTaskManager,
)
from fastapi import Request, status
from app.services.influencers.qa_generator import QAGenerationStatus
from app.services.finetuning_service import (
    get_finetuning_service,
    InfluencerFineTuningService,
)
from datetime import datetime
from app.models.influencer import StylePreset, BatchKey, AIInfluencer
from fastapi import HTTPException
from typing import Dict, Any
from openai import OpenAI
import os
import json
from pydantic import BaseModel

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
    auto_qa_enabled = os.getenv("AUTO_FINETUNING_ENABLED", "true").lower() == "true"
    logger.info(f"🔧 자동 QA 생성 설정: {auto_qa_enabled}")

    if auto_qa_enabled:
        logger.info(
            f"⚡ 백그라운드 QA 생성 작업 시작 - influencer_id: {influencer.influencer_id}"
        )
        # 백그라운드에서 QA 생성 작업 시작
        background_tasks.add_task(
            generate_influencer_qa_background, influencer.influencer_id, user_id
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
    req: Request,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """AI 인플루언서에 Instagram 비즈니스 계정 연동"""
    # 원시 요청 데이터 확인
    try:
        body = await req.json()
        print(f"🔍 DEBUG Raw request body: {body}")
    except:
        print("🔍 DEBUG Failed to parse request body")
    
    user_id = current_user.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")
    print(f"🔍 DEBUG influencer_id: {influencer_id}")
    print(f"🔍 DEBUG request: {request}")
    print(f"🔍 DEBUG request.code: {request.code}")
    print(f"🔍 DEBUG request.redirect_uri: {request.redirect_uri}")
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
    auto_qa_enabled = os.getenv("AUTO_FINETUNING_ENABLED", "true").lower() == "true"

    if not auto_qa_enabled:
        raise HTTPException(status_code=403, detail="자동 QA 생성이 비활성화되어 있습니다")
    
    # 백그라운드에서 QA 생성 작업 시작
    background_tasks.add_task(generate_influencer_qa_background, influencer_id)

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
            "is_running": batch_key_entry.status in [
                QAGenerationStatus.PENDING.value, 
                QAGenerationStatus.TONE_GENERATION.value,
                QAGenerationStatus.DOMAIN_PREPARATION.value,
                QAGenerationStatus.PROCESSING.value, 
                QAGenerationStatus.BATCH_SUBMITTED.value, 
                QAGenerationStatus.BATCH_PROCESSING.value,
                QAGenerationStatus.BATCH_UPLOAD.value,
                QAGenerationStatus.PROCESSING_RESULTS.value
            ], # DB 상태 기반으로 실행 여부 판단
            "openai_batch_status": openai_batch_status,  # 실제 OpenAI 상태 추가
        }
    else:
        # 해당 인플루언서의 모든 작업 조회 (DB에서)
        all_tasks_from_db = db.query(BatchKey).filter(BatchKey.influencer_id == influencer_id).order_by(BatchKey.created_at.desc()).all()
        
        influencer_tasks = [
            {
                "task_id": task.task_id,
                "status": task.status,
                "batch_id": task.openai_batch_id,
                "total_qa_pairs": task.total_qa_pairs,
                "generated_qa_pairs": task.generated_qa_pairs,
                "error_message": task.error_message,
                "s3_urls": {
                    "processed_qa_url": task.s3_qa_file_url,
                    "raw_results_url": task.s3_processed_file_url
                } if task.s3_qa_file_url or task.s3_processed_file_url else None,
                "created_at": task.created_at,
                "updated_at": task.updated_at,
                "is_running": task.status in [
                    QAGenerationStatus.PENDING.value, 
                    QAGenerationStatus.TONE_GENERATION.value,
                    QAGenerationStatus.DOMAIN_PREPARATION.value,
                    QAGenerationStatus.PROCESSING.value, 
                    QAGenerationStatus.BATCH_SUBMITTED.value, 
                    QAGenerationStatus.BATCH_PROCESSING.value,
                    QAGenerationStatus.BATCH_UPLOAD.value,
                    QAGenerationStatus.PROCESSING_RESULTS.value
                ],
            }
            for task in all_tasks_from_db
        ]

        return {
            "influencer_id": influencer_id,
            "tasks": influencer_tasks,
            "total_tasks": len(influencer_tasks),
            "running_tasks": len([t for t in influencer_tasks if t["is_running"]]),
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

    # 작업 존재 확인 및 상태 업데이트
    batch_key_entry = db.query(BatchKey).filter(BatchKey.task_id == task_id).first()
    if not batch_key_entry or batch_key_entry.influencer_id != influencer_id:
        raise HTTPException(status_code=404, detail="작업을 찾을 수 없습니다")

    # 이미 완료되거나 실패한 작업은 취소할 수 없음
    if batch_key_entry.status in [QAGenerationStatus.COMPLETED.value, QAGenerationStatus.FAILED.value, QAGenerationStatus.BATCH_COMPLETED.value]:
        raise HTTPException(status_code=400, detail="이미 완료되었거나 실패한 작업은 취소할 수 없습니다.")

    # 상태를 취소로 변경
    batch_key_entry.status = QAGenerationStatus.FAILED.value # 취소도 실패로 간주
    batch_key_entry.error_message = "사용자에 의해 취소됨"
    db.commit()

    # TODO: OpenAI 배치 작업 자체를 취소하는 로직 추가 필요 (API 지원 시)
    # 현재는 DB 상태만 업데이트

    return {
        "message": "작업 취소 요청이 처리되었습니다",
        "task_id": task_id,
        "cancelled": True,
    }


@router.get("/qa/tasks/status")
async def get_all_qa_tasks_status(
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """모든 QA 생성 작업 상태 조회 (관리자용)"""
    # 모든 BatchKey 작업 조회 (DB에서)
    all_tasks_from_db = db.query(BatchKey).order_by(BatchKey.created_at.desc()).all()

    tasks_data = [
        {
            "task_id": task.task_id,
            "influencer_id": task.influencer_id,
            "status": task.status,
            "batch_id": task.openai_batch_id,
            "total_qa_pairs": task.total_qa_pairs,
            "generated_qa_pairs": task.generated_qa_pairs,
            "error_message": task.error_message,
            "s3_urls": {
                "processed_qa_url": task.s3_qa_file_url,
                "raw_results_url": task.s3_processed_file_url
            } if task.s3_qa_file_url or task.s3_processed_file_url else None,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
            "is_running": task.status in [
            QAGenerationStatus.PENDING.value, 
            QAGenerationStatus.TONE_GENERATION.value,
            QAGenerationStatus.DOMAIN_PREPARATION.value,
            QAGenerationStatus.PROCESSING.value, 
            QAGenerationStatus.BATCH_SUBMITTED.value, 
            QAGenerationStatus.BATCH_PROCESSING.value,
            QAGenerationStatus.BATCH_UPLOAD.value,
            QAGenerationStatus.PROCESSING_RESULTS.value
        ],
        }
        for task in all_tasks_from_db
    ]

    return {
        "total_tasks": len(tasks_data),
        "running_tasks": len([t for t in tasks_data if t["is_running"]]),
        "tasks": tasks_data,
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
                "updated_at": task.updated_at,
            }
            for task in tasks
        ],
        "total_tasks": len(tasks),
        "latest_task": tasks[-1].__dict__ if tasks else None,
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
                "updated_at": task.updated_at,
            }
            for task in all_tasks.values()
        ],
    }


@router.post("/webhooks/openai/batch-complete")
async def handle_openai_batch_webhook(
    request: Request,
    db: Session = Depends(get_db),
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

        # 해당 배치 ID를 가진 작업 찾기 (DB에서)
        from app.models.influencer import BatchKey
        batch_key_entry = db.query(BatchKey).filter(BatchKey.openai_batch_id == batch_id).first()

        if not batch_key_entry:
            print(f"⚠️ 해당 배치 ID를 가진 BatchKey를 찾을 수 없음: batch_id={batch_id}")
            return {"error": "작업을 찾을 수 없습니다"}

        print(
            f"✅ BatchKey 발견: task_id={batch_key_entry.task_id}, influencer_id={batch_key_entry.influencer_id}"
        )

        # 배치 완료 시 즉시 처리
        if batch_status == "completed":
            print(f"🚀 배치 완료, 즉시 결과 처리 시작: task_id={batch_key_entry.task_id}")

            # 환경변수로 자동 처리 제어
            auto_qa_enabled = (
                os.getenv("AUTO_FINETUNING_ENABLED", "true").lower() == "true"
            )

            if not auto_qa_enabled:
                print(
                    f"🔒 자동 QA 처리가 비활성화되어 있습니다 (AUTO_FINETUNING_ENABLED=false)"
                )
                # DB 상태만 업데이트
                batch_key_entry.status = QAGenerationStatus.BATCH_COMPLETED.value
                db.commit()
                return {
                    "message": "자동 QA 처리가 비활성화되어 있습니다",
                    "task_id": batch_key_entry.task_id,
                }

            # 상태 업데이트
            batch_key_entry.status = QAGenerationStatus.BATCH_COMPLETED.value
            db.commit()

            # 백그라운드에서 결과 처리 및 S3 업로드 실행
            import asyncio
            from app.database import get_db
            from app.services.influencers.qa_generator import InfluencerQAGenerator

            async def process_webhook_result():
                """웹훅 결과 처리를 위한 별도 DB 세션 사용"""
                webhook_db = next(get_db())
                try:
                    qa_generator_instance = InfluencerQAGenerator() # 새로운 인스턴스 생성
                    await qa_generator_instance.complete_qa_generation(batch_key_entry.task_id, webhook_db)
                finally:
                    webhook_db.close()

            asyncio.create_task(process_webhook_result())

            return {"message": "배치 완료 웹훅 처리 시작", "task_id": batch_key_entry.task_id}

        elif batch_status == "failed":
            print(f"❌ 배치 실패: task_id={batch_key_entry.task_id}")
            batch_key_entry.status = QAGenerationStatus.FAILED.value
            batch_key_entry.error_message = "OpenAI 배치 작업 실패"
            db.commit()

            return {"message": "배치 실패 처리 완료", "task_id": batch_key_entry.task_id}

        # 그 외 상태 (예: validating, in_progress)는 DB에 업데이트
        batch_key_entry.status = batch_status
        db.commit()
        return {"message": "웹훅 수신", "batch_id": batch_id, "status": batch_status}

    except Exception as e:
        print(f"❌ 웹훅 처리 중 오류: {str(e)}")
        import traceback

        print(f"상세 오류: {traceback.format_exc()}")
        return {"error": f"웹훅 처리 실패: {str(e)}"}


@router.post("/webhooks/finetuning-complete")
async def handle_finetuning_webhook(
    webhook_data: FinetuningWebhookRequest,
    db: Session = Depends(get_db),
):
    """파인튜닝 완료 웹훅 처리"""
    logger.info(f"🎯 파인튜닝 웹훅 수신: task_id={webhook_data.task_id}, status={webhook_data.status}")

    try:
        # VLLM task_id로 먼저 찾고, 없으면 일반 task_id로 찾기
        batch_key_entry = db.query(BatchKey).filter(BatchKey.vllm_task_id == webhook_data.task_id).first()
        
        if not batch_key_entry:
            # 하위 호환성을 위해 task_id로도 검색
            batch_key_entry = db.query(BatchKey).filter(BatchKey.task_id == webhook_data.task_id).first()

        if not batch_key_entry:
            logger.warning(f"⚠️ 해당 task_id를 가진 BatchKey를 찾을 수 없음: {webhook_data.task_id}")
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="작업을 찾을 수 없습니다")

        if webhook_data.status == "completed":
            batch_key_entry.status = QAGenerationStatus.FINALIZED.value
            batch_key_entry.hf_model_url = webhook_data.hf_model_url
            batch_key_entry.completed_at = datetime.now()
            logger.info(f"✅ 파인튜닝 완료: task_id={webhook_data.task_id}, 모델 URL={webhook_data.hf_model_url}")
            
            # AIInfluencer 모델 상태를 사용 가능으로 업데이트
            influencer = db.query(AIInfluencer).filter(
                AIInfluencer.influencer_id == batch_key_entry.influencer_id
            ).first()
            
            if influencer:
                influencer.learning_status = 1  # 1: 사용가능
                if webhook_data.hf_model_url:
                    influencer.influencer_model_repo = webhook_data.hf_model_url
                logger.info(f"✅ 인플루언서 모델 상태 업데이트 완료: influencer_id={batch_key_entry.influencer_id}, status=사용 가능")
        elif webhook_data.status == "failed":
            batch_key_entry.status = QAGenerationStatus.FAILED.value
            batch_key_entry.error_message = webhook_data.error_message
            batch_key_entry.completed_at = datetime.now()
            logger.error(f"❌ 파인튜닝 실패: task_id={webhook_data.task_id}, 오류={webhook_data.error_message}")
        else:
            # 기타 상태 업데이트 (예: processing, validating 등)
            batch_key_entry.status = webhook_data.status
            logger.info(f"🔄 파인튜닝 상태 업데이트: task_id={webhook_data.task_id}, 상태={webhook_data.status}")
        
        db.commit()
        return {"message": "파인튜닝 웹훅 처리 완료", "task_id": webhook_data.task_id, "status": webhook_data.status}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 파인튜닝 웹훅 처리 중 오류: {str(e)}", exc_info=True)
        db.rollback()
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=f"파인튜닝 웹훅 처리 실패: {str(e)}")


# 말투 생성 관련 API
@router.post("/generate-tones")
async def generate_conversation_tones(
    request: ToneGenerationRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """성격 기반 말투 생성 API"""
    from app.services.tone_service import ToneGenerationService
    return await ToneGenerationService.generate_conversation_tones(request, False)


@router.post("/regenerate-tones")
async def regenerate_conversation_tones(
    request: ToneGenerationRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """말투 재생성 API"""
    from app.services.tone_service import ToneGenerationService
    return await ToneGenerationService.generate_conversation_tones(request, True)


async def _generate_question_for_character(client: OpenAI, character_info: str, temperature: float = 0.6) -> str:
    """캐릭터 정보에 어울리는 질문을 GPT가 생성하도록 합니다."""
    prompt = f"""
당신은 아래 캐릭터 정보를 바탕으로, 이 캐릭터가 가장 잘 드러날 수 있는 상황이나 일상적인 질문 하나를 한 문장으로 작성해주세요.

[캐릭터 정보]
{character_info}

조건:
- 질문은 반드시 하나만 작성해주세요.
- 질문은 일상적인 대화에서 자연스럽게 나올 수 있는 것이어야 합니다.
- 질문의 말투나 단어 선택도 캐릭터가 잘 드러나도록 유도해주세요.
"""

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "당신은 캐릭터 기반 대화 시나리오 생성 도우미입니다."},
            {"role": "user", "content": prompt}
        ],
        max_tokens=100,
        temperature=temperature
    )

    return response.choices[0].message.content.strip()


async def _generate_three_tones(client: OpenAI, character_info: str, question: str, temperature: float = 0.9) -> List[Dict[str, str]]:
    """캐릭터 정보를 바탕으로 3가지 다른 말투를 생성합니다."""
    
    conversation_examples = []
    
    for i in range(3):
        # 각 말투에 대한 시스템 프롬프트 생성
        system_prompt = await _generate_system_prompt_for_tone(client, character_info, i+1)
        
        # 시스템 프롬프트를 사용해 질문에 대답
        response = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": question}
            ],
            max_tokens=500,
            temperature=temperature
        )
        
        generated_text = response.choices[0].message.content.strip()
        
        # 말투 요약 생성
        tone_summary = await _summarize_speech_style(client, system_prompt)
        
        conversation_examples.append({
            "title": tone_summary.get("description", f"말투 {i+1}"),
            "example": generated_text,
            "tone": tone_summary.get("description", f"말투 {i+1}"),
            "hashtags": tone_summary.get("hashtags", f"#말투{i+1}"),
            "system_prompt": system_prompt
        })
    
    return conversation_examples


async def _generate_system_prompt_for_tone(client: OpenAI, character_info: str, tone_variation: int) -> str:
    """캐릭터 정보를 기반으로 특정 말투에 대한 시스템 프롬프트를 생성합니다."""
    
    tone_instructions = {
        1: "주어진 캐릭터 정보를 바탕으로 첫 번째 독특하고 창의적인 말투로 답변하세요. 캐릭터의 특성을 반영하되 예상치 못한 방식으로 표현해주세요.",
        2: "주어진 캐릭터 정보를 바탕으로 두 번째 독특하고 창의적인 말투로 답변하세요. 첫 번째와는 완전히 다른 새로운 스타일로 표현해주세요.",
        3: "주어진 캐릭터 정보를 바탕으로 세 번째 독특하고 창의적인 말투로 답변하세요. 앞의 두 가지와는 전혀 다른 참신한 방식으로 표현해주세요."
    }
    
    tone_instruction = tone_instructions.get(tone_variation, "캐릭터의 스타일을 반영한 창의적 말투를 사용하세요.")
    
    prompt = f"""
    [요청 조건]
    다음 캐릭터 정보에 기반하여 GPT의 말투 생성에 적합하도록 system prompt를 구성해주세요.
    1. [캐릭터 정보]의 '설명'과 '성격'은 사용자가 입력한 의미를 유지하면서, GPT가 캐릭터의 말투를 자연스럽게 생성할 수 있도록 더 명확하고 생생하게 표현해주세요. 단, 새로운 설정을 추가하거나 의미를 바꾸면 안 돼요.
    2. 이어서 해당 캐릭터 특성을 잘 반영한 [말투 지시사항]과 [주의사항]을 작성해주세요. 표현 방식, 말투, 감정 전달 방식 등 말투에 필요한 구체적인 특징이 드러나야 해요.
    3. 전체 출력 포맷은 아래와 같아야 해요:

    당신은 이제 캐릭터처럼 대화해야 합니다.

    [캐릭터 정보]
    {character_info}

    [말투 지시사항]
    {tone_instruction}

    [주의사항]
    {{캐릭터 특성에 따라 GPT가 직접 판단한 주의사항}}

    모든 내용은 캐릭터 말투 생성을 위한 system prompt 용도로 사용되므로, 형식과 말투의 일관성을 유지해주세요.
    """.strip()

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "아래 캐릭터 정보로 system prompt 전체를 구성해주세요. 문장 표현은 매끄럽고 정리된 스타일로 해주세요."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=1000
    )

    return response.choices[0].message.content.strip()




async def _summarize_speech_style(client: OpenAI, system_prompt: str) -> Dict[str, str]:
    """말투의 시스템 프롬프트를 기반으로 그 말투의 특징을 요약합니다."""
    system_instruction = """
    주어진 말투의 system prompt를 기반으로 그 말투의 특징을 요약해주세요. 반드시 아래 형식을 그대로 지켜서 JSON으로 출력하세요.

    형식:
    {
        "hashtags": "#키워드1 #키워드2 #키워드3",
        "description": "말투 설명 (한 문장, '~말투'로 끝나야 함)"
    }

    조건:
    1. 말투 스타일을 MZ 느낌나게 키워드 3개를 생성해 해시태그 형식으로 작성해 주세요.
    2. 말투 스타일을 한 문장으로 요약해주세요. 반드시 '말투'로 끝나야 합니다. 서술어 없이 명사형으로 끝납니다.
    3. 출력 형식은 반드시 JSON 형식으로 반환해주세요. (추가 설명 없이)
    """

    response = client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": f"말투 지시사항:\n{system_prompt}"}
        ],
        max_tokens=200,
        temperature=0.7
    )

    try:
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        logger.error(f"말투 요약 파싱 실패: {e}")
        return {
            "hashtags": "#GPT #응답파싱 #실패",
            "description": "말투 요약 실패한 말투"
        }


@router.post("/{influencer_id}/system-prompt")
async def save_system_prompt(
    influencer_id: str,
    request: SystemPromptSaveRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
):
    """선택한 시스템 프롬프트를 AI 인플루언서에 저장"""
    user_id = current_user.get("sub")
    
    # 요청 데이터 검증
    if not request.data or not request.data.strip():
        raise HTTPException(status_code=400, detail="시스템 프롬프트 데이터를 입력해주세요")
    
    if request.type not in ["system", "custom"]:
        raise HTTPException(status_code=400, detail="type은 'system' 또는 'custom'이어야 합니다")
    
    try:
        # 인플루언서 조회
        influencer = get_influencer_by_id(db, user_id, influencer_id)
        if not influencer:
            raise HTTPException(status_code=404, detail="인플루언서를 찾을 수 없습니다")
        
        # 시스템 프롬프트 업데이트
        from app.models.influencer import AIInfluencer
        db.query(AIInfluencer).filter(
            AIInfluencer.influencer_id == influencer_id,
            AIInfluencer.user_id == user_id
        ).update({
            "system_prompt": request.data.strip()
        })
        
        db.commit()
        
        logger.info(f"✅ 시스템 프롬프트 저장 완료: influencer_id={influencer_id}, type={request.type}")
        
        return {
            "message": "시스템 프롬프트가 성공적으로 저장되었습니다",
            "influencer_id": influencer_id,
            "type": request.type,
            "system_prompt_saved": True
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"❌ 시스템 프롬프트 저장 중 오류: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail=f"시스템 프롬프트 저장 중 오류가 발생했습니다: {str(e)}")
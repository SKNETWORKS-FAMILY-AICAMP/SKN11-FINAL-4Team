import logging
import time

from fastapi import APIRouter, HTTPException

from app.models import FineTuningRequest, FineTuningResponse, FineTuningStatus, FineTuningStatusResponse
import app.core as core

logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/finetuning/start", response_model=FineTuningResponse)
async def start_finetuning_endpoint(request: FineTuningRequest):
    """파인튜닝 시작"""
    try:
        # 작업 ID 생성
        task_id = f"ft_{request.influencer_id}_{int(time.time())}"
        
        # 작업 정보 저장
        core.finetuning_tasks[task_id] = {
            "task_id": task_id,
            "influencer_id": request.influencer_id,
            "influencer_name": request.influencer_name,
            "personality": request.personality,
            "qa_data": request.qa_data,
            "hf_repo_id": request.hf_repo_id,
            "hf_token": request.hf_token,
            "training_epochs": request.training_epochs,
            "style_info": request.style_info,
            "is_converted": getattr(request, 'is_converted', False),
            "batch_id": request.batch_id,
            "status": FineTuningStatus.PENDING.value,
            "created_at": time.time(),
            "updated_at": time.time()
        }
        
        # 큐 초기화 확인 및 디버깅
        logger.info(f"🔍 디버깅: core.finetuning_queue 상태 = {core.finetuning_queue}")
        logger.info(f"🔍 디버깅: core.finetuning_tasks 개수 = {len(core.finetuning_tasks)}")
        
        if core.finetuning_queue is None:
            logger.error("❌ core.finetuning_queue가 None입니다!")
            raise HTTPException(
                status_code=503,
                detail="서버가 아직 완전히 초기화되지 않았습니다. 잠시 후 다시 시도해주세요."
            )
        
        logger.info(f"🎯 파인튜닝 작업 큐에 추가: {task_id}")
        await core.finetuning_queue.put(task_id) # 큐에 작업 추가
        
        return FineTuningResponse(
            task_id=task_id,
            status=FineTuningStatus.PENDING.value,
            message=f"파인튜닝 작업 {task_id} 시작 요청됨. 백그라운드에서 처리됩니다.",
            hf_repo_id=request.hf_repo_id,
            batch_id=request.batch_id
        )
        
    except Exception as e:
        logger.error(f"❌ 파인튜닝 시작 요청 실패: {e}")
        raise HTTPException(status_code=500, detail=f"파인튜닝 시작 요청 실패: {str(e)}")

@router.get("/finetuning/status/{task_id}", response_model=FineTuningStatusResponse)
async def get_finetuning_status(task_id: str):
    """파인튜닝 상태 조회"""
    if task_id not in core.finetuning_tasks:
        raise HTTPException(status_code=404, detail=f"파인튜닝 작업 {task_id}를 찾을 수 없습니다.")
    
    task = core.finetuning_tasks[task_id]
    
    return FineTuningStatusResponse(
        task_id=task_id,
        status=task["status"],
        progress=task.get("progress"),
        error_message=task.get("error_message"),
        hf_model_url=task.get("hf_model_url"),
        batch_id=task.get("batch_id")
    )

@router.get("/finetuning/tasks")
async def list_finetuning_tasks():
    """파인튜닝 작업 목록"""
    return {
        "tasks": core.finetuning_tasks,
        "total_count": len(core.finetuning_tasks)
    }
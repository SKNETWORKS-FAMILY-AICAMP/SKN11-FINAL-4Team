from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from app.models import LoRALoadRequest
from app import core
from app.core import load_lora_adapter

router = APIRouter()

@router.post("/load_adapter")
async def load_lora_adapter_endpoint(request: LoRALoadRequest):
    """LoRA 어댑터 로드"""
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info(f"🔄 LoRA 어댑터 로드 엔드포인트 호출됨")
    logger.info(f"📋 요청 데이터: {request.dict()}")
    
    logger.info(f"🔍 현재 엔진 상태 확인: {core.engine}")
    if core.engine is None:
        logger.error("❌ 엔진이 초기화되지 않았습니다.")
        raise HTTPException(status_code=500, detail="엔진이 초기화되지 않았습니다.")
    
    logger.info(f"✅ 엔진 상태 확인 완료: {type(core.engine)}")
    
    try:
        logger.info(f"🔄 load_lora_adapter 함수 호출 중...")
        result = await load_lora_adapter(request)
        logger.info(f"✅ load_lora_adapter 함수 실행 완료: {result}")
        return result
        
    except Exception as e:
        logger.error(f"❌ 어댑터 로드 엔드포인트에서 예외 발생: {str(e)}")
        logger.error(f"❌ 예외 타입: {type(e).__name__}")
        import traceback
        logger.error(f"❌ 전체 스택 트레이스: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"어댑터 로드 실패: {str(e)}")

@router.get("/adapters")
async def list_adapters() -> Dict[str, Any]:
    """로드된 어댑터 목록 조회"""
    return {
        "loaded_adapters": core.loaded_adapters,
        "total_count": len(core.loaded_adapters)
    }

@router.delete("/adapter/{model_id}")
async def unload_adapter(model_id: str):
    """어댑터 언로드"""
    if model_id not in core.loaded_adapters:
        raise HTTPException(status_code=404, detail=f"어댑터 {model_id}를 찾을 수 없습니다.")
    
    try:
        del core.loaded_adapters[model_id]
        # logger.info(f"🗑️ LoRA 어댑터 언로드 완료: {model_id}") # logger는 core에서 관리
        
        return {"message": f"어댑터 {model_id} 언로드 완료"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"어댑터 언로드 실패: {str(e)}")

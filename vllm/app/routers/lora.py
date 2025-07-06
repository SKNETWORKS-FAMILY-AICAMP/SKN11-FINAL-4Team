from fastapi import APIRouter, HTTPException
from typing import Dict, Any

from app.models import LoRALoadRequest
from app.core import engine, loaded_adapters, load_lora_adapter

router = APIRouter()

@router.post("/load_adapter")
async def load_lora_adapter_endpoint(request: LoRALoadRequest):
    """LoRA 어댑터 로드"""
    if engine is None:
        raise HTTPException(status_code=500, detail="엔진이 초기화되지 않았습니다.")
    
    try:
        result = await load_lora_adapter(request)
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"어댑터 로드 실패: {str(e)}")

@router.get("/adapters")
async def list_adapters() -> Dict[str, Any]:
    """로드된 어댑터 목록 조회"""
    return {
        "loaded_adapters": loaded_adapters,
        "total_count": len(loaded_adapters)
    }

@router.delete("/adapter/{model_id}")
async def unload_adapter(model_id: str):
    """어댑터 언로드"""
    if model_id not in loaded_adapters:
        raise HTTPException(status_code=404, detail=f"어댑터 {model_id}를 찾을 수 없습니다.")
    
    try:
        del loaded_adapters[model_id]
        # logger.info(f"🗑️ LoRA 어댑터 언로드 완료: {model_id}") # logger는 core에서 관리
        
        return {"message": f"어댑터 {model_id} 언로드 완료"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"어댑터 언로드 실패: {str(e)}")

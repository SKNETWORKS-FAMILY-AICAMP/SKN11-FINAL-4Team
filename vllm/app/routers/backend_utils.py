"""
백엔드 지원 API 엔드포인트
백엔드에서 GPU 처리가 필요한 작업들을 vLLM 서버에서 처리합니다.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import List, Dict, Any
import logging

from app.utils.finetuning_utils import create_system_message, convert_qa_data_for_finetuning

logger = logging.getLogger(__name__)

router = APIRouter()

class SystemMessageRequest(BaseModel):
    influencer_name: str
    personality: str
    style_info: str = ""

class QADataConversionRequest(BaseModel):
    qa_data: List[Dict[str, Any]]
    influencer_name: str
    personality: str
    style_info: str = ""

class QAValidationRequest(BaseModel):
    qa_data: List[Dict[str, Any]]

@router.post("/create-system-message")
async def create_system_message_endpoint(request: SystemMessageRequest):
    """캐릭터 정보를 기반으로 시스템 메시지 생성"""
    try:
        logger.info(f"🎯 시스템 메시지 생성 요청: {request.influencer_name}")
        
        system_message = create_system_message(
            request.influencer_name,
            request.personality,
            request.style_info
        )
        
        logger.info("✅ 시스템 메시지 생성 완료")
        return {"system_message": system_message}
        
    except Exception as e:
        logger.error(f"❌ 시스템 메시지 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=f"시스템 메시지 생성 실패: {str(e)}")

@router.post("/convert-qa-data")
async def convert_qa_data_endpoint(request: QADataConversionRequest):
    """QA 데이터를 파인튜닝용 형식으로 변환"""
    try:
        logger.info(f"🔄 QA 데이터 변환 요청: {len(request.qa_data)}개")
        
        finetuning_data = convert_qa_data_for_finetuning(
            request.qa_data,
            request.influencer_name,
            request.personality,
            request.style_info
        )
        
        logger.info(f"✅ QA 데이터 변환 완료: {len(finetuning_data)}개")
        return {"finetuning_data": finetuning_data}
        
    except Exception as e:
        logger.error(f"❌ QA 데이터 변환 실패: {e}")
        raise HTTPException(status_code=500, detail=f"QA 데이터 변환 실패: {str(e)}")

@router.post("/validate-qa-data")
async def validate_qa_data_endpoint(request: QAValidationRequest):
    """QA 데이터 유효성 검증"""
    try:
        logger.info(f"✅ QA 데이터 검증 요청: {len(request.qa_data)}개")
        
        if not request.qa_data:
            return {"is_valid": False, "reason": "QA 데이터가 비어있습니다"}
        
        valid_count = 0
        total_count = len(request.qa_data)
        
        for i, qa_pair in enumerate(request.qa_data):
            if not isinstance(qa_pair, dict):
                continue
                
            question = qa_pair.get('question', '').strip()
            answer = qa_pair.get('answer', '').strip()
            
            if question and answer:
                valid_count += 1
        
        is_valid = (valid_count / total_count) >= 0.5  # 최소 50% 이상 유효
        
        logger.info(f"✅ QA 데이터 검증 완료: {valid_count}/{total_count}개 유효")
        return {
            "is_valid": is_valid,
            "valid_count": valid_count,
            "total_count": total_count,
            "validity_ratio": valid_count / total_count
        }
        
    except Exception as e:
        logger.error(f"❌ QA 데이터 검증 실패: {e}")
        raise HTTPException(status_code=500, detail=f"QA 데이터 검증 실패: {str(e)}")
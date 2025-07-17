from fastapi import APIRouter, Depends, HTTPException, status, Request
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel
import json
import logging
import os
from app.database import get_db
from app.models.influencer import AIInfluencer
from app.models.voice import VoiceBase, GeneratedVoice
from app.services.vllm_client import get_vllm_client
from app.services.s3_service import get_s3_service
from app.core.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


class VoiceGenerationRequest(BaseModel):
    text: str
    influencer_id: str
    base_voice_url: Optional[str] = None


@router.post("/generate_voice")
async def generate_voice(
    request: VoiceGenerationRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    s3_service = Depends(get_s3_service),
):
    """텍스트를 음성으로 변환"""
    user_id = current_user.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")
    
    # 인플루언서 확인
    influencer = db.query(AIInfluencer).filter(
        AIInfluencer.influencer_id == request.influencer_id,
        AIInfluencer.user_id == user_id
    ).first()
    
    if not influencer:
        raise HTTPException(status_code=404, detail="인플루언서를 찾을 수 없습니다")
    
    # 베이스 음성 확인
    base_voice = db.query(VoiceBase).filter(
        VoiceBase.influencer_id == influencer.id
    ).first()
    
    if not base_voice:
        raise HTTPException(status_code=400, detail="베이스 음성이 설정되지 않았습니다")
    
    # 텍스트 길이 검증
    if len(request.text) > 500:
        raise HTTPException(status_code=400, detail="텍스트는 500자 이하여야 합니다")
    
    try:
        # VLLM 클라이언트로 음성 생성 요청 (베이스 음성 URL 포함)
        vllm_client = await get_vllm_client()
        async with vllm_client as client:
            # 베이스 음성 URL과 함께 음성 생성 요청
            result = await client.generate_voice(
                text=request.text,
                base_voice_url=base_voice.s3_url,
                influencer_id=request.influencer_id
            )
        
        if not result.get("s3_url"):
            raise HTTPException(status_code=500, detail="음성 생성에 실패했습니다")
        
        # 생성된 음성 정보를 데이터베이스에 저장
        generated_voice = GeneratedVoice(
            influencer_id=influencer.id,
            base_voice_id=base_voice.id,
            text=request.text,
            s3_url=result["s3_url"],
            s3_key=result.get("s3_key", ""),
            duration=result.get("duration"),
            file_size=result.get("file_size")
        )
        db.add(generated_voice)
        db.commit()
        
        return {
            "s3_url": result["s3_url"],
            "duration": result.get("duration"),
            "text": request.text,
            "created_at": generated_voice.created_at.isoformat()
        }
        
    except Exception as e:
        logger.error(f"음성 생성 실패: {e}")
        raise HTTPException(status_code=500, detail=str(e))
from fastapi import APIRouter, Depends, HTTPException, status, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from datetime import datetime
from typing import Dict, List, Optional, AsyncGenerator
from pydantic import BaseModel
import json
import logging
import os
import httpx
import asyncio
import base64
from app.database import get_db
from app.models.influencer import AIInfluencer
from app.models.voice import VoiceBase, GeneratedVoice
from app.services.vllm_client import get_vllm_client
from app.services.s3_service import get_s3_service
from app.core.security import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter()


class TTSWebhookRequest(BaseModel):
    task_id: str
    status: str  # completed, failed
    s3_url: Optional[str] = None
    s3_key: Optional[str] = None
    duration: Optional[float] = None
    file_size: Optional[int] = None
    error_message: Optional[str] = None


class VoiceGenerationRequest(BaseModel):
    text: str
    influencer_id: str
    base_voice_url: Optional[str] = None


class StreamingVoiceRequest(BaseModel):
    texts: List[str]  # 문장 단위로 분할된 텍스트 리스트
    influencer_id: str
    chunk_schedule: Optional[List[int]] = None
    chunk_overlap: int = 1


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
        AIInfluencer.influencer_id == request.influencer_id
    ).first()
    
    if not influencer:
        raise HTTPException(status_code=404, detail="인플루언서를 찾을 수 없습니다")
    
    # 베이스 음성 확인
    base_voice = db.query(VoiceBase).filter(
        VoiceBase.influencer_id == influencer.influencer_id
    ).first()
    
    if not base_voice:
        raise HTTPException(status_code=400, detail="베이스 음성이 설정되지 않았습니다")
    
    # 텍스트 길이 검증
    if len(request.text) > 500:
        raise HTTPException(status_code=400, detail="텍스트는 500자 이하여야 합니다")
    
    try:
        # VLLM 서버 상태 확인
        from app.services.vllm_client import vllm_health_check, vllm_generate_voice
        
        vllm_available = await vllm_health_check()
        if not vllm_available:
            logger.error("VLLM 서버를 사용할 수 없습니다")
            raise HTTPException(
                status_code=503, 
                detail="음성 생성 서비스를 사용할 수 없습니다. 잠시 후 다시 시도해주세요."
            )
        
        # S3 presigned URL 생성
        if base_voice.s3_key:
            presigned_url = s3_service.generate_presigned_url(
                s3_key=base_voice.s3_key,
                expiration=3600  # 1시간 유효
            )
        else:
            # s3_key가 없으면 s3_url에서 추출
            import re
            match = re.search(r'amazonaws\.com/(.+)$', base_voice.s3_url)
            if match:
                object_key = match.group(1)
                presigned_url = s3_service.generate_presigned_url(
                    s3_key=object_key,
                    expiration=3600
                )
            else:
                presigned_url = base_voice.s3_url  # fallback
        
        # VLLM 클라이언트로 음성 생성 요청
        logger.info(f"음성 생성 요청: text={request.text[:50]}..., influencer_id={request.influencer_id}")
        
        result = await vllm_generate_voice(
            text=request.text,
            base_voice_url=presigned_url,  # presigned URL 사용
            influencer_id=request.influencer_id
        )
        
        logger.info(f"VLLM 서버 응답: {result}")
        
        if not result:
            logger.error("음성 생성 요청 실패: 응답이 없음")
            raise HTTPException(status_code=500, detail="음성 생성에 실패했습니다")
        
        # 비동기 작업인 경우 (task_id 반환)
        if result.get("status") == "pending" and result.get("task_id"):
            logger.info(f"TTS 생성 작업 시작됨: task_id={result['task_id']}")
            
            # 작업 정보를 데이터베이스에 저장 (상태: pending)
            generated_voice = GeneratedVoice(
                influencer_id=influencer.influencer_id,
                base_voice_id=base_voice.id,
                text=request.text,
                task_id=result["task_id"],
                status="pending",
                s3_url=None,  # 아직 생성되지 않음
                s3_key=None,
                duration=None,
                file_size=None
            )
            db.add(generated_voice)
            db.commit()
            
            return {
                "task_id": result["task_id"],
                "status": "pending",
                "message": "TTS 생성 작업이 시작되었습니다. 잠시 후 음성이 생성됩니다.",
                "text": request.text,
                "created_at": generated_voice.created_at.isoformat()
            }
        
        # 동기 작업인 경우 (즉시 s3_url 반환) - 기존 로직
        elif result.get("s3_url"):
            generated_voice = GeneratedVoice(
                influencer_id=influencer.influencer_id,
                base_voice_id=base_voice.id,
                text=request.text,
                status="completed",
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
                "status": "completed",
                "created_at": generated_voice.created_at.isoformat()
            }
        else:
            logger.error(f"예상치 못한 응답 형식: {result}")
            raise HTTPException(status_code=500, detail="음성 생성에 실패했습니다")
        
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        logger.error(f"음성 생성 실패: {str(e)}")
        logger.error(f"상세 에러: {error_detail}")
        
        # 클라이언트에게는 간단한 메시지만 전달
        error_message = str(e) if str(e) else "음성 생성 중 오류가 발생했습니다"
        raise HTTPException(status_code=500, detail=error_message)


@router.post("/webhook/tts-complete")
async def handle_tts_webhook(
    webhook_data: TTSWebhookRequest,
    db: Session = Depends(get_db),
):
    """TTS 생성 완료 웹훅 처리"""
    logger.info(f"TTS 웹훅 수신: task_id={webhook_data.task_id}, status={webhook_data.status}")
    
    try:
        # task_id로 GeneratedVoice 찾기
        voice = db.query(GeneratedVoice).filter(
            GeneratedVoice.task_id == webhook_data.task_id
        ).first()
        
        if not voice:
            logger.error(f"task_id에 해당하는 음성을 찾을 수 없음: {webhook_data.task_id}")
            raise HTTPException(status_code=404, detail="해당 작업을 찾을 수 없습니다")
        
        # 상태 업데이트
        if webhook_data.status == "completed":
            voice.status = "completed"
            voice.s3_url = webhook_data.s3_url
            voice.s3_key = webhook_data.s3_key
            voice.duration = webhook_data.duration
            voice.file_size = webhook_data.file_size
            logger.info(f"TTS 생성 완료: task_id={webhook_data.task_id}, s3_url={webhook_data.s3_url}")
        
        elif webhook_data.status == "failed":
            voice.status = "failed"
            logger.error(f"TTS 생성 실패: task_id={webhook_data.task_id}, error={webhook_data.error_message}")
        
        db.commit()
        
        return {
            "message": "웹훅 처리 완료",
            "task_id": webhook_data.task_id,
            "status": webhook_data.status
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"웹훅 처리 중 오류: {str(e)}")
        db.rollback()
        raise HTTPException(status_code=500, detail="웹훅 처리 중 오류가 발생했습니다")


@router.post("/stream_voice")
async def stream_voice(
    request: StreamingVoiceRequest,
    db: Session = Depends(get_db),
    current_user: dict = Depends(get_current_user),
    s3_service = Depends(get_s3_service),
):
    """텍스트를 스트리밍 음성으로 변환"""
    user_id = current_user.get("sub")
    if not user_id:
        raise HTTPException(status_code=401, detail="User ID not found")
    
    # 인플루언서 확인
    influencer = db.query(AIInfluencer).filter(
        AIInfluencer.influencer_id == request.influencer_id
    ).first()
    
    if not influencer:
        raise HTTPException(status_code=404, detail="인플루언서를 찾을 수 없습니다")
    
    # 베이스 음성 확인
    base_voice = db.query(VoiceBase).filter(
        VoiceBase.influencer_id == influencer.influencer_id
    ).first()
    
    if not base_voice:
        raise HTTPException(status_code=400, detail="베이스 음성이 설정되지 않았습니다")
    
    # 텍스트 총 길이 검증
    total_length = sum(len(text) for text in request.texts)
    if total_length > 2000:
        raise HTTPException(status_code=400, detail="텍스트 총 길이는 2000자 이하여야 합니다")
    
    async def generate_stream() -> AsyncGenerator[str, None]:
        """SSE 스트림 생성"""
        vllm_url = os.getenv('VLLM_BASE_URL', 'http://localhost:8001')
        stream_endpoint = f"{vllm_url}/zonos/stream_tts_with_voice"
        
        try:
            
            # S3 presigned URL 생성
            if base_voice.s3_key:
                presigned_url = s3_service.generate_presigned_url(
                    s3_key=base_voice.s3_key,
                    expiration=3600
                )
            else:
                import re
                match = re.search(r'amazonaws\.com/(.+)$', base_voice.s3_url)
                if match:
                    object_key = match.group(1)
                    presigned_url = s3_service.generate_presigned_url(
                        s3_key=object_key,
                        expiration=3600
                    )
                else:
                    presigned_url = base_voice.s3_url
            
            # 베이스 음성 다운로드 및 Base64 인코딩
            async with httpx.AsyncClient(verify=False) as client:
                voice_response = await client.get(presigned_url)
                if voice_response.status_code != 200:
                    raise HTTPException(status_code=500, detail="베이스 음성을 가져올 수 없습니다")
                
                voice_data_base64 = base64.b64encode(voice_response.content).decode()
            
            # 초기 이벤트 전송
            yield f"data: {json.dumps({'event': 'start', 'message': '스트리밍 시작', 'influencer_id': request.influencer_id})}\n\n"
            
            # VLLM 서버로 스트리밍 요청 (RunPod는 자체 서명 인증서를 사용할 수 있음)
            async with httpx.AsyncClient(timeout=120.0, verify=False) as client:
                # 스트리밍 요청 데이터
                stream_data = {
                    "texts": request.texts,
                    "voice_data_base64": voice_data_base64,
                    "emotion": [0.3077, 0.0256, 0.0256, 0.0256, 0.0256, 0.0256, 0.2564, 0.3077],  # 중립 감정
                    "chunk_schedule": request.chunk_schedule,
                    "chunk_overlap": request.chunk_overlap
                }
                
                # SSE 스트림 수신
                async with client.stream(
                    'POST',
                    stream_endpoint,
                    json=stream_data,
                    headers={"Accept": "text/event-stream"}
                ) as response:
                    if response.status_code != 200:
                        error_data = await response.aread()
                        logger.error(f"VLLM 스트리밍 오류: {error_data}")
                        yield f"data: {json.dumps({'event': 'error', 'error': 'VLLM 서버 오류'})}\n\n"
                        return
                    
                    # VLLM 서버의 SSE 스트림을 클라이언트로 전달
                    async for line in response.aiter_lines():
                        if line.startswith('data: '):
                            try:
                                # VLLM 데이터 파싱
                                vllm_data = json.loads(line[6:])
                                
                                # 클라이언트에게 전달
                                client_data = {
                                    'event': vllm_data.get('event'),
                                    'influencer_id': request.influencer_id
                                }
                                
                                if vllm_data.get('event') == 'chunk':
                                    client_data['chunk'] = vllm_data.get('chunk')
                                    client_data['sample_rate'] = vllm_data.get('sample_rate')
                                elif vllm_data.get('event') == 'complete':
                                    client_data['message'] = '스트리밍 완료'
                                elif vllm_data.get('event') == 'error':
                                    client_data['error'] = vllm_data.get('error')
                                
                                yield f"data: {json.dumps(client_data)}\n\n"
                                
                                # complete 이벤트면 종료
                                if vllm_data.get('event') == 'complete':
                                    break
                                    
                            except json.JSONDecodeError as e:
                                logger.error(f"JSON 파싱 오류: {e}, line: {line}")
                                continue
                    
        except httpx.ConnectError as e:
            logger.error(f"VLLM 서버 연결 실패: {str(e)}")
            logger.error(f"VLLM URL: {vllm_url}")
            yield f"data: {json.dumps({'event': 'error', 'error': f'VLLM 서버 연결 실패: {vllm_url}'})}\n\n"
        except httpx.TimeoutException:
            logger.error("VLLM 서버 타임아웃")
            yield f"data: {json.dumps({'event': 'error', 'error': '서버 타임아웃'})}\n\n"
        except Exception as e:
            logger.error(f"스트리밍 중 오류: {str(e)}")
            logger.error(f"오류 타입: {type(e).__name__}")
            yield f"data: {json.dumps({'event': 'error', 'error': str(e)})}\n\n"
    
    return StreamingResponse(
        generate_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )
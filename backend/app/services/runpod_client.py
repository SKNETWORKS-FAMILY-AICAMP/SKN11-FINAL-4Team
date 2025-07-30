"""
RunPod Serverless 클라이언트 서비스
TTS(Text-to-Speech) 음성 생성을 위한 RunPod API 통합
"""

import os
import json
import logging
import httpx
import base64
from typing import Optional, Dict, Any
from datetime import datetime

from app.core.config import settings

logger = logging.getLogger(__name__)


class RunPodError(Exception):
    """RunPod 클라이언트 오류"""
    pass


class RunPodClient:
    """RunPod Serverless API 클라이언트"""
    
    def __init__(self):
        self.api_key = os.getenv("RUNPOD_API_KEY", "")
        self.base_url = "https://api.runpod.ai/v2"
        self.timeout = 300  # 5분 타임아웃
        
        if not self.api_key:
            logger.warning("⚠️ RUNPOD_API_KEY가 설정되지 않았습니다")
    
    @property
    def endpoint_id(self) -> str:
        """동적으로 엔드포인트 ID 가져오기"""
        return os.getenv("RUNPOD_ENDPOINT_ID", "tpwska9ui667mu")
    
    @property
    def endpoint_url(self) -> str:
        """RunPod 엔드포인트 URL"""
        return f"{self.base_url}/{self.endpoint_id}/run"
    
    @property
    def status_url(self) -> str:
        """RunPod 상태 확인 URL"""
        return f"{self.base_url}/{self.endpoint_id}/status"
    
    @property
    def headers(self) -> Dict[str, str]:
        """API 요청 헤더"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def health_check(self) -> bool:
        """RunPod 서버 상태 확인"""
        # RunPod serverless는 항상 준비된 상태로 간주
        # 실제 상태는 요청 시 확인됨
        if not self.api_key:
            logger.warning("⚠️ RunPod API 키가 없습니다")
            return False
        
        logger.info(f"✅ RunPod 엔드포인트 준비됨: {self.endpoint_id}")
        return True
    
    async def generate_voice(
        self,
        text: str,
        voice_data_base64: str,
        language: str = "ko",
        influencer_id: str = None,
        base_voice_id: int = None
    ) -> Dict[str, Any]:
        """음성 생성 요청
        
        Args:
            text: 변환할 텍스트
            voice_data_base64: Base64로 인코딩된 음성 데이터
            language: 언어 코드 (기본값: ko)
            influencer_id: 인플루언서 ID
            base_voice_id: 베이스 음성 ID
            
        Returns:
            Dict[str, Any]: RunPod 응답 (task_id, status 등 포함)
        """
        try:
            # 페이로드
            payload = {
                "input": {
                    "text": text,
                    "voice_data_base64": voice_data_base64,
                    "language": language,
                    "influencer_id": influencer_id,  # 인플루언서 ID 추가
                    "base_voice_id": base_voice_id   # 베이스 음성 ID 추가
                }
            }
            
            logger.info(f"🎤 RunPod TTS 요청: text={text[:50]}...")
            logger.info(f"📍 엔드포인트 URL: {self.endpoint_url}")
            logger.info(f"🆔 엔드포인트 ID: {self.endpoint_id}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.endpoint_url,
                    headers=self.headers,
                    json=payload
                )
                
                if response.status_code != 200:
                    error_msg = f"RunPod API 오류: {response.status_code} - {response.text}"
                    logger.error(f"❌ {error_msg}")
                    raise RunPodError(error_msg)
                
                result = response.json()
                logger.info(f"✅ RunPod 요청 성공: {result}")
                
                # RunPod는 비동기 작업을 반환하므로 task_id와 status를 포함
                return {
                    "task_id": result.get("id"),
                    "status": "pending",
                    "runpod_response": result
                }
                
        except httpx.TimeoutException:
            error_msg = "RunPod 요청 시간 초과"
            logger.error(f"❌ {error_msg}")
            raise RunPodError(error_msg)
        except Exception as e:
            logger.error(f"❌ RunPod 음성 생성 실패: {e}")
            raise RunPodError(f"음성 생성 실패: {e}")
    
    async def get_job_status(self, job_id: str) -> Dict[str, Any]:
        """작업 상태 확인
        
        Args:
            job_id: RunPod 작업 ID
            
        Returns:
            Dict[str, Any]: 작업 상태 정보
        """
        try:
            url = f"{self.base_url}/{self.endpoint_id}/status/{job_id}"
            
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get(
                    url,
                    headers=self.headers
                )
                
                if response.status_code != 200:
                    logger.error(f"❌ 작업 상태 확인 실패: {response.status_code}")
                    return {"status": "error", "error": response.text}
                
                return response.json()
                
        except Exception as e:
            logger.error(f"❌ 작업 상태 확인 실패: {e}")
            return {"status": "error", "error": str(e)}
    
    async def download_voice_data(self, voice_url: str) -> str:
        """음성 파일을 다운로드하고 Base64로 인코딩
        
        Args:
            voice_url: 음성 파일 URL (S3 presigned URL 등)
            
        Returns:
            str: Base64로 인코딩된 음성 데이터
        """
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.get(voice_url)
                response.raise_for_status()
                
                voice_data = response.content
                voice_data_base64 = base64.b64encode(voice_data).decode("utf-8")
                
                logger.info(f"✅ 음성 데이터 다운로드 및 인코딩 완료: {len(voice_data_base64)} chars")
                return voice_data_base64
                
        except Exception as e:
            logger.error(f"❌ 음성 데이터 다운로드 실패: {e}")
            raise RunPodError(f"음성 데이터 다운로드 실패: {e}")


# 싱글톤 인스턴스
_runpod_client = None


def get_runpod_client() -> RunPodClient:
    """RunPod 클라이언트 싱글톤 인스턴스 반환"""
    global _runpod_client
    if _runpod_client is None:
        _runpod_client = RunPodClient()
    return _runpod_client


# 편의 함수들
async def runpod_health_check() -> bool:
    """RunPod 서버 상태 확인"""
    client = get_runpod_client()
    return await client.health_check()


async def runpod_generate_voice(
    text: str,
    base_voice_url: str,
    influencer_id: str = None,
    base_voice_id: int = None,
    task_id: str = None
) -> Dict[str, Any]:
    """RunPod로 음성 생성 (편의 함수)"""
    client = get_runpod_client()
    
    # 음성 데이터 다운로드 및 Base64 인코딩
    voice_data_base64 = await client.download_voice_data(base_voice_url)
    
    # RunPod 요청 (influencer_id와 base_voice_id를 직접 전달)
    result = await client.generate_voice(
        text=text,
        voice_data_base64=voice_data_base64,
        language="ko",
        influencer_id=influencer_id,  # TTS worker에 전달
        base_voice_id=base_voice_id   # TTS worker에 전달
    )
    
    # task_id 추가 (로깅 및 추적용)
    if task_id:
        result["internal_task_id"] = task_id
    
    return result
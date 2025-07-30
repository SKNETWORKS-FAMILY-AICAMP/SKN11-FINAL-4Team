"""
RunPod Serverless 클라이언트
백엔드에서 RunPod 워커를 호출하기 위한 유틸리티
"""
import os
import httpx
import asyncio
import logging
from typing import Dict, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)

class RunPodEndpoint(Enum):
    """RunPod 엔드포인트 정의"""
    TTS = "tts"
    LLM = "llm"
    EMBEDDING = "embedding"
    FINETUNING = "finetuning"

class RunPodClient:
    """RunPod Serverless API 클라이언트"""
    
    def __init__(self):
        self.api_key = os.getenv("RUNPOD_API_KEY")
        self.base_url = "https://api.runpod.ai/v2"
        
        # 엔드포인트 ID 설정 (환경변수에서 가져옴)
        self.endpoints = {
            RunPodEndpoint.TTS: os.getenv("RUNPOD_TTS_ENDPOINT_ID"),
            RunPodEndpoint.LLM: os.getenv("RUNPOD_LLM_ENDPOINT_ID"),
            RunPodEndpoint.EMBEDDING: os.getenv("RUNPOD_EMBEDDING_ENDPOINT_ID"),
            RunPodEndpoint.FINETUNING: os.getenv("RUNPOD_FINETUNING_ENDPOINT_ID")
        }
        
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def run_async(
        self,
        endpoint: RunPodEndpoint,
        input_data: Dict[str, Any],
        webhook_url: Optional[str] = None
    ) -> Dict[str, Any]:
        """비동기 작업 실행"""
        endpoint_id = self.endpoints.get(endpoint)
        if not endpoint_id:
            raise ValueError(f"엔드포인트 ID가 설정되지 않았습니다: {endpoint}")
        
        url = f"{self.base_url}/{endpoint_id}/run"
        
        payload = {
            "input": input_data
        }
        
        if webhook_url:
            payload["webhook"] = webhook_url
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                headers=self.headers,
                timeout=30.0
            )
            
            if response.status_code != 200:
                raise Exception(f"RunPod API 오류: {response.status_code} - {response.text}")
            
            return response.json()
    
    async def run_sync(
        self,
        endpoint: RunPodEndpoint,
        input_data: Dict[str, Any],
        timeout: int = 300
    ) -> Dict[str, Any]:
        """동기 작업 실행 (완료까지 대기)"""
        endpoint_id = self.endpoints.get(endpoint)
        if not endpoint_id:
            raise ValueError(f"엔드포인트 ID가 설정되지 않았습니다: {endpoint}")
        
        url = f"{self.base_url}/{endpoint_id}/runsync"
        
        payload = {
            "input": input_data
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                json=payload,
                headers=self.headers,
                timeout=timeout
            )
            
            if response.status_code != 200:
                raise Exception(f"RunPod API 오류: {response.status_code} - {response.text}")
            
            return response.json()
    
    async def get_status(self, endpoint: RunPodEndpoint, job_id: str) -> Dict[str, Any]:
        """작업 상태 확인"""
        endpoint_id = self.endpoints.get(endpoint)
        if not endpoint_id:
            raise ValueError(f"엔드포인트 ID가 설정되지 않았습니다: {endpoint}")
        
        url = f"{self.base_url}/{endpoint_id}/status/{job_id}"
        
        async with httpx.AsyncClient() as client:
            response = await client.get(
                url,
                headers=self.headers,
                timeout=10.0
            )
            
            if response.status_code != 200:
                raise Exception(f"RunPod API 오류: {response.status_code} - {response.text}")
            
            return response.json()
    
    async def cancel_job(self, endpoint: RunPodEndpoint, job_id: str) -> Dict[str, Any]:
        """작업 취소"""
        endpoint_id = self.endpoints.get(endpoint)
        if not endpoint_id:
            raise ValueError(f"엔드포인트 ID가 설정되지 않았습니다: {endpoint}")
        
        url = f"{self.base_url}/{endpoint_id}/cancel/{job_id}"
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                url,
                headers=self.headers,
                timeout=10.0
            )
            
            if response.status_code != 200:
                raise Exception(f"RunPod API 오류: {response.status_code} - {response.text}")
            
            return response.json()
    
    async def health_check(self, endpoint: RunPodEndpoint) -> bool:
        """엔드포인트 상태 확인"""
        endpoint_id = self.endpoints.get(endpoint)
        if not endpoint_id:
            return False
        
        url = f"{self.base_url}/{endpoint_id}/health"
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers=self.headers,
                    timeout=5.0
                )
                return response.status_code == 200
        except:
            return False

# 싱글톤 인스턴스
_runpod_client = None

def get_runpod_client() -> RunPodClient:
    """RunPod 클라이언트 싱글톤 인스턴스 반환"""
    global _runpod_client
    if _runpod_client is None:
        _runpod_client = RunPodClient()
    return _runpod_client
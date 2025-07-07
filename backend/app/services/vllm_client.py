"""
VLLM 서버 클라이언트 서비스
FastAPI 백엔드에서 VLLM 서버로 요청을 라우팅하는 클라이언트
"""

import asyncio
import json
import logging
import httpx
import websockets
from typing import Optional, Dict, List, Any, AsyncIterator
from datetime import datetime
from dataclasses import dataclass
from enum import Enum

from app.core.config import settings

logger = logging.getLogger(__name__)


class VLLMClientError(Exception):
    """VLLM 클라이언트 오류"""
    pass


@dataclass
class VLLMServerConfig:
    """VLLM 서버 설정"""
    base_url: str
    timeout: int = 300
    
    @property
    def ws_url(self) -> str:
        # HTTP -> WS 변환 (http:// -> ws://, https:// -> wss://)
        return self.base_url.replace("http://", "ws://").replace("https://", "wss://")


class VLLMClient:
    """VLLM 서버 클라이언트"""
    
    def __init__(self, config: Optional[VLLMServerConfig] = None):
        self.config = config or VLLMServerConfig()
        self.client = httpx.AsyncClient(
            base_url=self.config.base_url,
            timeout=httpx.Timeout(self.config.timeout)
        )
        
    async def __aenter__(self):
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()
    
    async def health_check(self) -> bool:
        """VLLM 서버 상태 확인"""
        try:
            response = await self.client.get("/")
            return response.status_code == 200
        except Exception as e:
            logger.error(f"VLLM 서버 상태 확인 실패: {e}")
            return False
    
    async def get_stats(self) -> Dict[str, Any]:
        """VLLM 서버 통계 조회"""
        try:
            response = await self.client.get("/stats")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"VLLM 서버 통계 조회 실패: {e}")
            raise VLLMClientError(f"서버 통계 조회 실패: {e}")
    
    async def load_adapter(self, model_id: str, hf_repo_name: str, 
                          hf_token: Optional[str] = None) -> Dict[str, Any]:
        """LoRA 어댑터 로드"""
        try:
            payload = {
                "model_id": model_id,
                "hf_repo_name": hf_repo_name
            }
            if hf_token:
                payload["hf_token"] = hf_token
            
            response = await self.client.post("/load_adapter", json=payload)
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"✅ 어댑터 로드 성공: {model_id}")
            return result
            
        except Exception as e:
            logger.error(f"❌ 어댑터 로드 실패: {model_id}, {e}")
            raise VLLMClientError(f"어댑터 로드 실패: {e}")
    
    async def generate_response(self, user_message: str, system_message: str = None,
                              influencer_name: str = "어시스턴트", model_id: str = None,
                              max_new_tokens: int = 150, temperature: float = 0.7) -> Dict[str, Any]:
        """응답 생성"""
        try:
            payload = {
                "user_message": user_message,
                "system_message": system_message or "당신은 도움이 되는 AI 어시스턴트입니다.",
                "influencer_name": influencer_name,
                "max_new_tokens": max_new_tokens,
                "temperature": temperature,
                "do_sample": True,
                "use_chat_template": True
            }
            if model_id:
                payload["model_id"] = model_id
            
            response = await self.client.post("/generate", json=payload)
            response.raise_for_status()
            
            result = response.json()
            logger.debug(f"✅ 응답 생성 성공: {influencer_name}")
            return result
            
        except Exception as e:
            logger.error(f"❌ 응답 생성 실패: {e}")
            raise VLLMClientError(f"응답 생성 실패: {e}")
    
    async def list_adapters(self) -> Dict[str, Any]:
        """로드된 어댑터 목록 조회"""
        try:
            response = await self.client.get("/adapters")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"어댑터 목록 조회 실패: {e}")
            raise VLLMClientError(f"어댑터 목록 조회 실패: {e}")
    
    async def unload_adapter(self, model_id: str) -> Dict[str, Any]:
        """어댑터 언로드"""
        try:
            response = await self.client.delete(f"/adapter/{model_id}")
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"✅ 어댑터 언로드 성공: {model_id}")
            return result
            
        except Exception as e:
            logger.error(f"❌ 어댑터 언로드 실패: {model_id}, {e}")
            raise VLLMClientError(f"어댑터 언로드 실패: {e}")
    
    async def start_finetuning(self, influencer_id: str, influencer_name: str,
                             personality: str, qa_data: List[Dict], hf_repo_id: str,
                             hf_token: str, training_epochs: int = 5,
                             style_info: str = "", is_converted: bool = False) -> Dict[str, Any]:
        """파인튜닝 시작"""
        try:
            payload = {
                "influencer_id": influencer_id,
                "influencer_name": influencer_name,
                "personality": personality,
                "qa_data": qa_data,
                "hf_repo_id": hf_repo_id,
                "hf_token": hf_token,
                "training_epochs": training_epochs,
                "style_info": style_info,
                "is_converted": is_converted
            }
            
            response = await self.client.post("/finetuning/start", json=payload)
            response.raise_for_status()
            
            result = response.json()
            logger.info(f"✅ 파인튜닝 시작 성공: {influencer_id}")
            return result
            
        except Exception as e:
            logger.error(f"❌ 파인튜닝 시작 실패: {influencer_id}, {e}")
            raise VLLMClientError(f"파인튜닝 시작 실패: {e}")
    
    async def get_finetuning_status(self, task_id: str) -> Dict[str, Any]:
        """파인튜닝 상태 조회"""
        try:
            response = await self.client.get(f"/finetuning/status/{task_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"파인튜닝 상태 조회 실패: {task_id}, {e}")
            raise VLLMClientError(f"파인튜닝 상태 조회 실패: {e}")
    
    async def list_finetuning_tasks(self) -> Dict[str, Any]:
        """파인튜닝 작업 목록 조회"""
        try:
            response = await self.client.get("/finetuning/tasks")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"파인튜닝 작업 목록 조회 실패: {e}")
            raise VLLMClientError(f"파인튜닝 작업 목록 조회 실패: {e}")


class VLLMWebSocketClient:
    """VLLM WebSocket 클라이언트"""
    
    def __init__(self, config: Optional[VLLMServerConfig] = None):
        self.config = config or VLLMServerConfig()
        self.websocket = None
    
    async def connect(self, lora_repo: str):
        """WebSocket 연결"""
        try:
            # Base64 인코딩 (기존 호환성 유지)
            import base64
            encoded_repo = base64.b64encode(lora_repo.encode('utf-8')).decode('utf-8')
            
            ws_url = f"{self.config.ws_url}/ws/chat/{encoded_repo}"
            self.websocket = await websockets.connect(ws_url)
            logger.info(f"🔗 VLLM WebSocket 연결 성공: {lora_repo}")
            
        except Exception as e:
            logger.error(f"❌ VLLM WebSocket 연결 실패: {e}")
            raise VLLMClientError(f"WebSocket 연결 실패: {e}")
    
    async def send_message(self, message: str, system_message: str = None,
                          influencer_name: str = "어시스턴트"):
        """메시지 전송"""
        if not self.websocket:
            raise VLLMClientError("WebSocket 연결이 없습니다.")
        
        try:
            payload = {
                "message": message,
                "system_message": system_message or "당신은 도움이 되는 AI 어시스턴트입니다.",
                "influencer_name": influencer_name
            }
            
            await self.websocket.send(json.dumps(payload))
            logger.debug(f"📤 메시지 전송: {message[:50]}...")
            
        except Exception as e:
            logger.error(f"❌ 메시지 전송 실패: {e}")
            raise VLLMClientError(f"메시지 전송 실패: {e}")
    
    async def receive_response(self) -> Dict[str, Any]:
        """응답 수신"""
        if not self.websocket:
            raise VLLMClientError("WebSocket 연결이 없습니다.")
        
        try:
            response = await self.websocket.recv()
            data = json.loads(response)
            logger.debug(f"📥 응답 수신: {data.get('type', 'unknown')}")
            return data
            
        except Exception as e:
            logger.error(f"❌ 응답 수신 실패: {e}")
            raise VLLMClientError(f"응답 수신 실패: {e}")
    
    async def close(self):
        """연결 종료"""
        if self.websocket:
            await self.websocket.close()
            self.websocket = None
            logger.info("🔌 VLLM WebSocket 연결 종료")


_vllm_config = VLLMServerConfig(
    base_url=settings.VLLM_BASE_URL,
    timeout=getattr(settings, 'VLLM_TIMEOUT', 300)
)


async def get_vllm_client() -> VLLMClient:
    """VLLM 클라이언트 의존성 주입용 함수"""
    return VLLMClient(_vllm_config)


# 편의 함수들
async def vllm_health_check() -> bool:
    """VLLM 서버 상태 확인"""
    async with VLLMClient(_vllm_config) as client:
        return await client.health_check()


async def vllm_generate_response(user_message: str, system_message: str = None,
                                influencer_name: str = "어시스턴트", 
                                model_id: str = None, **kwargs) -> str:
    """VLLM에서 응답 생성 (편의 함수)"""
    async with VLLMClient(_vllm_config) as client:
        result = await client.generate_response(
            user_message=user_message,
            system_message=system_message,
            influencer_name=influencer_name,
            model_id=model_id,
            **kwargs
        )
        return result.get("response", "")


async def vllm_load_adapter_if_needed(model_id: str, hf_repo_name: str,
                                     hf_token: str = None) -> bool:
    """필요시 어댑터 로드"""
    async with VLLMClient(_vllm_config) as client:
        try:
            # 로드된 어댑터 목록 확인
            adapters = await client.list_adapters()
            loaded_adapters = adapters.get("loaded_adapters", {})
            
            if model_id in loaded_adapters:
                logger.info(f"♻️ 어댑터 {model_id}는 이미 로드되어 있습니다.")
                return True
            
            # 어댑터 로드
            await client.load_adapter(model_id, hf_repo_name, hf_token)
            return True
            
        except Exception as e:
            logger.error(f"❌ 어댑터 로드 실패: {model_id}, {e}")
            return False
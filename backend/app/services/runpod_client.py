"""
RunPod Serverless 클라이언트 서비스
TTS(Text-to-Speech) 음성 생성을 위한 RunPod API 통합
"""

import os
import json
import logging
import httpx
import base64
from typing import Optional, Dict, Any, AsyncIterator
from datetime import datetime

from app.core.config import settings
from app.services.runpod_endpoint_manager import get_endpoint_manager

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
        self.endpoint_manager = get_endpoint_manager()
        
        if not self.api_key:
            logger.warning("⚠️ RUNPOD_API_KEY가 설정되지 않았습니다")
    
    async def get_endpoint_id(self, endpoint_type: str = "tts") -> str:
        """동적으로 엔드포인트 ID 가져오기"""
        try:
            endpoint_id = await self.endpoint_manager.get_endpoint_id(endpoint_type)
            if endpoint_id:
                return endpoint_id
            # 폴백: 환경 변수에서 가져오기
            fallback_key = f"RUNPOD_{endpoint_type.upper()}_ENDPOINT_ID"
            return os.getenv(fallback_key, "tpwska9ui667mu")
        except Exception as e:
            logger.warning(f"⚠️ 엔드포인트 ID 조회 실패, 폴백 사용: {e}")
            return os.getenv("RUNPOD_ENDPOINT_ID", "tpwska9ui667mu")
    
    async def get_generation_endpoint_id(self) -> str:
        """vLLM Generation 엔드포인트 ID"""
        return await self.get_endpoint_id("vllm")
    
    async def get_endpoint_url(self, endpoint_type: str = "tts") -> str:
        """RunPod 엔드포인트 URL"""
        endpoint_id = await self.get_endpoint_id(endpoint_type)
        return f"{self.base_url}/{endpoint_id}/run"
    
    async def get_status_url(self, endpoint_type: str = "tts") -> str:
        """RunPod 상태 확인 URL"""
        endpoint_id = await self.get_endpoint_id(endpoint_type)
        return f"{self.base_url}/{endpoint_id}/status"
    
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
        base_voice_id: int = None,
        voice_id: int = None
    ) -> Dict[str, Any]:
        """음성 생성 요청
        
        Args:
            text: 변환할 텍스트
            voice_data_base64: Base64로 인코딩된 음성 데이터
            language: 언어 코드 (기본값: ko)
            influencer_id: 인플루언서 ID
            base_voice_id: 베이스 음성 ID
            voice_id: DB에서 생성된 voice ID
            
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
                    "base_voice_id": base_voice_id,  # 베이스 음성 ID 추가
                    "voice_id": voice_id  # DB에서 생성된 ID 추가
                }
            }
            
            endpoint_url = await self.get_endpoint_url("tts")
            endpoint_id = await self.get_endpoint_id("tts")
            
            logger.info(f"🎤 RunPod TTS 요청: text={text[:50]}...")
            logger.info(f"📍 엔드포인트 URL: {endpoint_url}")
            logger.info(f"🆔 엔드포인트 ID: {endpoint_id}")
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    endpoint_url,
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
            endpoint_id = await self.get_endpoint_id("tts")
            url = f"{self.base_url}/{endpoint_id}/status/{job_id}"
            
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
    
    async def generate_text(
        self,
        prompt: str,
        lora_adapter: Optional[str] = None,
        system_message: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 512,
        top_p: float = 0.9,
        stream: bool = False
    ) -> Dict[str, Any]:
        """텍스트 생성 요청
        
        Args:
            prompt: 생성할 텍스트 프롬프트
            lora_adapter: LoRA 어댑터 이름 또는 경로
            system_message: 시스템 메시지
            temperature: 생성 온도
            max_tokens: 최대 토큰 수
            top_p: Top-p 샘플링
            stream: 스트리밍 여부
            
        Returns:
            Dict[str, Any]: RunPod 응답
        """
        try:
            # 페이로드 구성
            payload = {
                "input": {
                    "prompt": prompt,
                    "system_message": system_message,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "top_p": top_p,
                    "stream": stream
                }
            }
            
            # LoRA 어댑터가 있으면 추가
            if lora_adapter:
                payload["input"]["lora_adapter"] = lora_adapter
            
            logger.info(f"🤖 RunPod 텍스트 생성 요청: prompt={prompt[:50]}...")
            
            # Generation 엔드포인트 URL
            generation_endpoint_id = await self.get_generation_endpoint_id()
            generation_url = f"{self.base_url}/{generation_endpoint_id}/run"
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    generation_url,
                    headers=self.headers,
                    json=payload
                )
                
                if response.status_code != 200:
                    error_msg = f"RunPod API 오류: {response.status_code} - {response.text}"
                    logger.error(f"❌ {error_msg}")
                    raise RunPodError(error_msg)
                
                result = response.json()
                logger.info(f"✅ RunPod 텍스트 생성 요청 성공: {result}")
                
                return result
                
        except httpx.TimeoutException:
            error_msg = "RunPod 요청 시간 초과"
            logger.error(f"❌ {error_msg}")
            raise RunPodError(error_msg)
        except Exception as e:
            logger.error(f"❌ RunPod 텍스트 생성 실패: {e}")
            raise RunPodError(f"텍스트 생성 실패: {e}")
    
    async def generate_text_stream(
        self,
        prompt: str,
        lora_adapter: Optional[str] = None,
        system_message: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 512,
        top_p: float = 0.9
    ) -> AsyncIterator[str]:
        """텍스트 생성 스트리밍
        
        Args:
            prompt: 생성할 텍스트 프롬프트
            lora_adapter: LoRA 어댑터 이름 또는 경로
            system_message: 시스템 메시지
            temperature: 생성 온도
            max_tokens: 최대 토큰 수
            top_p: Top-p 샘플링
            
        Yields:
            str: 생성된 텍스트 토큰
        """
        try:
            # 페이로드 구성
            payload = {
                "input": {
                    "prompt": prompt,
                    "system_message": system_message,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "top_p": top_p,
                    "stream": True
                }
            }
            
            # LoRA 어댑터가 있으면 추가
            if lora_adapter:
                payload["input"]["lora_adapter"] = lora_adapter
            
            logger.info(f"🤖 RunPod 텍스트 스트리밍 요청: prompt={prompt[:50]}...")
            
            # Generation 엔드포인트 URL
            generation_endpoint_id = await self.get_generation_endpoint_id()
            generation_url = f"{self.base_url}/{generation_endpoint_id}/stream"
            
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                async with client.stream(
                    "POST",
                    generation_url,
                    headers=self.headers,
                    json=payload
                ) as response:
                    if response.status_code != 200:
                        error_text = await response.aread()
                        error_msg = f"RunPod API 오류: {response.status_code} - {error_text.decode()}"
                        logger.error(f"❌ {error_msg}")
                        yield f"오류: {error_msg}"
                        return
                    
                    async for line in response.aiter_lines():
                        if line.startswith("data: "):
                            try:
                                data = json.loads(line[6:])
                                if "text" in data:
                                    yield data["text"]
                                elif "error" in data:
                                    logger.error(f"❌ RunPod 스트리밍 오류: {data['error']}")
                                    yield f"오류: {data['error']}"
                                    break
                                elif "done" in data and data["done"]:
                                    break
                            except json.JSONDecodeError:
                                logger.warning(f"⚠️ JSON 파싱 실패: {line}")
                                continue
                
        except httpx.TimeoutException:
            error_msg = "RunPod 스트리밍 시간 초과"
            logger.error(f"❌ {error_msg}")
            yield f"오류: {error_msg}"
        except Exception as e:
            logger.error(f"❌ RunPod 텍스트 스트리밍 실패: {e}")
            yield f"오류: 텍스트 생성 실패 - {e}"
    
    async def download_lora_adapter(
        self,
        adapter_name: str,
        hf_repo_id: str,
        hf_token: Optional[str] = None
    ) -> Dict[str, Any]:
        """LoRA 어댑터 다운로드 요청
        
        Args:
            adapter_name: 어댑터 이름
            hf_repo_id: HuggingFace 레포지토리 ID
            hf_token: HuggingFace 토큰 (private repo의 경우)
            
        Returns:
            Dict[str, Any]: 다운로드 결과
        """
        try:
            generation_endpoint_id = await self.get_generation_endpoint_id()
            return await self.endpoint_manager.download_lora_adapter(
                endpoint_id=generation_endpoint_id,
                adapter_name=adapter_name,
                hf_repo_id=hf_repo_id,
                hf_token=hf_token
            )
        except Exception as e:
            logger.error(f"❌ LoRA 어댑터 다운로드 요청 실패: {e}")
            raise RunPodError(f"LoRA 어댑터 다운로드 실패: {e}")


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
    voice_id: int = None
) -> Dict[str, Any]:
    """RunPod로 음성 생성 (편의 함수)"""
    client = get_runpod_client()
    
    # 음성 데이터 다운로드 및 Base64 인코딩
    voice_data_base64 = await client.download_voice_data(base_voice_url)
    
    # RunPod 요청 (influencer_id, base_voice_id, voice_id를 직접 전달)
    result = await client.generate_voice(
        text=text,
        voice_data_base64=voice_data_base64,
        language="ko",
        influencer_id=influencer_id,  # TTS worker에 전달
        base_voice_id=base_voice_id,   # TTS worker에 전달
        voice_id=voice_id  # TTS worker에 전달 (DB ID)
    )
    
    return result


async def runpod_generate_text(
    prompt: str,
    lora_adapter: Optional[str] = None,
    system_message: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 512,
    stream: bool = False
) -> Dict[str, Any]:
    """RunPod로 텍스트 생성 (편의 함수)"""
    client = get_runpod_client()
    return await client.generate_text(
        prompt=prompt,
        lora_adapter=lora_adapter,
        system_message=system_message,
        temperature=temperature,
        max_tokens=max_tokens,
        stream=stream
    )


async def runpod_generate_text_stream(
    prompt: str,
    lora_adapter: Optional[str] = None,
    system_message: Optional[str] = None,
    temperature: float = 0.7,
    max_tokens: int = 512
) -> AsyncIterator[str]:
    """RunPod로 텍스트 스트리밍 생성 (편의 함수)"""
    client = get_runpod_client()
    async for token in client.generate_text_stream(
        prompt=prompt,
        lora_adapter=lora_adapter,
        system_message=system_message,
        temperature=temperature,
        max_tokens=max_tokens
    ):
        yield token


async def runpod_download_lora_adapter(
    adapter_name: str,
    hf_repo_id: str,
    hf_token: Optional[str] = None
) -> Dict[str, Any]:
    """RunPod로 LoRA 어댑터 다운로드 (편의 함수)"""
    client = get_runpod_client()
    return await client.download_lora_adapter(
        adapter_name=adapter_name,
        hf_repo_id=hf_repo_id,
        hf_token=hf_token
    )
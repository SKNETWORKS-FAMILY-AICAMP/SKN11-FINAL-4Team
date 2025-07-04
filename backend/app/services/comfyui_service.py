"""
ComfyUI API 서비스

SOLID 원칙:
- SRP: ComfyUI API 연동 및 이미지 생성만 담당
- OCP: 새로운 이미지 생성 모델이나 워크플로우 추가 시 확장 가능
- LSP: 추상 인터페이스를 구현하여 다른 이미지 생성 서비스로 교체 가능
- ISP: 클라이언트별 인터페이스 분리
- DIP: 구체적인 ComfyUI 구현이 아닌 추상화에 의존

Clean Architecture:
- Domain Layer: 이미지 생성 비즈니스 로직
- Infrastructure Layer: 외부 ComfyUI API 연동
"""

import asyncio
import json
import uuid
import requests
from typing import Dict, List, Optional, Any, Callable
from abc import ABC, abstractmethod
from pydantic import BaseModel
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


# 요청/응답 모델 정의 (Clean Architecture - Domain Layer)
class ImageGenerationRequest(BaseModel):
    """이미지 생성 요청 모델"""
    prompt: str
    negative_prompt: Optional[str] = "low quality, blurry, distorted"
    width: int = 1024
    height: int = 1024
    steps: int = 20
    cfg_scale: float = 7.0
    seed: Optional[int] = None
    style: str = "realistic"


class ImageGenerationResponse(BaseModel):
    """이미지 생성 응답 모델"""
    job_id: str
    status: str  # "queued", "processing", "completed", "failed"
    images: List[str] = []  # Base64 이미지 또는 URL 리스트
    prompt_used: str
    generation_time: Optional[float] = None
    metadata: Dict[str, Any] = {}


# 추상 인터페이스 (SOLID - DIP 원칙)
class ImageGeneratorInterface(ABC):
    """이미지 생성 추상 인터페이스"""
    
    @abstractmethod
    async def generate_image(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        """이미지 생성"""
        pass
    
    @abstractmethod
    async def get_generation_status(self, job_id: str) -> ImageGenerationResponse:
        """생성 상태 조회"""
        pass


class ComfyUIService(ImageGeneratorInterface):
    """
    ComfyUI API 서비스 구현
    
    SOLID 원칙 준수:
    - SRP: ComfyUI API 호출과 워크플로우 관리만 담당
    - OCP: 새로운 워크플로우 템플릿 추가 시 확장 가능
    """
    
    def __init__(self, comfyui_server_url: str = "http://127.0.0.1:8188"):
        self.server_url = comfyui_server_url
        self.client_id = str(uuid.uuid4())
        self.use_mock = True  # 기본적으로 Mock 모드 (ComfyUI 서버 없을 때)
        
        # ComfyUI 서버 연결 테스트
        self._test_connection()
        
        logger.info(f"ComfyUI Service initialized (Server: {self.server_url}, Mock mode: {self.use_mock})")
    
    def _test_connection(self):
        """ComfyUI 서버 연결 테스트"""
        try:
            response = requests.get(f"{self.server_url}/system_stats", timeout=5)
            if response.status_code == 200:
                self.use_mock = False
                logger.info("ComfyUI server connection successful")
            else:
                logger.warning(f"ComfyUI server responded with status {response.status_code}")
        except requests.exceptions.RequestException as e:
            logger.warning(f"ComfyUI server not available: {e}")
            self.use_mock = True
    
    async def generate_image(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        """
        이미지 생성
        
        Clean Architecture: 비즈니스 로직과 외부 서비스 분리
        """
        try:
            if self.use_mock:
                return await self._generate_mock_image(request)
            else:
                return await self._generate_real_image(request)
        except Exception as e:
            logger.error(f"Image generation failed: {e}")
            # 실패 시 Mock 데이터로 폴백
            return await self._generate_mock_image(request)
    
    async def get_generation_status(self, job_id: str) -> ImageGenerationResponse:
        """생성 상태 조회"""
        if self.use_mock:
            return await self._get_mock_status(job_id)
        else:
            return await self._get_real_status(job_id)
    
    async def _generate_real_image(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        """실제 ComfyUI API 호출"""
        
        try:
            # ComfyUI 워크플로우 JSON 생성
            workflow = self._create_workflow(request)
            
            # ComfyUI 서버에 요청 전송
            job_id = str(uuid.uuid4())
            
            # 큐에 워크플로우 추가
            queue_response = requests.post(
                f"{self.server_url}/prompt",
                json={
                    "prompt": workflow,
                    "client_id": self.client_id
                }
            )
            
            if queue_response.status_code != 200:
                raise Exception(f"Failed to queue workflow: {queue_response.text}")
            
            queue_data = queue_response.json()
            prompt_id = queue_data.get("prompt_id")
            
            # 생성 완료까지 대기 (WebSocket 연결 또는 폴링)
            result = await self._wait_for_completion(prompt_id)
            
            return ImageGenerationResponse(
                job_id=job_id,
                status="completed",
                images=result.get("images", []),
                prompt_used=request.prompt,
                generation_time=result.get("generation_time"),
                metadata={
                    "prompt_id": prompt_id,
                    "comfyui_server": self.server_url,
                    "workflow_type": "txt2img",
                    "settings": request.dict()
                }
            )
            
        except Exception as e:
            logger.error(f"ComfyUI generation failed: {e}")
            return ImageGenerationResponse(
                job_id=str(uuid.uuid4()),
                status="failed",
                images=[],
                prompt_used=request.prompt,
                metadata={"error": str(e)}
            )
    
    async def _generate_mock_image(self, request: ImageGenerationRequest) -> ImageGenerationResponse:
        """Mock 이미지 생성 (ComfyUI 서버 없을 때)"""
        
        # 시뮬레이션 지연
        await asyncio.sleep(2)
        
        job_id = str(uuid.uuid4())
        
        # Mock 이미지 URL (실제로는 생성된 이미지)
        mock_images = [
            "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==",  # 1x1 픽셀 이미지
        ]
        
        return ImageGenerationResponse(
            job_id=job_id,
            status="completed",
            images=mock_images,
            prompt_used=request.prompt,
            generation_time=2.0,
            metadata={
                "note": "Mock image generation - 실제 ComfyUI 서버 연결 시 실제 이미지가 생성됩니다",
                "mock_data": True,
                "prompt": request.prompt,
                "settings": request.dict()
            }
        )
    
    async def _get_mock_status(self, job_id: str) -> ImageGenerationResponse:
        """Mock 상태 조회"""
        return ImageGenerationResponse(
            job_id=job_id,
            status="completed",
            images=["mock_image_url"],
            prompt_used="mock prompt",
            metadata={"mock_data": True}
        )
    
    async def _get_real_status(self, job_id: str) -> ImageGenerationResponse:
        """실제 상태 조회"""
        # 실제 ComfyUI 상태 조회 로직
        # 구현 필요
        pass
    
    def _create_workflow(self, request: ImageGenerationRequest) -> Dict[str, Any]:
        """
        ComfyUI 워크플로우 JSON 생성
        
        기본적인 txt2img 워크플로우 템플릿
        """
        
        # 기본 워크플로우 템플릿 (Stable Diffusion 기준)
        workflow = {
            "3": {
                "inputs": {
                    "seed": request.seed or -1,
                    "steps": request.steps,
                    "cfg": request.cfg_scale,
                    "sampler_name": "euler",
                    "scheduler": "normal",
                    "denoise": 1,
                    "model": ["4", 0],
                    "positive": ["6", 0],
                    "negative": ["7", 0],
                    "latent_image": ["5", 0]
                },
                "class_type": "KSampler"
            },
            "4": {
                "inputs": {
                    "ckpt_name": "sd_xl_base_1.0.safetensors"  # 기본 모델
                },
                "class_type": "CheckpointLoaderSimple"
            },
            "5": {
                "inputs": {
                    "width": request.width,
                    "height": request.height,
                    "batch_size": 1
                },
                "class_type": "EmptyLatentImage"
            },
            "6": {
                "inputs": {
                    "text": request.prompt,
                    "clip": ["4", 1]
                },
                "class_type": "CLIPTextEncode"
            },
            "7": {
                "inputs": {
                    "text": request.negative_prompt or "low quality, blurry",
                    "clip": ["4", 1]
                },
                "class_type": "CLIPTextEncode"
            },
            "8": {
                "inputs": {
                    "samples": ["3", 0],
                    "vae": ["4", 2]
                },
                "class_type": "VAEDecode"
            },
            "9": {
                "inputs": {
                    "filename_prefix": "ComfyUI",
                    "images": ["8", 0]
                },
                "class_type": "SaveImage"
            }
        }
        
        return workflow
    
    async def _wait_for_completion(self, prompt_id: str, timeout: int = 300) -> Dict[str, Any]:
        """
        ComfyUI 생성 완료까지 대기
        
        WebSocket 또는 폴링을 통해 상태 확인
        """
        
        # WebSocket 연결로 실시간 상태 확인
        try:
            ws_url = f"ws://127.0.0.1:8188/ws?clientId={self.client_id}"
            
            # 간단한 폴링 방식으로 구현 (WebSocket 구현은 복잡함)
            for _ in range(timeout):
                await asyncio.sleep(1)
                
                # 히스토리 확인
                history_response = requests.get(f"{self.server_url}/history/{prompt_id}")
                if history_response.status_code == 200:
                    history_data = history_response.json()
                    if prompt_id in history_data:
                        # 완료된 경우 이미지 URL 추출
                        result = history_data[prompt_id]
                        images = self._extract_images_from_history(result)
                        return {
                            "images": images,
                            "generation_time": 1.0  # 실제 시간 계산 필요
                        }
            
            # 타임아웃
            raise Exception(f"Generation timeout after {timeout} seconds")
            
        except Exception as e:
            logger.error(f"Failed to wait for completion: {e}")
            raise
    
    def _extract_images_from_history(self, history_data: Dict[str, Any]) -> List[str]:
        """히스토리 데이터에서 이미지 URL 추출"""
        
        images = []
        
        try:
            outputs = history_data.get("outputs", {})
            for node_id, node_output in outputs.items():
                if "images" in node_output:
                    for image_info in node_output["images"]:
                        filename = image_info.get("filename")
                        if filename:
                            # ComfyUI 서버의 이미지 URL 생성
                            image_url = f"{self.server_url}/view?filename={filename}"
                            images.append(image_url)
        
        except Exception as e:
            logger.error(f"Failed to extract images: {e}")
        
        return images


# 싱글톤 패턴으로 서비스 인스턴스 관리
_comfyui_service_instance = None

def get_comfyui_service() -> ComfyUIService:
    """ComfyUI 서비스 싱글톤 인스턴스 반환"""
    global _comfyui_service_instance
    if _comfyui_service_instance is None:
        _comfyui_service_instance = ComfyUIService()
    return _comfyui_service_instance

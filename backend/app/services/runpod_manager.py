"""
RunPod Serverless 관리 서비스
RunPod API를 사용하여 여러 타입의 serverless endpoint를 동적으로 생성/관리
TTS, vLLM, Fine-tuning 각각의 엔드포인트를 별도로 관리
"""

import os
import json
import logging
import httpx
from typing import Optional, Dict, Any, List, Literal
from datetime import datetime
import os
from dotenv import load_dotenv
from abc import ABC, abstractmethod

load_dotenv()

logger = logging.getLogger(__name__)


class RunPodManagerError(Exception):
    """RunPod 관리자 오류"""
    pass


ServiceType = Literal["tts", "vllm", "finetuning"]


class BaseRunPodManager(ABC):
    """RunPod 엔드포인트 관리자 베이스 클래스"""
    
    def __init__(self, service_type: ServiceType):
        self.api_key = os.getenv("RUNPOD_API_KEY", "")
        self.base_url = "https://api.runpod.io/graphql"
        self.service_type = service_type
        
        if not self.api_key:
            raise RunPodManagerError("RUNPOD_API_KEY가 설정되지 않았습니다")
    
    @property
    @abstractmethod
    def docker_image(self) -> str:
        """Docker 이미지명"""
        pass
    
    @property
    @abstractmethod
    def endpoint_name(self) -> str:
        """엔드포인트 이름"""
        pass
    
    @property
    @abstractmethod
    def container_disk_size(self) -> int:
        """컨테이너 디스크 크기 (GB)"""
        pass
    
    @property
    @abstractmethod
    def env_vars(self) -> List[Dict[str, str]]:
        """환경 변수"""
        pass
    
    @property
    @abstractmethod
    def search_keywords(self) -> List[str]:
        """엔드포인트 검색용 키워드"""
        pass
    
    @property
    def headers(self) -> Dict[str, str]:
        """API 요청 헤더"""
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
    
    async def list_endpoints(self) -> List[Dict[str, Any]]:
        """모든 serverless 엔드포인트 목록 조회"""
        query = """
        query {
            myself {
                endpoints {
                    id
                    name
                    templateId
                    workersMin
                    workersMax
                    template {
                        id
                        name
                        imageName
                        containerDiskInGb
                        volumeInGb
                    }
                }
            }
        }
        """
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers=self.headers,
                    json={"query": query}
                )
                
                if response.status_code != 200:
                    raise RunPodManagerError(f"엔드포인트 목록 조회 실패: {response.text}")
                
                data = response.json()
                
                if "errors" in data:
                    logger.error(f"GraphQL 오류: {data['errors']}")
                    raise RunPodManagerError(f"엔드포인트 조회 오류: {data['errors']}")
                
                endpoints = data.get("data", {}).get("myself", {}).get("endpoints", [])
                
                logger.info(f"📋 RunPod 엔드포인트 목록: {len(endpoints)}개")
                return endpoints
                
        except Exception as e:
            logger.error(f"❌ 엔드포인트 목록 조회 실패: {e}")
            raise RunPodManagerError(f"엔드포인트 목록 조회 실패: {e}")
    
    async def find_endpoint(self) -> Optional[Dict[str, Any]]:
        """서비스별 엔드포인트 찾기"""
        try:
            endpoints = await self.list_endpoints()
            
            for endpoint in endpoints:
                logger.info(f"엔드포인트 정보: {endpoint}")
                template = endpoint.get("template", {})
                
                # 다양한 조건으로 매칭 시도
                image_name = template.get("imageName", "")
                endpoint_name = endpoint.get("name", "")
                template_name = template.get("name", "")
                
                # Docker 이미지 정확 매칭 우선
                if self.docker_image in image_name or image_name in self.docker_image:
                    logger.info(f"✅ 기존 엔드포인트 찾음 (이미지 매칭): {endpoint['id']}")
                    logger.info(f"   - 엔드포인트 이름: {endpoint_name}")
                    logger.info(f"   - 템플릿 이름: {template_name}")
                    logger.info(f"   - Docker 이미지: {image_name}")
                    logger.info(f"   - 전체 엔드포인트 정보: {endpoint}")
                    return endpoint
                
                # 키워드 매칭
                for keyword in self.search_keywords:
                    if (keyword in image_name.lower() or
                        keyword in endpoint_name.lower() or
                        keyword in template_name.lower()):
                        logger.info(f"✅ 기존 엔드포인트 찾음 (키워드 '{keyword}' 매칭): {endpoint['id']}")
                        logger.info(f"   - 엔드포인트 이름: {endpoint_name}")
                        logger.info(f"   - 템플릿 이름: {template_name}")
                        logger.info(f"   - Docker 이미지: {image_name}")
                        return endpoint
            
            logger.info(f"ℹ️ {self.service_type} 엔드포인트를 찾을 수 없습니다")
            return None
            
        except Exception as e:
            logger.error(f"❌ {self.service_type} 엔드포인트 검색 실패: {e}")
            return None
    
    async def create_template(self) -> Dict[str, Any]:
        """새로운 serverless 템플릿 생성"""
        mutation = """
        mutation saveTemplate($input: SaveTemplateInput!) {
            saveTemplate(input: $input) {
                id
                name
                imageName
                containerDiskInGb
            }
        }
        """
        
        variables = {
            "input": {
                "name": self.endpoint_name,
                "imageName": self.docker_image,
                "dockerArgs": "",  # Required field
                "containerDiskInGb": self.container_disk_size,
                "volumeInGb": 0,
                "ports": "8000/http",
                "env": self.env_vars,
                "isServerless": True
            }
        }
        
        try:
            logger.info(f"📝 새 RunPod 템플릿 생성 중: {self.endpoint_name}")
            
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    self.base_url,
                    headers=self.headers,
                    json={"query": mutation, "variables": variables}
                )
                
                if response.status_code != 200:
                    raise RunPodManagerError(f"템플릿 생성 실패: {response.text}")
                
                data = response.json()
                
                if "errors" in data:
                    raise RunPodManagerError(f"GraphQL 오류: {data['errors']}")
                
                template = data.get("data", {}).get("saveTemplate")
                
                if not template:
                    raise RunPodManagerError("템플릿 생성 응답이 비어있습니다")
                
                logger.info(f"✅ 템플릿 생성 완료: {template['id']}")
                return template
                
        except Exception as e:
            logger.error(f"❌ 템플릿 생성 실패: {e}")
            raise RunPodManagerError(f"템플릿 생성 실패: {e}")
    
    async def create_endpoint(self, template_id: str) -> Dict[str, Any]:
        """템플릿을 사용하여 새로운 serverless 엔드포인트 생성"""
        mutation = """
        mutation {
            saveEndpoint(input: {
                templateId: "%s"
                name: "%s"
                workersMin: 0
                workersMax: 3
                idleTimeout: 5
                locations: "US"
                networkVolumeId: ""
                scalerType: "QUEUE_DELAY"
                scalerValue: 4
            }) {
                id
                name
                templateId
                workersMin
                workersMax
            }
        }
        """ % (template_id, self.endpoint_name)
        
        try:
            logger.info(f"🚀 템플릿 {template_id}를 사용하여 엔드포인트 생성 중")
            
            async with httpx.AsyncClient(timeout=60) as client:
                response = await client.post(
                    self.base_url,
                    headers=self.headers,
                    json={"query": mutation}
                )
                
                if response.status_code != 200:
                    raise RunPodManagerError(f"엔드포인트 생성 실패: {response.text}")
                
                data = response.json()
                
                if "errors" in data:
                    raise RunPodManagerError(f"GraphQL 오류: {data['errors']}")
                
                endpoint = data.get("data", {}).get("saveEndpoint")
                
                if not endpoint:
                    raise RunPodManagerError("엔드포인트 생성 응답이 비어있습니다")
                
                logger.info(f"✅ 엔드포인트 생성 완료: {endpoint['id']}")
                return endpoint
                
        except Exception as e:
            logger.error(f"❌ 엔드포인트 생성 실패: {e}")
            raise RunPodManagerError(f"엔드포인트 생성 실패: {e}")
    
    async def get_or_create_endpoint(self) -> Dict[str, Any]:
        """엔드포인트 가져오기 또는 생성"""
        try:
            # 기존 엔드포인트 찾기
            endpoint = await self.find_endpoint()
            
            if endpoint:
                logger.info(f"♻️ 기존 엔드포인트 사용: {endpoint['id']}")
                # 환경 변수에 저장
                os.environ["RUNPOD_ENDPOINT_ID"] = endpoint["id"]
                return endpoint
            
            # 엔드포인트를 찾지 못한 경우
            logger.error("❌ zonos-tts-worker 엔드포인트를 찾을 수 없습니다")
            logger.info("💡 RunPod 대시보드에서 다음 설정으로 엔드포인트를 생성하세요:")
            logger.info(f"   - Docker 이미지: {self.docker_image}")
            logger.info(f"   - 컨테이너 크기: {self.container_disk_size}GB")
            logger.info("   - 또는 기존 엔드포인트가 있다면 이름이나 Docker 이미지를 확인하세요")
            
            raise RunPodManagerError(
                "zonos-tts-worker 엔드포인트를 찾을 수 없습니다. "
                "RunPod 대시보드에서 엔드포인트를 생성하거나 기존 엔드포인트 설정을 확인하세요."
            )
            
        except Exception as e:
            logger.error(f"❌ 엔드포인트 가져오기/생성 실패: {e}")
            raise RunPodManagerError(f"엔드포인트 관리 실패: {e}")
    
    async def get_endpoint_status(self, endpoint_id: str) -> Dict[str, Any]:
        """엔드포인트 상태 확인"""
        query = """
        query GetEndpointStatus($endpointId: String!) {
            endpoint(id: $endpointId) {
                id
                name
                workersMin
                workersMax
                workersRunning
                workersThrottled
                queuedRequests
                avgResponseTime
                template {
                    name
                    imageName
                }
            }
        }
        """
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers=self.headers,
                    json={
                        "query": query,
                        "variables": {"endpointId": endpoint_id}
                    }
                )
                
                if response.status_code != 200:
                    raise RunPodManagerError(f"상태 확인 실패: {response.text}")
                
                data = response.json()
                
                if "errors" in data:
                    logger.error(f"GraphQL 오류: {data['errors']}")
                    return {"status": "error", "error": str(data['errors'])}
                
                status = data.get("data", {}).get("endpoint", {})
                
                logger.info(f"📊 엔드포인트 상태: {status}")
                return status
                
        except Exception as e:
            logger.error(f"❌ 엔드포인트 상태 확인 실패: {e}")
            return {"status": "error", "error": str(e)}


# 각 서비스별 구체적인 매니저 클래스
class TTSRunPodManager(BaseRunPodManager):
    """TTS 서비스용 RunPod 매니저"""
    
    def __init__(self):
        super().__init__("tts")
    
    @property
    def docker_image(self) -> str:
        return "fallsnowing/zonos-tts-worker"
    
    @property
    def endpoint_name(self) -> str:
        return "zonos-tts-worker"
    
    @property
    def container_disk_size(self) -> int:
        return 50  # GB
    
    @property
    def env_vars(self) -> List[Dict[str, str]]:
        return [
            {"key": "MODEL_NAME", "value": "zonos-tts"},
            {"key": "LANGUAGE", "value": "ko"}
        ]
    
    @property
    def search_keywords(self) -> List[str]:
        return ["zonos", "tts", "voice", "speech"]
    
    async def generate_voice(
        self,
        text: str,
        voice_id: Optional[str] = None,
        language: str = "ko",
        **kwargs
    ) -> Dict[str, Any]:
        """TTS 음성 생성"""
        import httpx
        import json
        
        try:
            # 엔드포인트 찾기
            endpoint = await self.find_endpoint()
            if not endpoint or not endpoint.get("id"):
                raise RunPodManagerError("TTS 엔드포인트를 찾을 수 없습니다")
            
            endpoint_id = endpoint["id"]
            
            # 페이로드 구성
            payload = {
                "input": {
                    "text": text,
                    "language": language
                }
            }
            
            # 음성 ID가 있으면 추가
            if voice_id:
                payload["input"]["voice_id"] = voice_id
            
            # 추가 파라미터가 있으면 추가
            for key, value in kwargs.items():
                if value is not None:
                    payload["input"][key] = value
            
            # RunPod API 호출
            base_url = "https://api.runpod.ai/v2"
            api_key = os.getenv("RUNPOD_API_KEY")
            
            if not api_key:
                raise RunPodManagerError("RUNPOD_API_KEY가 설정되지 않았습니다")
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # 동기 호출 사용
            url = f"{base_url}/{endpoint_id}/runsync"
            
            logger.info(f"🎵 TTS 음성 생성 요청: {url}")
            logger.info(f"📦 Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
            
            async with httpx.AsyncClient(timeout=300) as client:
                response = await client.post(url, headers=headers, json=payload)
                
                if response.status_code != 200:
                    error_msg = f"RunPod TTS API 오류: {response.status_code} - {response.text}"
                    logger.error(f"❌ {error_msg}")
                    logger.error(f"❌ 요청 URL: {url}")
                    logger.error(f"❌ 엔드포인트 ID: {endpoint_id}")
                    raise RunPodManagerError(error_msg)
                
                result = response.json()
                logger.info(f"✅ TTS 음성 생성 성공")
                
                return result
                    
        except Exception as e:
            logger.error(f"❌ TTS 음성 생성 실패: {e}")
            raise RunPodManagerError(f"TTS 음성 생성 실패: {e}")
    
    async def health_check(self) -> bool:
        """TTS 엔드포인트 상태 확인"""
        try:
            endpoint = await self.find_endpoint()
            return endpoint is not None and endpoint.get("id") is not None
        except Exception as e:
            logger.warning(f"⚠️ TTS 상태 확인 실패: {e}")
            return False


class VLLMRunPodManager(BaseRunPodManager):
    """vLLM 서비스용 RunPod 매니저"""
    
    def __init__(self):
        super().__init__("vllm")
    
    @property
    def docker_image(self) -> str:
        return "fallsnowing/exaone-vllm-worker"  # 실제 RunPod에서 사용 중인 이미지
    
    @property
    def endpoint_name(self) -> str:
        return "vllm-lora-worker"
    
    @property
    def container_disk_size(self) -> int:
        return 100  # GB - vLLM은 더 큰 저장소가 필요
    
    @property
    def env_vars(self) -> List[Dict[str, str]]:
        return [
            {"key": "MODEL_NAME", "value": "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct"},
            {"key": "MAX_MODEL_LEN", "value": "4096"},
            {"key": "TENSOR_PARALLEL_SIZE", "value": "1"},
            {"key": "GPU_MEMORY_UTILIZATION", "value": "0.85"},
            {"key": "DISABLE_V2_BLOCK_MANAGER", "value": "true"},
            {"key": "VLLM_ENGINE_ARGS", "value": "--gpu-memory-utilization 0.85 --max-model-len 4096"},
            {"key": "PYTORCH_CUDA_ALLOC_CONF", "value": "expandable_segments:True"}
        ]
    
    @property
    def search_keywords(self) -> List[str]:
        return ["vllm", "llama", "lora", "generation", "chat"]
    
    async def generate_text(
        self,
        prompt: str,
        lora_adapter: Optional[str] = None,
        system_message: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 512,
        hf_token: Optional[str] = None,
        hf_repo: Optional[str] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """vLLM 텍스트 생성"""
        import httpx
        import json
        
        try:
            # 엔드포인트 찾기
            endpoint = await self.find_endpoint()
            if not endpoint or not endpoint.get("id"):
                raise RunPodManagerError("vLLM 엔드포인트를 찾을 수 없습니다")
            
            endpoint_id = endpoint["id"]
            
            # 페이로드 구성
            payload = {
                "input": {
                    "prompt": prompt,
                    "system_message": system_message,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": stream
                }
            }
            
            # LoRA 어댑터가 있으면 추가
            if lora_adapter:
                logger.info(f"🔧 LoRA 어댑터 설정: lora_adapter={lora_adapter}, hf_repo={hf_repo}")
                if hf_repo:
                    payload["input"]["lora_adapter"] = f"hf://{hf_repo}"
                    logger.info(f"✅ HF repository 경로 사용: hf://{hf_repo}")
                else:
                    payload["input"]["lora_adapter"] = lora_adapter
                    logger.warning(f"⚠️ HF repository 없이 UUID 사용: {lora_adapter}")
                    
                # HF 토큰이 있으면 추가
                if hf_token:
                    payload["input"]["hf_token"] = hf_token
                    logger.info(f"🔑 HF 토큰 포함 (길이: {len(hf_token)})")
            
            # RunPod API 호출
            base_url = "https://api.runpod.ai/v2"
            api_key = os.getenv("RUNPOD_API_KEY")
            
            if not api_key:
                raise RunPodManagerError("RUNPOD_API_KEY가 설정되지 않았습니다")
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            # 동기 호출 사용
            url = f"{base_url}/{endpoint_id}/runsync"
            
            logger.info(f"🤖 vLLM 텍스트 생성 요청: {url}")
            logger.info(f"📦 Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
            
            async with httpx.AsyncClient(timeout=300) as client:
                response = await client.post(url, headers=headers, json=payload)
                
                if response.status_code != 200:
                    error_msg = f"RunPod API 오류: {response.status_code} - {response.text}"
                    logger.error(f"❌ {error_msg}")
                    logger.error(f"❌ 요청 URL: {url}")
                    logger.error(f"❌ 엔드포인트 ID: {endpoint_id}")
                    raise RunPodManagerError(error_msg)
                
                result = response.json()
                
                logger.info(f"✅ vLLM 텍스트 생성 성공",result)
                
                # RunPod 응답 형식 처리
                if result.get("status") == "COMPLETED":
                    # output 내부의 generated_text 추출
                    output = result.get("output", {})
                    generated_text = output.get("generated_text", "")
                    
                    return {
                        "status": "completed",
                        "generated_text": generated_text,
                        "model": output.get("model", ""),
                        "lora_adapter": output.get("lora_adapter", ""),
                        "used_lora": output.get("used_lora", False)
                    }
                elif result.get("status") == "success":
                    # 이전 형식 호환성을 위한 처리
                    return {
                        "status": "completed",
                        "output": result
                    }
                else:
                    return {
                        "status": "failed", 
                        "error": result.get("error", "알 수 없는 오류")
                    }
                    
        except Exception as e:
            logger.error(f"❌ vLLM 텍스트 생성 실패: {e}")
            raise RunPodManagerError(f"vLLM 텍스트 생성 실패: {e}")
    
    async def health_check(self) -> bool:
        """vLLM 엔드포인트 상태 확인"""
        try:
            endpoint = await self.find_endpoint()
            return endpoint is not None and endpoint.get("id") is not None
        except Exception as e:
            logger.warning(f"⚠️ vLLM 상태 확인 실패: {e}")
            return False
    
    async def generate_text_stream(
        self,
        prompt: str,
        lora_adapter: Optional[str] = None,
        system_message: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 512,
        hf_token: Optional[str] = None,
        hf_repo: Optional[str] = None
    ):
        """vLLM 스트리밍 텍스트 생성 (실제 /stream 엔드포인트 사용)"""
        import httpx
        import json
        
        try:
            # 엔드포인트 찾기
            endpoint = await self.find_endpoint()
            if not endpoint or not endpoint.get("id"):
                logger.warning("⚠️ vLLM 엔드포인트를 찾을 수 없어 폴백 방식을 사용합니다")
                async for token in self._fallback_streaming(prompt, lora_adapter, system_message, temperature, max_tokens, hf_token, hf_repo):
                    yield token
                return
            
            endpoint_id = endpoint["id"]
            
            # 페이로드 구성
            payload = {
                "input": {
                    "prompt": prompt,
                    "system_message": system_message,
                    "temperature": temperature,
                    "max_tokens": max_tokens,
                    "stream": True
                }
            }
            
            # LoRA 어댑터가 있으면 추가
            if lora_adapter:
                logger.info(f"🔧 LoRA 어댑터 설정: lora_adapter={lora_adapter}, hf_repo={hf_repo}")
                if hf_repo:
                    payload["input"]["lora_adapter"] = lora_adapter
                    payload["input"]["hf_repo"] = hf_repo
                    logger.info(f"✅ HF repository 경로 사용: {hf_repo}")
                else:
                    payload["input"]["lora_adapter"] = lora_adapter
                    logger.warning(f"⚠️ HF repository 없이 UUID 사용: {lora_adapter}")
                    
                # HF 토큰이 있으면 추가
                if hf_token:
                    payload["input"]["hf_token"] = hf_token
                    logger.info(f"🔑 HF 토큰 포함 (길이: {len(hf_token)})")
            
            # RunPod API 호출
            base_url = "https://api.runpod.ai/v2"
            api_key = os.getenv("RUNPOD_API_KEY")
            
            if not api_key:
                raise RunPodManagerError("RUNPOD_API_KEY가 설정되지 않았습니다")
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "text/event-stream",
                "Cache-Control": "no-cache"
            }
            
            # 스트리밍 엔드포인트를 먼저 시도
            stream_url = f"{base_url}/{endpoint_id}/stream"
            
            logger.info(f"🌊 vLLM 스트리밍 요청: {stream_url}")
            logger.info(f"📦 Payload: {json.dumps(payload, indent=2, ensure_ascii=False)}")
            
            try:
                async with httpx.AsyncClient(timeout=300) as client:
                    async with client.stream(
                        "POST", 
                        stream_url, 
                        headers=headers, 
                        json=payload
                    ) as response:
                        
                        if response.status_code == 200:
                            logger.info("✅ 실제 스트리밍 시작")
                            
                            # SSE 스트림 처리
                            async for line in response.aiter_lines():
                                if line.startswith("data: "):
                                    data_str = line[6:]  # "data: " 제거
                                    if data_str.strip():
                                        try:
                                            data = json.loads(data_str)
                                            
                                            # 토큰이 있으면 yield
                                            if "text" in data and data["text"]:
                                                yield data["text"]
                                            
                                            # 완료 신호 확인
                                            if data.get("finished") or data.get("done"):
                                                logger.info("✅ 스트리밍 완료")
                                                break
                                                
                                        except json.JSONDecodeError:
                                            continue
                            
                            return  # 성공적으로 스트리밍 완료
                            
                        elif response.status_code == 404:
                            logger.warning("⚠️ /stream 엔드포인트가 존재하지 않아 폴백 방식을 사용합니다")
                        else:
                            logger.warning(f"⚠️ 스트리밍 요청 실패 ({response.status_code}), 폴백 방식을 사용합니다")
                            
            except Exception as stream_error:
                logger.warning(f"⚠️ 스트리밍 연결 실패: {stream_error}, 폴백 방식을 사용합니다")
            
            # 스트리밍 실패시 폴백 방식 사용
            async for token in self._fallback_streaming(prompt, lora_adapter, system_message, temperature, max_tokens, hf_token, hf_repo):
                yield token
                    
        except Exception as e:
            logger.error(f"❌ vLLM 스트리밍 실패: {e}")
            # 오류 발생 시 기본 오류 메시지를 스트리밍으로 반환
            yield f"오류가 발생했습니다: {str(e)}"
    
    async def _fallback_streaming(
        self,
        prompt: str,
        lora_adapter: Optional[str] = None,
        system_message: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 512,
        hf_token: Optional[str] = None,
        hf_repo: Optional[str] = None
    ):
        """폴백 스트리밍 방식 (동기 호출 후 토큰 분할)"""
        logger.info("🌊 폴백 스트리밍 방식 사용")
        
        try:
            # 동기 호출로 완전한 응답을 받은 후 청크로 나누어 스트리밍
            result = await self.generate_text(
                prompt=prompt,
                lora_adapter=lora_adapter,
                system_message=system_message,
                temperature=temperature,
                max_tokens=max_tokens,
                hf_token=hf_token,
                hf_repo=hf_repo,
                stream=False
            )
            
            # 응답에서 텍스트 추출
            generated_text = ""
            if result.get("status") == "completed" and result.get("output"):
                output = result["output"]
                if output.get("status") == "success":
                    generated_text = output.get("generated_text", "")
                else:
                    generated_text = "응답 생성에 실패했습니다."
            else:
                generated_text = result.get("generated_text", "응답 생성에 실패했습니다.")
            
            # 텍스트를 토큰 단위로 나누어 스트리밍 시뮬레이션
            if generated_text:
                import asyncio
                import re
                
                # 한국어와 영어를 고려한 토큰 분할 (단어 및 구두점 기준)
                tokens = re.findall(r'\S+|\s+', generated_text)
                
                logger.info(f"🌊 폴백 스트리밍 시작: {len(tokens)}개 토큰")
                
                for i, token in enumerate(tokens):
                    # 스트리밍 효과를 위한 짧은 지연
                    if i > 0:  # 첫 번째 토큰은 바로 전송
                        await asyncio.sleep(0.05)  # 50ms 지연
                    
                    yield token
                
                logger.info(f"✅ 폴백 스트리밍 완료: {len(tokens)}개 토큰 전송")
            else:
                # 빈 응답인 경우 기본 메시지 반환
                yield "죄송합니다. 응답을 생성할 수 없습니다."
                    
        except Exception as e:
            logger.error(f"❌ vLLM 폴백 스트리밍 실패: {e}")
            # 오류 발생 시 기본 오류 메시지를 스트리밍으로 반환
            yield f"오류가 발생했습니다: {str(e)}"


class FinetuningRunPodManager(BaseRunPodManager):
    """Fine-tuning 서비스용 RunPod 매니저"""
    
    def __init__(self):
        super().__init__("finetuning")
    
    @property
    def docker_image(self) -> str:
        return "fallsnowing/finetuning-worker"  # 실제 이미지명으로 변경 필요
    
    @property
    def endpoint_name(self) -> str:
        return "finetuning-worker"
    
    @property
    def container_disk_size(self) -> int:
        return 200  # GB - Fine-tuning은 더 많은 저장소가 필요
    
    @property
    def env_vars(self) -> List[Dict[str, str]]:
        return [
            {"key": "BASE_MODEL", "value": "LGAI-EXAONE/EXAONE-3.5-2.4B-Instruct"},
            {"key": "TRAINING_FRAMEWORK", "value": "axolotl"},
            {"key": "MAX_STEPS", "value": "1000"},
            {"key": "GPU_MEMORY_UTILIZATION", "value": "0.85"},
            {"key": "DISABLE_V2_BLOCK_MANAGER", "value": "true"},
            {"key": "VLLM_ENGINE_ARGS", "value": "--gpu-memory-utilization 0.85 --max-model-len 4096"},
            {"key": "PYTORCH_CUDA_ALLOC_CONF", "value": "expandable_segments:True"}
        ]
    
    @property
    def search_keywords(self) -> List[str]:
        return ["finetuning", "training", "axolotl", "lora", "qlora"]


# 기존 RunPodManager를 BaseRunPodManager 상속으로 변경 (하위 호환성)
class RunPodManager(TTSRunPodManager):
    """기존 RunPodManager - TTS 매니저의 별칭 (하위 호환성)"""
    pass


# 싱글톤 인스턴스들
_tts_manager = None
_vllm_manager = None
_finetuning_manager = None
_runpod_manager = None  # 기존 호환성


def get_tts_manager() -> TTSRunPodManager:
    """TTS RunPod 매니저 싱글톤 인스턴스 반환"""
    global _tts_manager
    if _tts_manager is None:
        _tts_manager = TTSRunPodManager()
    return _tts_manager


def get_vllm_manager() -> VLLMRunPodManager:
    """vLLM RunPod 매니저 싱글톤 인스턴스 반환"""
    global _vllm_manager
    if _vllm_manager is None:
        _vllm_manager = VLLMRunPodManager()
    return _vllm_manager


def get_finetuning_manager() -> FinetuningRunPodManager:
    """Fine-tuning RunPod 매니저 싱글톤 인스턴스 반환"""
    global _finetuning_manager
    if _finetuning_manager is None:
        _finetuning_manager = FinetuningRunPodManager()
    return _finetuning_manager


def get_runpod_manager() -> RunPodManager:
    """기존 RunPod 관리자 싱글톤 인스턴스 반환 (하위 호환성)"""
    global _runpod_manager
    if _runpod_manager is None:
        _runpod_manager = RunPodManager()
    return _runpod_manager


def get_manager_by_service_type(service_type: ServiceType) -> BaseRunPodManager:
    """서비스 타입별 매니저 반환"""
    if service_type == "tts":
        return get_tts_manager()
    elif service_type == "vllm":
        return get_vllm_manager()
    elif service_type == "finetuning":
        return get_finetuning_manager()
    else:
        raise ValueError(f"지원하지 않는 서비스 타입: {service_type}")


# 서버 시작 시 초기화 함수
async def initialize_runpod():
    """서버 시작 시 RunPod 다중 서비스 초기화"""
    try:
        logger.info("🏁 RunPod 다중 서비스 초기화 시작")
        
        # API 키 확인
        if not os.getenv("RUNPOD_API_KEY"):
            logger.warning("⚠️ RUNPOD_API_KEY가 설정되지 않았습니다. RunPod 기능이 비활성화됩니다.")
            return None
        
        initialized_services = {}
        
        # TTS 서비스 초기화
        try:
            logger.info("🎤 TTS 서비스 초기화 중...")
            tts_manager = get_tts_manager()
            tts_endpoint = await tts_manager.get_or_create_endpoint()
            
            if tts_endpoint:
                initialized_services["tts"] = tts_endpoint
                os.environ["RUNPOD_TTS_ENDPOINT_ID"] = tts_endpoint["id"]
                logger.info(f"✅ TTS 서비스 초기화 완료: {tts_endpoint['id']}")
            else:
                logger.warning("⚠️ TTS 엔드포인트 초기화 실패")
        except Exception as e:
            logger.warning(f"⚠️ TTS 서비스 초기화 실패: {e}")
        
        # vLLM 서비스 초기화 (선택적)
        try:
            logger.info("🤖 vLLM 서비스 초기화 중...")
            vllm_manager = get_vllm_manager()
            vllm_endpoint = await vllm_manager.find_endpoint()  # 생성하지 말고 찾기만
            
            if vllm_endpoint:
                initialized_services["vllm"] = vllm_endpoint
                os.environ["RUNPOD_VLLM_ENDPOINT_ID"] = vllm_endpoint["id"]
                logger.info(f"✅ vLLM 서비스 발견됨: {vllm_endpoint['id']}")
            else:
                logger.info("ℹ️ vLLM 엔드포인트를 찾을 수 없습니다 (필요시 수동 생성)")
        except Exception as e:
            logger.info(f"ℹ️ vLLM 서비스 확인 실패: {e}")
        
        # Fine-tuning 서비스 초기화 (선택적)
        try:
            logger.info("🏋️ Fine-tuning 서비스 초기화 중...")
            finetuning_manager = get_finetuning_manager()
            finetuning_endpoint = await finetuning_manager.find_endpoint()  # 생성하지 말고 찾기만
            
            if finetuning_endpoint:
                initialized_services["finetuning"] = finetuning_endpoint
                os.environ["RUNPOD_FINETUNING_ENDPOINT_ID"] = finetuning_endpoint["id"]
                logger.info(f"✅ Fine-tuning 서비스 발견됨: {finetuning_endpoint['id']}")
            else:
                logger.info("ℹ️ Fine-tuning 엔드포인트를 찾을 수 없습니다 (필요시 수동 생성)")
        except Exception as e:
            logger.info(f"ℹ️ Fine-tuning 서비스 확인 실패: {e}")
        
        # 하위 호환성을 위해 TTS 엔드포인트를 기본값으로 설정
        if "tts" in initialized_services:
            os.environ["RUNPOD_ENDPOINT_ID"] = initialized_services["tts"]["id"]
        
        if initialized_services:
            logger.info(f"✅ RunPod 초기화 완료: {list(initialized_services.keys())} 서비스")
            return initialized_services
        else:
            logger.warning("⚠️ RunPod 서비스 초기화 실패 (TTS 기능이 제한될 수 있습니다)")
            return None
            
    except Exception as e:
        logger.error(f"❌ RunPod 초기화 중 오류: {e}")
        return None


async def initialize_service(service_type: ServiceType, create_if_missing: bool = False):
    """특정 서비스 초기화"""
    try:
        logger.info(f"🔧 {service_type} 서비스 초기화 중...")
        
        manager = get_manager_by_service_type(service_type)
        
        if create_if_missing:
            endpoint = await manager.get_or_create_endpoint()
        else:
            endpoint = await manager.find_endpoint()
        
        if endpoint:
            env_key = f"RUNPOD_{service_type.upper()}_ENDPOINT_ID"
            os.environ[env_key] = endpoint["id"]
            logger.info(f"✅ {service_type} 서비스 초기화 완료: {endpoint['id']}")
            return endpoint
        else:
            logger.warning(f"⚠️ {service_type} 엔드포인트를 찾을 수 없습니다")
            return None
            
    except Exception as e:
        logger.error(f"❌ {service_type} 서비스 초기화 실패: {e}")
        return None